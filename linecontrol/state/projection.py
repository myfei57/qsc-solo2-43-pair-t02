"""Rebuild machine state from the committed part of the record stream."""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional

from ..rules.uniqueness import BatchRegistry
from ..store.kinds import (
    KIND_AVR_DEEXCITE,
    KIND_AVR_EXCITE,
    KIND_BREAKER_CLOSE,
    KIND_BREAKER_LATCH_RELEASE,
    KIND_BREAKER_OPEN,
    KIND_BREAKER_TRIP,
    KIND_ENGINE_START,
    KIND_ENGINE_STOP,
    KIND_GOV_ADJUST,
    KIND_LOAD_ADJUST,
    KIND_LUBE_LATCH_CLEAR,
    KIND_LUBE_LATCH_SET,
    KIND_LUBE_PRESSURE,
    KIND_SYNC_PERSIST,
)
from .events import alarm_key, is_alarm_clear, is_alarm_set


@dataclass
class MachineState:
    engine: str = "stopped"
    breaker: str = "open"
    lube_pressure_bar: float = 0.0
    lube_latched: bool = False
    breaker_latched: bool = False
    excitation_v: float = 0.0
    load_kw: float = 0.0
    target_hz: float = 50.0
    last_tick: int = 0
    records_applied: int = 0

    @property
    def online(self) -> bool:
        return self.engine == "running" and self.breaker == "closed"

    @classmethod
    def initial(cls) -> "MachineState":
        return cls()

    @classmethod
    def from_mapping(cls, mapping: Dict[str, Any]) -> "MachineState":
        base = cls.initial()
        for name in (
            "engine",
            "breaker",
            "lube_pressure_bar",
            "lube_latched",
            "breaker_latched",
            "excitation_v",
            "load_kw",
            "target_hz",
            "last_tick",
            "records_applied",
        ):
            if name in mapping:
                setattr(base, name, mapping[name])
        return base

    def describe(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "breaker": self.breaker,
            "lube_pressure_bar": self.lube_pressure_bar,
            "lube_latched": self.lube_latched,
            "breaker_latched": self.breaker_latched,
            "excitation_v": self.excitation_v,
            "load_kw": self.load_kw,
            "target_hz": self.target_hz,
            "last_tick": self.last_tick,
            "records_applied": self.records_applied,
            "online": self.online,
        }


@dataclass(frozen=True)
class AlarmRecord:
    alarm: str
    kind: str
    batch_id: str
    state: str
    tick: int
    record_id: str
    detail: Dict[str, Any] = field(default_factory=dict)

    def describe(self) -> Dict[str, Any]:
        return {
            "alarm": self.alarm,
            "kind": self.kind,
            "batch": self.batch_id,
            "state": self.state,
            "tick": self.tick,
            "record": self.record_id,
            "detail": dict(self.detail),
        }


class StateProjector:
    """Turns committed records into machine state, alarms and batch identity."""

    def __init__(self, log) -> None:
        self._log = log

    def visible_records(self, start_seq: int = 0) -> List:
        return [record for record in self._log.visible() if record.seq > start_seq]

    def replay(self, start_seq: int = 0, base: Optional[MachineState] = None) -> MachineState:
        state = base if base is not None else MachineState.initial()
        for record in self.visible_records(start_seq):
            state = self.apply(state, record)
        return state

    def apply(self, state: MachineState, record) -> MachineState:
        payload = record.payload
        working = replace(state)
        working.last_tick = max(working.last_tick, record.tick)
        working.records_applied += 1
        kind = record.kind
        if kind == KIND_ENGINE_START:
            working.engine = "running"
        elif kind == KIND_ENGINE_STOP:
            working.engine = "stopped"
        elif kind == KIND_LUBE_PRESSURE:
            working.lube_pressure_bar = float(payload.get("bar", 0.0))
        elif kind == KIND_LUBE_LATCH_SET:
            working.lube_latched = True
        elif kind == KIND_LUBE_LATCH_CLEAR:
            working.lube_latched = False
        elif kind == KIND_BREAKER_CLOSE:
            working.breaker = "closed"
        elif kind == KIND_BREAKER_OPEN:
            working.breaker = "open"
        elif kind == KIND_BREAKER_TRIP:
            working.breaker = "open"
            working.breaker_latched = True
        elif kind == KIND_BREAKER_LATCH_RELEASE:
            working.breaker_latched = False
        elif kind == KIND_AVR_EXCITE:
            working.excitation_v = float(payload.get("voltage", 0.0))
        elif kind == KIND_AVR_DEEXCITE:
            working.excitation_v = 0.0
        elif kind == KIND_LOAD_ADJUST:
            working.load_kw = float(payload.get("kw", 0.0))
        elif kind == KIND_GOV_ADJUST:
            working.target_hz = float(payload.get("target_hz", working.target_hz))
        return working

    def alarms(self) -> List[AlarmRecord]:
        collected: List[AlarmRecord] = []
        for record in self._log.visible():
            if is_alarm_set(record):
                collected.append(self._alarm(record, "set"))
            elif is_alarm_clear(record):
                collected.append(self._alarm(record, "cleared"))
        return collected

    def _alarm(self, record, state: str) -> AlarmRecord:
        return AlarmRecord(
            alarm=alarm_key(record),
            kind=record.kind,
            batch_id=record.batch_id,
            state=state,
            tick=record.tick,
            record_id=record.record_id,
            detail=dict(record.payload),
        )

    def current_alarms(self) -> List[AlarmRecord]:
        latest: Dict[str, AlarmRecord] = {}
        for entry in self.alarms():
            latest[entry.alarm] = entry
        return [entry for entry in latest.values() if entry.state == "set"]

    def batch_registry(self) -> BatchRegistry:
        registry = BatchRegistry()
        for record in self._log.visible():
            if record.kind == KIND_SYNC_PERSIST and record.batch_id:
                registry.register(record.batch_id, record.digest, record.tick, record.kind)
        return registry

    def kind_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for record in self._log.visible():
            counts[record.kind] = counts.get(record.kind, 0) + 1
        return dict(sorted(counts.items()))

    def report(self) -> Dict[str, Any]:
        return {
            "state": self.replay().describe(),
            "current_alarms": [item.describe() for item in self.current_alarms()],
            "alarm_history": len(self.alarms()),
            "kind_counts": self.kind_counts(),
            "batches": self.batch_registry().size(),
        }
