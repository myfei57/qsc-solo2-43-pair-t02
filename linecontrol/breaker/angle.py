"""Contact angle helpers."""

from ..ns.units import angle_delta_deg


def contact_angle_deg(phase_deg: float, reference_deg: float) -> float:
    return angle_delta_deg(phase_deg, reference_deg)
