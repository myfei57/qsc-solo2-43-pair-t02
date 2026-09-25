"""Plain in memory counters with a stable snapshot shape."""

from typing import Any, Dict

from ..runtime.errors import ValidationError


class MetricRegistry:
    def __init__(self) -> None:
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}

    def incr(self, name: str, amount: float = 1) -> float:
        if not name:
            raise ValidationError("metric name must not be empty")
        self._counters[name] = self._counters.get(name, 0.0) + float(amount)
        return self._counters[name]

    def gauge(self, name: str, value: float) -> float:
        if not name:
            raise ValidationError("metric name must not be empty")
        self._gauges[name] = float(value)
        return self._gauges[name]

    def counter(self, name: str) -> float:
        return self._counters.get(name, 0.0)

    def counters(self) -> Dict[str, float]:
        return {key: self._counters[key] for key in sorted(self._counters)}

    def gauges(self) -> Dict[str, float]:
        return {key: self._gauges[key] for key in sorted(self._gauges)}

    def summary(self) -> Dict[str, Any]:
        return {"counters": self.counters(), "gauges": self.gauges()}

    def reset(self) -> None:
        self._counters.clear()
        self._gauges.clear()
