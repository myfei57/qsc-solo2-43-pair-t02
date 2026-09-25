"""Failure modes of the phase matching subsystem."""

from ..runtime.errors import ControlError, GenerationMismatch, ItemExpired, PreconditionMissing


class BaselineMissing(PreconditionMissing):
    code = "baseline_missing"


class BaselineExpired(ItemExpired):
    code = "baseline_expired"


class BaselineStale(GenerationMismatch):
    code = "baseline_stale"


class FrequencyOutOfWindow(ControlError):
    code = "frequency_out_of_window"


class PhaseOutOfWindow(ControlError):
    code = "phase_out_of_window"
