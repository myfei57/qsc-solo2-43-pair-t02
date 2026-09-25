"""Which record kinds raise or clear an alarm."""

from typing import Any, Dict

from ..store.kinds import (
    KIND_ALARM_CLEAR,
    KIND_ALARM_SET,
    KIND_BREAKER_LATCH_RELEASE,
    KIND_BREAKER_TRIP,
    KIND_LUBE_LATCH_CLEAR,
    KIND_LUBE_LATCH_SET,
)

ALARM_SET_KINDS = (KIND_LUBE_LATCH_SET, KIND_BREAKER_TRIP, KIND_ALARM_SET)
ALARM_CLEAR_KINDS = (KIND_LUBE_LATCH_CLEAR, KIND_BREAKER_LATCH_RELEASE, KIND_ALARM_CLEAR)


def alarm_key(record) -> str:
    """Alarms are identified by an explicit name, falling back to the record kind."""

    payload: Dict[str, Any] = record.payload or {}
    name = payload.get("alarm")
    if name:
        return str(name)
    return str(record.kind)


def is_alarm_set(record) -> bool:
    return record.kind in ALARM_SET_KINDS


def is_alarm_clear(record) -> bool:
    return record.kind in ALARM_CLEAR_KINDS
