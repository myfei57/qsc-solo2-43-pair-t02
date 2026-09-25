"""Vocabulary for data records and log control records."""

from ..runtime.errors import ValidationError

KIND_SYNC_BASELINE = "sync.baseline"
KIND_SYNC_PERSIST = "sync.persist"
KIND_SYNC_COMMIT = "sync.commit"
KIND_ENGINE_START = "engine.start"
KIND_ENGINE_STOP = "engine.stop"
KIND_LUBE_PRESSURE = "lube.pressure"
KIND_LUBE_LATCH_SET = "lube.latch.set"
KIND_LUBE_LATCH_CLEAR = "lube.latch.clear"
KIND_BREAKER_CLOSE = "breaker.close"
KIND_BREAKER_OPEN = "breaker.open"
KIND_BREAKER_TRIP = "breaker.trip"
KIND_BREAKER_LATCH_RELEASE = "breaker.latch.release"
KIND_GOV_ADJUST = "gov.adjust"
KIND_LOAD_ADJUST = "load.adjust"
KIND_AVR_EXCITE = "avr.excite"
KIND_AVR_DEEXCITE = "avr.deexcite"
KIND_FUEL_DELIVER = "fuel.deliver"
KIND_CONFIG_PARAM = "config.param"
KIND_ALARM_SET = "alarm.set"
KIND_ALARM_CLEAR = "alarm.clear"
KIND_AUDIT = "audit.entry"

KIND_COMMIT = "commit"
KIND_ROLLBACK = "rollback"
KIND_TOMBSTONE = "tombstone"

CONTROL_KINDS = (KIND_COMMIT, KIND_ROLLBACK, KIND_TOMBSTONE)

DATA_KINDS = (
    KIND_SYNC_BASELINE,
    KIND_SYNC_PERSIST,
    KIND_SYNC_COMMIT,
    KIND_ENGINE_START,
    KIND_ENGINE_STOP,
    KIND_LUBE_PRESSURE,
    KIND_LUBE_LATCH_SET,
    KIND_LUBE_LATCH_CLEAR,
    KIND_BREAKER_CLOSE,
    KIND_BREAKER_OPEN,
    KIND_BREAKER_TRIP,
    KIND_BREAKER_LATCH_RELEASE,
    KIND_GOV_ADJUST,
    KIND_LOAD_ADJUST,
    KIND_AVR_EXCITE,
    KIND_AVR_DEEXCITE,
    KIND_FUEL_DELIVER,
    KIND_CONFIG_PARAM,
    KIND_ALARM_SET,
    KIND_ALARM_CLEAR,
    KIND_AUDIT,
)

def is_control(kind: str) -> bool:
    return kind in CONTROL_KINDS


def require_data_kind(kind: str) -> str:
    if kind not in DATA_KINDS:
        if kind in CONTROL_KINDS:
            raise ValidationError("control records cannot be appended directly", kind=kind)
        raise ValidationError("unknown record kind", kind=kind)
    return kind
