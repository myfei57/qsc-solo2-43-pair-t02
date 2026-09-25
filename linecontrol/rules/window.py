"""Threshold windows used by the acceptance comparisons."""

from dataclasses import dataclass

from ..runtime.errors import ValidationError


@dataclass(frozen=True)
class Window:
    """A closed or open interval with a deterministic classification."""

    low: float
    high: float
    inclusive: bool = True

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValidationError("window low bound exceeds high bound", low=self.low, high=self.high)

    def contains(self, value: float) -> bool:
        if self.inclusive:
            return self.low <= value <= self.high
        return self.low < value < self.high

    def classify(self, value: float) -> str:
        if value < self.low:
            return "below"
        if value > self.high:
            return "above"
        return "inside"

    def clamp(self, value: float) -> float:
        if value < self.low:
            return self.low
        if value > self.high:
            return self.high
        return value

    @property
    def half_width(self) -> float:
        return round((self.high - self.low) / 2.0, 6)

    def describe(self) -> dict:
        return {
            "low": self.low,
            "high": self.high,
            "inclusive": self.inclusive,
            "half_width": self.half_width,
        }


def centered_window(center: float, half_width: float) -> Window:
    if half_width < 0:
        raise ValidationError("half_width must not be negative", half_width=half_width)
    return Window(low=round(center - half_width, 6), high=round(center + half_width, 6))
