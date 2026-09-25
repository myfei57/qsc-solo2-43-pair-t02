"""Shared primitives: deterministic clock, identifiers, codecs and errors."""

from .clock import VirtualClock
from .codec import decode, digest, encode
from .errors import (
    ControlError,
    DuplicateRejected,
    GenerationMismatch,
    InterlockLatched,
    ItemExpired,
    NotPersisted,
    OrderViolation,
    OutOfRange,
    PreconditionMissing,
    SnapshotInvalid,
    UnknownItem,
    UnknownParameter,
    ValidationError,
)
from .ids import IdSequencer

__all__ = [
    "ControlError",
    "DuplicateRejected",
    "GenerationMismatch",
    "IdSequencer",
    "InterlockLatched",
    "ItemExpired",
    "NotPersisted",
    "OrderViolation",
    "OutOfRange",
    "PreconditionMissing",
    "SnapshotInvalid",
    "UnknownItem",
    "UnknownParameter",
    "ValidationError",
    "VirtualClock",
    "decode",
    "digest",
    "encode",
]
