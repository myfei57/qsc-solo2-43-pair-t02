"""Start conditions evaluated in order."""

from typing import Any, Dict, List


def evaluate(pressure_bar: float, established_bar: float, latched: bool) -> List[Dict[str, Any]]:
    return [
        {
            "gate": "oil.pressure.established",
            "passed": pressure_bar >= established_bar,
            "detail": {"pressure_bar": pressure_bar, "required_bar": established_bar},
        },
        {"gate": "oil.latch.clear", "passed": not latched, "detail": {"latched": latched}},
    ]


def blocker(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    for check in checks:
        if not check["passed"]:
            return check
    return {"gate": "", "passed": True, "detail": {}}
