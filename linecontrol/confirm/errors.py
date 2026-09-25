"""Failure modes for confirmation tickets."""

from ..runtime.errors import (
    ControlError,
    DuplicateRejected,
    GenerationMismatch,
    ItemExpired,
    UnknownItem,
    ValidationError,
)


class ConfirmError(ControlError):
    code = "confirm_error"


class UnknownTicket(UnknownItem):
    code = "unknown_ticket"


class TicketAlreadyUsed(DuplicateRejected):
    code = "ticket_already_used"


class TicketExpired(ItemExpired):
    code = "ticket_expired"


class TicketStale(GenerationMismatch):
    code = "ticket_stale"


class TicketSubjectMismatch(ConfirmError):
    code = "ticket_subject_mismatch"


class InvalidTicketRequest(ValidationError):
    code = "invalid_ticket_request"
