"""Excitation is applied to a running unit and removed after the breaker opens."""

from typing import Any, Dict

from ..ns.units import kw_to_mw
from ..runtime.errors import OutOfRange
from ..store.kinds import KIND_AVR_DEEXCITE, KIND_AVR_EXCITE
from .errors import ExcitationGateClosed, ExcitationOrderViolation


class ExcitationService:
    def __init__(self, log, clock, registry, view, engine_running, breaker_closed) -> None:
        self._log = log
        self._clock = clock
        self._registry = registry
        self._view = view
        self._engine_running = engine_running
        self._breaker_closed = breaker_closed

    def voltage(self) -> float:
        return self._view.excitation_v()

    def nominal_voltage(self) -> float:
        return self._registry.value("avr.excite_voltage_v")

    def excite(self, voltage: float = None) -> Dict[str, Any]:
        if not self._engine_running():
            raise ExcitationGateClosed("excitation needs a running prime mover")
        value = self.nominal_voltage() if voltage is None else float(voltage)
        if value <= 0 or value > 1200.0:
            raise OutOfRange("excitation voltage is outside the working band", voltage=value)
        record = self._log.append(
            KIND_AVR_EXCITE,
            generation=self._registry.combine(("avr.excite_voltage_v",)),
            payload={"voltage": round(value, 6)},
            tick=self._clock.tick,
        )
        self._log.commit(tick=self._clock.tick)
        return {"voltage": round(value, 6), "record": record.record_id}

    def deexcite(self) -> Dict[str, Any]:
        if self._breaker_closed():
            raise ExcitationOrderViolation("the breaker must open before excitation is removed")
        if self.voltage() <= 0:
            raise ExcitationOrderViolation("excitation is already removed")
        record = self._log.append(
            KIND_AVR_DEEXCITE,
            generation=self._registry.combine(("avr.excite_voltage_v",)),
            payload={"voltage": 0.0},
            tick=self._clock.tick,
        )
        self._log.commit(tick=self._clock.tick)
        return {"voltage": 0.0, "record": record.record_id}

    def status(self) -> Dict[str, Any]:
        return {
            "voltage": self.voltage(),
            "nominal_voltage": self.nominal_voltage(),
            "excited": self.voltage() > 0,
            "load_mw": kw_to_mw(self._view.load_kw()),
        }
