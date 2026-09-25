"""Deterministic tick clock used by every time based decision."""

from .errors import ValidationError


class VirtualClock:
    """A monotone tick counter. No wall clock, no sleeping."""

    def __init__(self, start: int = 0, step: int = 1) -> None:
        if start < 0:
            raise ValidationError("start must not be negative", start=start)
        if step <= 0:
            raise ValidationError("step must be positive", step=step)
        self._tick = int(start)
        self._step = int(step)

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def step(self) -> int:
        return self._step

    def advance(self, count: int = 1) -> int:
        if count < 0:
            raise ValidationError("count must not be negative", count=count)
        self._tick += count * self._step
        return self._tick

    def stamp(self) -> str:
        return "T{:08d}".format(self._tick)
