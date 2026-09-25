"""Failure modes of the line breaker."""

from ..runtime.errors import ControlError, InterlockLatched


class BreakerLatched(InterlockLatched):
    code = "breaker_latched"


class ContactAngleOutOfRange(ControlError):
    code = "contact_angle_out_of_range"
