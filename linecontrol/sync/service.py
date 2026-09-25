"""Calibration, window comparison and the durable sync result."""

from typing import Any, Dict, Optional

from ..contracts import BASELINE_KEYS, FREQUENCY_KEYS
from ..ns.units import check_frequency_band, normalize_angle_deg
from ..rules.uniqueness import BatchRegistry
from ..rules.window import centered_window
from ..runtime.errors import DuplicateRejected, NotPersisted, OutOfRange
from ..store.kinds import (
    KIND_SYNC_BASELINE,
    KIND_SYNC_COMMIT,
    KIND_SYNC_PERSIST,
)
from .baseline import Baseline
from .errors import BaselineExpired, BaselineMissing, BaselineStale, FrequencyOutOfWindow, PhaseOutOfWindow

FREQUENCY_SUBJECT = "gov.frequency"


class SyncService:
    def __init__(self, log, clock, registry, projector, tickets) -> None:
        self._log = log
        self._clock = clock
        self._registry = registry
        self._projector = projector
        self._tickets = tickets

    def generation(self) -> int:
        return self._registry.combine(BASELINE_KEYS)

    def frequency_generation(self) -> int:
        return self._registry.combine(FREQUENCY_KEYS)

    def frequency_subject(self) -> str:
        return FREQUENCY_SUBJECT

    def calibrate(
        self,
        phase_deg: float,
        freq_hz: float,
        ttl_ticks: Optional[int] = None,
    ) -> Baseline:
        check_frequency_band(float(freq_hz))
        angle = normalize_angle_deg(float(phase_deg))
        ttl = int(ttl_ticks) if ttl_ticks is not None else self._registry.integral("sync.baseline_ttl_ticks")
        if ttl <= 0:
            raise OutOfRange("baseline lifetime must be positive", ttl=ttl)
        generation = self.generation()
        record = self._log.append(
            KIND_SYNC_BASELINE,
            generation=generation,
            payload={
                "phase_deg": angle,
                "freq_hz": round(float(freq_hz), 6),
                "expires_tick": self._clock.tick + ttl,
                "ttl_ticks": ttl,
            },
            tick=self._clock.tick,
        )
        self._log.commit(tick=self._clock.tick)
        return Baseline.from_record(record)

    def baseline(self) -> Baseline:
        records = self._log.by_kind(KIND_SYNC_BASELINE)
        if not records:
            raise BaselineMissing("no calibration baseline has been recorded")
        return Baseline.from_record(records[-1])

    def require_baseline(self) -> Baseline:
        baseline = self.baseline()
        if baseline.expired(self._clock.tick):
            raise BaselineExpired(
                "calibration baseline has expired",
                baseline=baseline.baseline_id,
                expires_tick=baseline.expires_tick,
                now=self._clock.tick,
            )
        if baseline.generation != self.generation():
            raise BaselineStale(
                "calibration baseline belongs to an earlier parameter generation",
                baseline=baseline.baseline_id,
                expected=baseline.generation,
                observed=self.generation(),
            )
        return baseline

    def verify_frequency(
        self, measured_hz: float, baseline: Optional[Baseline] = None
    ) -> Dict[str, Any]:
        reference = baseline if baseline is not None else self.require_baseline()
        measured = float(measured_hz)
        check_frequency_band(measured)
        window = centered_window(reference.freq_hz, self._registry.value("sync.freq_window_hz"))
        delta = round(measured - reference.freq_hz, 6)
        if not window.contains(measured):
            raise FrequencyOutOfWindow(
                "measured frequency is outside the matching window",
                measured_hz=measured,
                reference_hz=reference.freq_hz,
                window=window.describe(),
            )
        return {
            "measured_hz": measured,
            "reference_hz": reference.freq_hz,
            "delta_hz": delta,
            "window": window.describe(),
            "baseline": reference.baseline_id,
        }

    def verify_phase(self, measured_deg: float, baseline: Optional[Baseline] = None) -> Dict[str, Any]:
        reference = baseline if baseline is not None else self.require_baseline()
        measured = normalize_angle_deg(float(measured_deg))
        delta = round(normalize_angle_deg(measured - reference.phase_deg), 6)
        window = centered_window(0.0, self._registry.value("sync.phase_window_deg"))
        if not window.contains(delta):
            raise PhaseOutOfWindow(
                "measured phase is outside the matching window",
                measured_deg=measured,
                reference_deg=reference.phase_deg,
                delta_deg=delta,
                window=window.describe(),
            )
        return {
            "measured_deg": measured,
            "reference_deg": reference.phase_deg,
            "delta_deg": delta,
            "window": window.describe(),
            "baseline": reference.baseline_id,
        }

    def batches(self, include_pending: bool = True) -> BatchRegistry:
        registry = BatchRegistry()
        records = list(self._log.visible())
        if include_pending:
            records.extend(self._log.pending())
        for record in records:
            if record.kind == KIND_SYNC_PERSIST and record.batch_id:
                registry.register(record.batch_id, record.digest, record.tick, record.kind)
        return registry

    def persist(self, batch_id: str) -> Dict[str, Any]:
        if not batch_id:
            raise OutOfRange("batch identifier must not be empty")
        baseline = self.require_baseline()
        if self.batches().seen(batch_id):
            raise DuplicateRejected("this batch already has a persisted sync result", batch=batch_id)
        record = self._log.append(
            KIND_SYNC_PERSIST,
            batch_id=batch_id,
            generation=baseline.generation,
            payload={
                "baseline": baseline.baseline_id,
                "phase_deg": baseline.phase_deg,
                "freq_hz": baseline.freq_hz,
                "generation": baseline.generation,
            },
            tick=self._clock.tick,
        )
        return {
            "batch": batch_id,
            "record": record.record_id,
            "committed": False,
            "baseline": baseline.baseline_id,
        }

    def commit(self, batch_id: str) -> Dict[str, Any]:
        pending = [record for record in self._log.pending() if record.batch_id == batch_id]
        if not pending and not self._log.is_committed(batch_id, KIND_SYNC_PERSIST):
            raise NotPersisted("nothing is waiting to be committed for this batch", batch=batch_id)
        marker = self._log.append(
            KIND_SYNC_COMMIT,
            batch_id=batch_id,
            generation=self.generation(),
            payload={"watermark_target": self._log.max_data_seq()},
            tick=self._clock.tick,
        )
        control = self._log.commit(tick=self._clock.tick)
        return {
            "batch": batch_id,
            "marker": marker.record_id,
            "commit_record": control.record_id,
            "watermark": self._log.watermark,
        }

    def is_persisted(self, batch_id: str) -> bool:
        return self._log.is_committed(batch_id, KIND_SYNC_PERSIST)

    def require_persisted(self, batch_id: str) -> None:
        if not self.is_persisted(batch_id):
            raise NotPersisted(
                "the sync result for this batch is not committed yet",
                batch=batch_id,
                watermark=self._log.watermark,
            )

    def confirm_frequency(self, measured_hz: float) -> Dict[str, Any]:
        baseline = self.require_baseline()
        report = self.verify_frequency(measured_hz, baseline)
        ttl = self._registry.integral("breaker.close_ticket_ttl_ticks")
        ticket = self._tickets.issue(
            FREQUENCY_SUBJECT,
            self.frequency_generation(),
            ttl,
            {"delta_hz": report["delta_hz"], "baseline": baseline.baseline_id},
            self._clock.tick,
        )
        return {"ticket": ticket.ticket_id, "frequency": report, "baseline": baseline.describe()}

    def status(self) -> Dict[str, Any]:
        try:
            baseline = self.baseline()
        except BaselineMissing:
            return {"baseline": None, "generation": self.generation()}
        return {
            "baseline": baseline.describe(),
            "generation": self.generation(),
            "expired": baseline.expired(self._clock.tick),
            "stale": baseline.generation != self.generation(),
            "remaining_ticks": baseline.remaining(self._clock.tick),
            "batches": self.batches().size(),
        }
