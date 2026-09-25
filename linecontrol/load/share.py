"""Deterministic load sharing between paralleled units."""

from typing import List

from ..runtime.errors import OutOfRange


def share_load(total_kw: float, units: int) -> List[float]:
    """Split a total evenly; the remainder goes to the first units in order."""

    if units <= 0:
        raise OutOfRange("unit count must be positive", units=units)
    if total_kw < 0:
        raise OutOfRange("shared load must not be negative", total_kw=total_kw)
    base = round(total_kw / units, 6)
    shares = [base for _ in range(units)]
    remainder = round(total_kw - base * units, 6)
    index = 0
    while remainder > 0 and index < units:
        step = min(0.001, remainder)
        shares[index] = round(shares[index] + step, 6)
        remainder = round(remainder - step, 6)
        index += 1
    return shares


def reverse_power_exceeded(load_kw: float, limit_kw: float) -> bool:
    return load_kw < -abs(limit_kw)
