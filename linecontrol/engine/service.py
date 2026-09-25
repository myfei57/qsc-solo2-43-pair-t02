"""Cranking and starting under the oil pressure gate."""

from typing import Any, Dict, List

from ..ns.units import hz_to_rpm
from ..runtime.errors import OrderViolation
from ..store.kinds import KIND_ENGINE_START, KIND_ENGINE_STOP
from .errors import EngineGateClosed, EngineNotRunning
from .gate import blocker, evaluate


class EngineService:
    def __init__(self, log, clock, registry, view, lube) -> None:
        self._log = log
        self._clock = clock
        self._registry = registry
        self._view = view
        self._lube = lube

    def state(self) -> str:
        return self._view.engine()

    def running(self) -> bool:
        return self.state() == "running"

    def checks(self) -> List[Dict[str, Any]]:
        return evaluate(
            pressure_bar=self._lube.pressure_bar(),
            established_bar=self._lube.established_threshold(),
            latched=self._lube.latch_engaged(),
        )

    def gate_report(self) -> Dict[str, Any]:
        checks = self.checks()
        stopped = blocker(checks)
        return {"checks": checks, "open": stopped["passed"], "blocked_by": stopped["gate"]}

    def crank(self) -> Dict[str, Any]:
        if self.running():
            raise OrderViolation("prime mover is already running")
        return {"engine": self.state()}

    def start(self) -> Dict[str, Any]:
        if self.running():
            raise OrderViolation("prime mover is already running")
        stopped = blocker(self.checks())
        if not stopped["passed"]:
            raise EngineGateClosed(stopped["gate"], gate=stopped["gate"], detail=stopped["detail"])
        rpm = hz_to_rpm(self._registry.value("gov.target_hz"))
        record = self._log.append(
            KIND_ENGINE_START,
            generation=self._registry.combine(("lube.established_pressure_bar", "gov.target_hz")),
            payload={"pressure_bar": self._lube.pressure_bar(), "rpm": rpm},
            tick=self._clock.tick,
        )
        self._log.commit(tick=self._clock.tick)
        return {"engine": "running", "rpm": rpm, "record": record.record_id}

    def stop(self) -> Dict[str, Any]:
        if not self.running():
            raise EngineNotRunning("prime mover is not running")
        record = self._log.append(
            KIND_ENGINE_STOP,
            generation=0,
            payload={"tick": self._clock.tick},
            tick=self._clock.tick,
        )
        self._log.commit(tick=self._clock.tick)
        return {"engine": "stopped", "record": record.record_id}

    def status(self) -> Dict[str, Any]:
        rpm = hz_to_rpm(self._registry.value("gov.target_hz"))
        return {
            "engine": self.state(),
            "running": self.running(),
            "target_rpm": rpm,
            "gate": self.gate_report(),
        }
