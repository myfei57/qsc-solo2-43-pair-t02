"""Failure modes of the prime mover."""

from ..runtime.errors import OrderViolation, PreconditionMissing


class EngineGateClosed(PreconditionMissing):
    code = "engine_gate_closed"


class EngineNotRunning(OrderViolation):
    code = "engine_not_running"
