"""Latch decision table for the low pressure alarm."""

from dataclasses import dataclass

from ..runtime.errors import ValidationError


@dataclass(frozen=True)
class LatchDecision:
    engaged: bool
    clearable: bool
    reason: str

    def describe(self) -> dict:
        return {"engaged": self.engaged, "clearable": self.clearable, "reason": self.reason}


class PressureLatch:
    """A latch clears only after an acknowledgement and a recovered pressure."""

    def __init__(self, low_bar: float, margin_bar: float) -> None:
        if margin_bar < 0:
            raise ValidationError("latch margin must not be negative", margin=margin_bar)
        self._low_bar = float(low_bar)
        self._margin_bar = float(margin_bar)

    @property
    def low_bar(self) -> float:
        return self._low_bar

    @property
    def clear_level_bar(self) -> float:
        return round(self._low_bar + self._margin_bar, 6)

    def should_engage(self, pressure_bar: float) -> bool:
        return pressure_bar < self._low_bar

    def decide(self, pressure_bar: float, engaged: bool, acknowledged: bool) -> LatchDecision:
        if not engaged:
            return LatchDecision(engaged=False, clearable=False, reason="latch is not engaged")
        if not acknowledged:
            return LatchDecision(engaged=True, clearable=False, reason="acknowledgement missing")
        if pressure_bar < self.clear_level_bar:
            return LatchDecision(
                engaged=True,
                clearable=False,
                reason="pressure has not recovered past the clear level",
            )
        return LatchDecision(engaged=True, clearable=True, reason="clear conditions satisfied")

    def describe(self) -> dict:
        return {"low_bar": self._low_bar, "clear_level_bar": self.clear_level_bar}
