"""A calibration baseline carries the generation it was taken under."""

from dataclasses import dataclass
from typing import Any, Dict

from ..ns.units import normalize_angle_deg


@dataclass(frozen=True)
class Baseline:
    baseline_id: str
    generation: int
    phase_deg: float
    freq_hz: float
    issued_tick: int
    expires_tick: int

    def expired(self, now: int) -> bool:
        return now > self.expires_tick

    def remaining(self, now: int) -> int:
        return max(self.expires_tick - now, 0)

    def describe(self) -> Dict[str, Any]:
        return {
            "baseline": self.baseline_id,
            "generation": self.generation,
            "phase_deg": self.phase_deg,
            "freq_hz": self.freq_hz,
            "issued_tick": self.issued_tick,
            "expires_tick": self.expires_tick,
            "phase_normalized_deg": normalize_angle_deg(self.phase_deg),
        }

    @classmethod
    def from_record(cls, record) -> "Baseline":
        payload = record.payload
        return cls(
            baseline_id=record.record_id,
            generation=record.generation,
            phase_deg=float(payload["phase_deg"]),
            freq_hz=float(payload["freq_hz"]),
            issued_tick=record.tick,
            expires_tick=int(payload["expires_tick"]),
        )
