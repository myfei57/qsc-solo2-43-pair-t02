"""Failure modes of the voltage regulator."""

from ..runtime.errors import OrderViolation, PreconditionMissing


class ExcitationGateClosed(PreconditionMissing):
    code = "excitation_gate_closed"


class ExcitationOrderViolation(OrderViolation):
    code = "excitation_order_violation"
