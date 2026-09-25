"""Deterministic identifier sequences for records, tickets and batches."""

from typing import Dict

from .errors import ValidationError


class IdSequencer:
    """Produces stable identifiers from a per-prefix counter."""

    def __init__(self, width: int = 6) -> None:
        if width < 3:
            raise ValidationError("width must be at least 3", width=width)
        self._width = int(width)
        self._counters: Dict[str, int] = {}

    @property
    def width(self) -> int:
        return self._width

    def next(self, prefix: str) -> str:
        if not prefix:
            raise ValidationError("prefix must not be empty")
        value = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = value
        return "{}-{:0{width}d}".format(prefix, value, width=self._width)

    def seed(self, prefix: str, value: int) -> None:
        current = self._counters.get(prefix, 0)
        if value > current:
            self._counters[prefix] = int(value)

    def counters(self) -> Dict[str, int]:
        return dict(sorted(self._counters.items()))
