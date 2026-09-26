"""Start conditions evaluated in order."""

from typing import Any, Dict, List

GATE_OIL_PRESSURE = "oil.pressure.established"
GATE_LATCH_CLEAR = "oil.latch.clear"
GATE_CRANK_COMPLETE = "crank.complete"

CRANK_GATES = (GATE_OIL_PRESSURE, GATE_LATCH_CLEAR)


def evaluate(pressure_bar: float, established_bar: float, latched: bool, cranked: bool) -> List[Dict[str, Any]]:
    return [
        {
            "gate": GATE_OIL_PRESSURE,
            "passed": pressure_bar >= established_bar,
            "detail": {"pressure_bar": pressure_bar, "required_bar": established_bar},
        },
        {"gate": GATE_LATCH_CLEAR, "passed": not latched, "detail": {"latched": latched}},
        {"gate": GATE_CRANK_COMPLETE, "passed": cranked, "detail": {"cranked": cranked}},
    ]


def blocker(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    for check in checks:
        if not check["passed"]:
            return check
    return {"gate": "", "passed": True, "detail": {}}


def crank_blocker(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The crank itself only waits on established pressure and a clear latch."""

    return blocker([check for check in checks if check["gate"] in CRANK_GATES])
