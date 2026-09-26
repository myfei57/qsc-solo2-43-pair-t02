"""Start conditions evaluated in order.

The gates mirror the ordered start sequence: first the oil pressure must be
built up, then the low pressure latch must be clear, then the unit must have
been barred over (cranked) within the crank window. Only once every gate is
open may the prime mover be released to running speed.
"""

from typing import Any, Dict, List, Optional


def pressure_checks(pressure_bar: float, established_bar: float, latched: bool) -> List[Dict[str, Any]]:
    """The gates shared by cranking and starting."""

    return [
        {
            "gate": "oil.pressure.established",
            "passed": pressure_bar >= established_bar,
            "detail": {"pressure_bar": pressure_bar, "required_bar": established_bar},
        },
        {"gate": "oil.latch.clear", "passed": not latched, "detail": {"latched": latched}},
    ]


def crank_check(
    cranked: bool,
    tick: int,
    crank_tick: Optional[int],
    window_ticks: int,
    pressure_bar: float,
    crank_pressure_bar: Optional[float],
    established_bar: float,
) -> Dict[str, Any]:
    """Cranking must have happened, stay inside its window and hold pressure."""

    window_age = None if crank_tick is None else tick - crank_tick
    pressure_held = (
        crank_pressure_bar is not None
        and crank_pressure_bar >= established_bar
        and pressure_bar >= established_bar
    )
    fresh = crank_tick is not None and 0 <= (tick - crank_tick) <= window_ticks
    passed = cranked and fresh and pressure_held
    return {
        "gate": "crank.complete",
        "passed": passed,
        "detail": {
            "cranked": cranked,
            "crank_tick": crank_tick,
            "tick": tick,
            "window_ticks": window_ticks,
            "age_ticks": window_age,
            "pressure_bar": pressure_bar,
            "crank_pressure_bar": crank_pressure_bar,
            "required_bar": established_bar,
        },
    }


def evaluate(
    pressure_bar: float,
    established_bar: float,
    latched: bool,
    cranked: bool = False,
    tick: int = 0,
    crank_tick: Optional[int] = None,
    window_ticks: int = 0,
    crank_pressure_bar: Optional[float] = None,
) -> List[Dict[str, Any]]:
    checks = pressure_checks(pressure_bar, established_bar, latched)
    checks.append(
        crank_check(
            cranked=cranked,
            tick=tick,
            crank_tick=crank_tick,
            window_ticks=window_ticks,
            pressure_bar=pressure_bar,
            crank_pressure_bar=crank_pressure_bar,
            established_bar=established_bar,
        )
    )
    return checks


def blocker(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    for check in checks:
        if not check["passed"]:
            return check
    return {"gate": "", "passed": True, "detail": {}}
