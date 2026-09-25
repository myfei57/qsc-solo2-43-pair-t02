"""Failure modes of the load controller."""

from ..runtime.errors import ControlError, OrderViolation, OutOfRange


class LoadGateClosed(OrderViolation):
    code = "load_gate_closed"


class LoadOverCapacity(OutOfRange):
    code = "load_over_capacity"


class ReversePowerDetected(ControlError):
    code = "reverse_power_detected"
