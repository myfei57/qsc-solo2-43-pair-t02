"""Single use, generation bound confirmations."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..runtime.ids import IdSequencer
from .errors import (
    InvalidTicketRequest,
    TicketAlreadyUsed,
    TicketExpired,
    TicketStale,
    TicketSubjectMismatch,
    UnknownTicket,
)


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    subject: str
    generation: int
    issued_tick: int
    expires_tick: int
    context: Dict[str, Any] = field(default_factory=dict)
    consumed_tick: Optional[int] = None

    @property
    def consumed(self) -> bool:
        return self.consumed_tick is not None

    def is_expired(self, now: int) -> bool:
        return now > self.expires_tick

    def describe(self) -> Dict[str, Any]:
        return {
            "ticket": self.ticket_id,
            "subject": self.subject,
            "generation": self.generation,
            "issued_tick": self.issued_tick,
            "expires_tick": self.expires_tick,
            "consumed_tick": self.consumed_tick,
            "context": dict(self.context),
        }


class TicketRegistry:
    """Confirmations expire on the tick clock and never survive a generation bump."""

    def __init__(self, ids: IdSequencer, prefix: str = "TCK") -> None:
        self._ids = ids
        self._prefix = prefix
        self._tickets: Dict[str, Ticket] = {}
        self._consumed: Dict[str, int] = {}

    def issue(
        self,
        subject: str,
        generation: int,
        ttl_ticks: int,
        context: Dict[str, Any],
        now: int,
    ) -> Ticket:
        if not subject:
            raise InvalidTicketRequest("ticket subject must not be empty")
        if ttl_ticks <= 0:
            raise InvalidTicketRequest("ticket lifetime must be positive", ttl=ttl_ticks)
        if generation < 0:
            raise InvalidTicketRequest("ticket generation must not be negative", generation=generation)
        ticket = Ticket(
            ticket_id=self._ids.next(self._prefix),
            subject=subject,
            generation=int(generation),
            issued_tick=int(now),
            expires_tick=int(now) + int(ttl_ticks),
            context=dict(context),
        )
        self._tickets[ticket.ticket_id] = ticket
        return ticket

    def peek(self, ticket_id: str) -> Ticket:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            raise UnknownTicket("no such confirmation", ticket=ticket_id)
        consumed = self._consumed.get(ticket_id)
        if consumed is not None:
            return Ticket(
                ticket_id=ticket.ticket_id,
                subject=ticket.subject,
                generation=ticket.generation,
                issued_tick=ticket.issued_tick,
                expires_tick=ticket.expires_tick,
                context=dict(ticket.context),
                consumed_tick=consumed,
            )
        return ticket

    def consume(self, ticket_id: str, subject: str, generation: int, now: int) -> Ticket:
        ticket = self.peek(ticket_id)
        if ticket.consumed:
            raise TicketAlreadyUsed(
                "confirmation was already spent", ticket=ticket_id, consumed_tick=ticket.consumed_tick
            )
        if ticket.is_expired(now):
            raise TicketExpired(
                "confirmation has expired", ticket=ticket_id, expires_tick=ticket.expires_tick, now=now
            )
        if ticket.subject != subject:
            raise TicketSubjectMismatch(
                "confirmation was issued for another action",
                ticket=ticket_id,
                expected=ticket.subject,
                observed=subject,
            )
        if ticket.generation != generation:
            raise TicketStale(
                "confirmation belongs to an earlier parameter generation",
                ticket=ticket_id,
                expected=ticket.generation,
                observed=generation,
            )
        self._consumed[ticket_id] = int(now)
        return self.peek(ticket_id)

    def tickets(self) -> List[Ticket]:
        return [self.peek(ticket_id) for ticket_id in sorted(self._tickets)]

    def pending(self, now: int) -> List[Ticket]:
        return [item for item in self.tickets() if not item.consumed and not item.is_expired(now)]

    def expired(self, now: int) -> List[Ticket]:
        return [item for item in self.tickets() if not item.consumed and item.is_expired(now)]

    def issued_count(self, subject: str = "") -> int:
        if not subject:
            return len(self._tickets)
        return sum(1 for item in self.tickets() if item.subject == subject)

    def summary(self, now: int) -> Dict[str, Any]:
        return {
            "issued": len(self._tickets),
            "consumed": len(self._consumed),
            "pending": len(self.pending(now)),
            "expired": len(self.expired(now)),
        }
