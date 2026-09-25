"""Trip latch release policy."""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class LatchReleaseDecision:
    releasable: bool
    reason: str

    def describe(self) -> Dict[str, Any]:
        return {"releasable": self.releasable, "reason": self.reason}


class LatchReleasePolicy:
    """A trip latch is released only with the breaker open and no load held."""

    def __init__(self, load_tolerance_kw: float = 0.0) -> None:
        self._tolerance = float(load_tolerance_kw)

    def decide(self, latched: bool, breaker_state: str, load_kw: float) -> LatchReleaseDecision:
        if not latched:
            return LatchReleaseDecision(False, "no trip latch is engaged")
        if breaker_state != "open":
            return LatchReleaseDecision(False, "breaker must be open before the latch is released")
        if load_kw > self._tolerance:
            return LatchReleaseDecision(False, "load is still applied to the unit")
        return LatchReleaseDecision(True, "release conditions satisfied")
