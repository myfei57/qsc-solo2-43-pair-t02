"""Unit conversions and physical bands for the electrical quantities."""

from ..runtime.errors import OutOfRange, ValidationError

POLE_PAIRS = 2
MIN_FREQUENCY_HZ = 40.0
MAX_FREQUENCY_HZ = 60.0


def hz_to_rpm(hz: float, pole_pairs: int = POLE_PAIRS) -> float:
    if pole_pairs <= 0:
        raise ValidationError("pole_pairs must be positive", pole_pairs=pole_pairs)
    return round(hz * 60.0 / pole_pairs, 3)


def kw_to_mw(kw: float) -> float:
    return round(kw / 1000.0, 6)


def bar_to_kpa(bar: float) -> float:
    return round(bar * 100.0, 3)


def normalize_angle_deg(angle: float) -> float:
    value = angle % 360.0
    if value > 180.0:
        value -= 360.0
    return round(value, 6)


def angle_delta_deg(left: float, right: float) -> float:
    return normalize_angle_deg(normalize_angle_deg(left) - normalize_angle_deg(right))


def check_frequency_band(hz: float) -> float:
    if hz < MIN_FREQUENCY_HZ or hz > MAX_FREQUENCY_HZ:
        raise OutOfRange(
            "frequency outside the supported band",
            hz=hz,
            low=MIN_FREQUENCY_HZ,
            high=MAX_FREQUENCY_HZ,
        )
    return hz
