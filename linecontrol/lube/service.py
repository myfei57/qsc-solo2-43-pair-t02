"""Oil pressure build up and the low pressure latch."""

from typing import Any, Dict, Optional

from ..runtime.errors import OutOfRange
from ..store.kinds import KIND_LUBE_LATCH_CLEAR, KIND_LUBE_LATCH_SET, KIND_LUBE_PRESSURE
from ..ns.units import bar_to_kpa
from .errors import LatchStillEngaged
from .latch import PressureLatch

MAX_PRESSURE_BAR = 12.0
ALARM_NAME = "lube.low_pressure"


class LubeService:
    def __init__(self, log, clock, registry, view) -> None:
        self._log = log
        self._clock = clock
        self._registry = registry
        self._view = view
        self._ack_tick: Optional[int] = None

    def low_threshold(self) -> float:
        return self._registry.value("lube.low_pressure_bar")

    def established_threshold(self) -> float:
        return self._registry.value("lube.established_pressure_bar")

    def latch(self) -> PressureLatch:
        return PressureLatch(self.low_threshold(), self._registry.value("lube.latch_clear_margin_bar"))

    def pressure_bar(self) -> float:
        return self._view.pressure_bar()

    def latch_engaged(self) -> bool:
        return self._view.lube_latched()

    def acknowledged(self) -> bool:
        return self._ack_tick is not None

    def established(self) -> bool:
        return self.pressure_bar() >= self.established_threshold()

    def build_pressure(self, pressure_bar: float) -> Dict[str, Any]:
        value = float(pressure_bar)
        if value < 0 or value > MAX_PRESSURE_BAR:
            raise OutOfRange(
                "pressure is outside the measurable band",
                pressure_bar=value,
                low=0.0,
                high=MAX_PRESSURE_BAR,
            )
        record = self._log.append(
            KIND_LUBE_PRESSURE,
            generation=self._registry.combine(("lube.low_pressure_bar",)),
            payload={"bar": round(value, 6)},
            tick=self._clock.tick,
        )
        result: Dict[str, Any] = {
            "pressure_bar": round(value, 6),
            "kpa": bar_to_kpa(value),
            "record": record.record_id,
            "latch": "clear",
        }
        if self.latch().should_engage(value) and not self.latch_engaged():
            self._log.append(
                KIND_LUBE_LATCH_SET,
                generation=self._registry.combine(("lube.low_pressure_bar",)),
                payload={"alarm": ALARM_NAME, "bar": round(value, 6)},
                tick=self._clock.tick,
            )
            self._ack_tick = None
            result["latch"] = "engaged"
        elif self.latch_engaged():
            result["latch"] = "engaged"
        self._log.commit(tick=self._clock.tick)
        return result

    def acknowledge(self) -> Dict[str, Any]:
        self._ack_tick = self._clock.tick
        return {"acknowledged_tick": self._ack_tick, "pressure_bar": self.pressure_bar()}

    def clear_latch(self) -> Dict[str, Any]:
        if not self.latch_engaged():
            raise LatchStillEngaged("no oil pressure latch is engaged")
        decision = self.latch().decide(self.pressure_bar(), True, self.acknowledged())
        if not decision.clearable:
            raise LatchStillEngaged(decision.reason, pressure_bar=self.pressure_bar())
        record = self._log.append(
            KIND_LUBE_LATCH_CLEAR,
            generation=self._registry.combine(("lube.low_pressure_bar",)),
            payload={"alarm": ALARM_NAME, "bar": self.pressure_bar()},
            tick=self._clock.tick,
        )
        self._log.commit(tick=self._clock.tick)
        self._ack_tick = None
        return {"latch": "clear", "record": record.record_id}

    def status(self) -> Dict[str, Any]:
        latch = self.latch()
        return {
            "pressure_bar": self.pressure_bar(),
            "kpa": bar_to_kpa(self.pressure_bar()),
            "low_threshold_bar": latch.low_bar,
            "clear_level_bar": latch.clear_level_bar,
            "established_threshold_bar": self.established_threshold(),
            "established": self.established(),
            "latched": self.latch_engaged(),
            "acknowledged": self.acknowledged(),
            "decision": latch.decide(self.pressure_bar(), self.latch_engaged(), self.acknowledged()).describe(),
        }
