"""Frequency adjustment, gated on the closed breaker and a live confirmation."""

from typing import Any, Dict

from ..contracts import FREQUENCY_KEYS
from ..ns.units import hz_to_rpm
from ..rules.window import centered_window
from ..runtime.errors import OutOfRange
from ..store.kinds import KIND_GOV_ADJUST
from ..sync.service import FREQUENCY_SUBJECT
from .errors import GovernorGateClosed


class GovernorService:
    def __init__(self, log, clock, registry, view, tickets, breaker_closed) -> None:
        self._log = log
        self._clock = clock
        self._registry = registry
        self._view = view
        self._tickets = tickets
        self._breaker_closed = breaker_closed

    def target_hz(self) -> float:
        return self._view.target_hz()

    def generation(self) -> int:
        return self._registry.combine(FREQUENCY_KEYS)

    def window(self):
        return centered_window(self._registry.value("gov.target_hz"), self._registry.value("gov.freq_window_hz"))

    def adjust(self, target_hz: float, ticket_id: str) -> Dict[str, Any]:
        if not self._breaker_closed():
            raise GovernorGateClosed("the governor adjusts only after the breaker closes")
        self._tickets.consume(ticket_id, FREQUENCY_SUBJECT, self.generation(), self._clock.tick)
        window = self.window()
        if not window.contains(float(target_hz)):
            raise OutOfRange(
                "target frequency is outside the acceptance window",
                target_hz=float(target_hz),
                window=window.describe(),
            )
        record = self._log.append(
            KIND_GOV_ADJUST,
            generation=self.generation(),
            payload={"target_hz": round(float(target_hz), 6), "rpm": hz_to_rpm(float(target_hz))},
            tick=self._clock.tick,
        )
        self._log.commit(tick=self._clock.tick)
        return {
            "target_hz": round(float(target_hz), 6),
            "rpm": hz_to_rpm(float(target_hz)),
            "record": record.record_id,
        }

    def status(self) -> Dict[str, Any]:
        return {
            "target_hz": self.target_hz(),
            "rpm": hz_to_rpm(self.target_hz()),
            "window": self.window().describe(),
            "generation": self.generation(),
        }
