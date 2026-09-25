"""Speed governor adjustment."""

from .errors import GovernorGateClosed
from .service import GovernorService

__all__ = ["GovernorGateClosed", "GovernorService"]
