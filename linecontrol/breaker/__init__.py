"""Line breaker close, open and trip latch."""

from .angle import contact_angle_deg
from .errors import BreakerLatched, ContactAngleOutOfRange
from .latch import LatchReleasePolicy
from .service import BreakerService

__all__ = [
    "BreakerLatched",
    "BreakerService",
    "ContactAngleOutOfRange",
    "LatchReleasePolicy",
    "contact_angle_deg",
]
