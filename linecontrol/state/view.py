"""A memoised read model over the committed record stream."""

from typing import Any, Dict, List

from .projection import MachineState, StateProjector


class MachineView:
    """Read only projection with a cache keyed on the log tail."""

    def __init__(self, log, projector: StateProjector) -> None:
        self._log = log
        self._projector = projector
        self._key = None
        self._state = None

    def state(self) -> MachineState:
        key = (self._log.watermark, self._log.max_seq(), len(self._log.records()))
        if self._key != key:
            self._state = self._projector.replay()
            self._key = key
        return self._state

    def invalidate(self) -> None:
        self._key = None
        self._state = None

    def engine(self) -> str:
        return self.state().engine

    def running(self) -> bool:
        return self.state().engine == "running"

    def breaker(self) -> str:
        return self.state().breaker

    def closed(self) -> bool:
        return self.state().breaker == "closed"

    def breaker_latched(self) -> bool:
        return self.state().breaker_latched

    def lube_latched(self) -> bool:
        return self.state().lube_latched

    def pressure_bar(self) -> float:
        return self.state().lube_pressure_bar

    def load_kw(self) -> float:
        return self.state().load_kw

    def target_hz(self) -> float:
        return self.state().target_hz

    def excitation_v(self) -> float:
        return self.state().excitation_v

    def online(self) -> bool:
        return self.state().online

    def alarms(self) -> List:
        return self._projector.current_alarms()

    def describe(self) -> Dict[str, Any]:
        payload = self.state().describe()
        payload["alarms"] = [item.describe() for item in self.alarms()]
        return payload
