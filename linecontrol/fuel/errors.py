"""Failure modes of the fuel supply."""

from ..runtime.errors import OutOfRange


class TankOverflow(OutOfRange):
    code = "tank_overflow"
