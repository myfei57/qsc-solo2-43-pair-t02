"""Display names for subsystems and machine states."""

from ..runtime.errors import UnknownItem

SUBSYSTEM_LABELS = {
    "engine": "prime mover",
    "lube": "oil circulation",
    "breaker": "line breaker",
    "sync": "phase matching",
    "gov": "speed governor",
    "load": "load controller",
    "avr": "voltage regulator",
    "fuel": "fuel supply",
    "store": "record store",
    "audit": "audit trail",
}

def subsystem_ids() -> list:
    return sorted(SUBSYSTEM_LABELS)


def label(subsystem: str) -> str:
    try:
        return SUBSYSTEM_LABELS[subsystem]
    except KeyError as exc:
        raise UnknownItem("unknown subsystem", subsystem=subsystem) from exc
