"""Error taxonomy shared by every subsystem."""

from typing import Any, Dict


class ControlError(Exception):
    """Base class for every domain failure surfaced through the API."""

    code = "control_error"
    status = 409

    def __init__(self, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.message = message
        self.detail: Dict[str, Any] = dict(detail)

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"error": self.code, "message": self.message}
        if self.detail:
            payload["detail"] = self.detail
        return payload


class ValidationError(ControlError):
    """Caller supplied a value that cannot be interpreted at all."""

    code = "validation_error"
    status = 422


class UnknownParameter(ValidationError):
    code = "unknown_parameter"


class OutOfRange(ValidationError):
    code = "out_of_range"


class OrderViolation(ControlError):
    """An operation was requested before its predecessor step completed."""

    code = "order_violation"


class NotPersisted(ControlError):
    """A predecessor result exists in memory but was never committed."""

    code = "not_persisted"


class InterlockLatched(ControlError):
    code = "interlock_latched"


class PreconditionMissing(ControlError):
    code = "precondition_missing"


class GenerationMismatch(ControlError):
    code = "generation_mismatch"


class ItemExpired(ControlError):
    code = "expired"


class DuplicateRejected(ControlError):
    code = "duplicate"


class UnknownItem(ControlError):
    code = "unknown_item"
    status = 404


class SnapshotInvalid(ControlError):
    code = "snapshot_invalid"
