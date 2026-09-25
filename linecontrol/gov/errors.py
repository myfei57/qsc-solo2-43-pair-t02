"""Failure modes of the speed governor."""

from ..runtime.errors import OrderViolation


class GovernorGateClosed(OrderViolation):
    code = "governor_gate_closed"
