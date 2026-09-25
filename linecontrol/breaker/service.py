"""Closing and opening the line breaker under the committed sync gate."""

from typing import Any, Dict, Optional

from ..contracts import CLOSE_KEYS, PHASE_KEYS
from ..rules.window import centered_window
from ..runtime.errors import OrderViolation
from ..store.kinds import (
    KIND_BREAKER_CLOSE,
    KIND_BREAKER_LATCH_RELEASE,
    KIND_BREAKER_OPEN,
    KIND_BREAKER_TRIP,
)
from .errors import BreakerLatched, ContactAngleOutOfRange
from .angle import contact_angle_deg
from .latch import LatchReleasePolicy

class BreakerService:
    def __init__(self, log, clock, registry, view, tickets, sync, load_kw) -> None:
        self._log = log
        self._clock = clock
        self._registry = registry
        self._view = view
        self._tickets = tickets
        self._sync = sync
        self._load_kw = load_kw
        self._policy = LatchReleasePolicy()

    def state(self) -> str:
        return self._view.breaker()

    def closed(self) -> bool:
        return self.state() == "closed"

    def latched(self) -> bool:
        return self._view.breaker_latched()

    def generation(self) -> int:
        return self._registry.combine(CLOSE_KEYS)

    def phase_generation(self) -> int:
        return self._registry.combine(PHASE_KEYS)

    def close(self, batch_id: str, ticket_id: str, phase_deg: float) -> Dict[str, Any]:
        if self.latched():
            raise BreakerLatched("a trip latch blocks closing")
        if self.closed():
            raise OrderViolation("breaker is already closed")
        self._sync.require_persisted(batch_id)
        baseline = self._sync.require_baseline()
        ticket = self._tickets.consume(
            ticket_id,
            self._sync.frequency_subject(),
            self._sync.frequency_generation(),
            self._clock.tick,
        )
        angle = contact_angle_deg(float(phase_deg), baseline.phase_deg)
        window = centered_window(0.0, self._registry.value("sync.phase_window_deg"))
        if not window.contains(angle):
            raise ContactAngleOutOfRange(
                "contact angle is outside the matching window",
                phase_deg=float(phase_deg),
                reference_deg=baseline.phase_deg,
                delta_deg=angle,
                window=window.describe(),
            )
        record = self._log.append(
            KIND_BREAKER_CLOSE,
            batch_id=batch_id,
            generation=self.generation(),
            payload={
                "batch": batch_id,
                "baseline": baseline.baseline_id,
                "phase_deg": float(phase_deg),
                "delta_deg": angle,
                "ticket": ticket.ticket_id,
            },
            tick=self._clock.tick,
        )
        self._log.commit(tick=self._clock.tick)
        return {
            "breaker": "closed",
            "batch": batch_id,
            "record": record.record_id,
            "delta_deg": angle,
            "ticket": ticket.ticket_id,
        }

    def open(self, reason: str) -> Dict[str, Any]:
        if not self.closed():
            raise OrderViolation("breaker is already open")
        record = self._log.append(
            KIND_BREAKER_OPEN,
            generation=self.phase_generation(),
            payload={"reason": reason},
            tick=self._clock.tick,
        )
        self._log.commit(tick=self._clock.tick)
        return {"breaker": "open", "record": record.record_id, "reason": reason}

    def trip(self, reason: str) -> Dict[str, Any]:
        if self.latched():
            raise BreakerLatched("a trip latch is already engaged")
        record = self._log.append(
            KIND_BREAKER_TRIP,
            generation=self.phase_generation(),
            payload={"alarm": "breaker.trip", "reason": reason},
            tick=self._clock.tick,
        )
        self._log.commit(tick=self._clock.tick)
        return {"breaker": "open", "latched": True, "record": record.record_id, "reason": reason}

    def release_decision(self):
        return self._policy.decide(self.latched(), self.state(), self._load_kw())

    def release_latch(self) -> Dict[str, Any]:
        decision = self.release_decision()
        if not decision.releasable:
            raise BreakerLatched(decision.reason, latched=self.latched(), breaker=self.state())
        record = self._log.append(
            KIND_BREAKER_LATCH_RELEASE,
            generation=self.phase_generation(),
            payload={"alarm": "breaker.trip", "reason": decision.reason},
            tick=self._clock.tick,
        )
        self._log.commit(tick=self._clock.tick)
        return {"latched": False, "record": record.record_id}

    def status(self) -> Dict[str, Any]:
        return {
            "breaker": self.state(),
            "closed": self.closed(),
            "latched": self.latched(),
            "generation": self.generation(),
            "release": self.release_decision().describe(),
        }
