"""Units and display names."""

from .names import SUBSYSTEM_LABELS, label, subsystem_ids
from .units import (
    MAX_FREQUENCY_HZ,
    MIN_FREQUENCY_HZ,
    POLE_PAIRS,
    angle_delta_deg,
    bar_to_kpa,
    check_frequency_band,
    hz_to_rpm,
    kw_to_mw,
    normalize_angle_deg,
)

__all__ = [
    "MAX_FREQUENCY_HZ",
    "MIN_FREQUENCY_HZ",
    "POLE_PAIRS",
    "SUBSYSTEM_LABELS",
    "angle_delta_deg",
    "bar_to_kpa",
    "check_frequency_band",
    "hz_to_rpm",
    "kw_to_mw",
    "label",
    "normalize_angle_deg",
    "subsystem_ids",
]
