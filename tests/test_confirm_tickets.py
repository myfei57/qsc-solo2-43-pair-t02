"""Version semantics: confirmations expire and never outlive their generation."""

import unittest

from linecontrol.confirm import (
    InvalidTicketRequest,
    TicketAlreadyUsed,
    TicketExpired,
    TicketRegistry,
    TicketStale,
    TicketSubjectMismatch,
    UnknownTicket,
)
from linecontrol.runtime.ids import IdSequencer


class TicketRegistryCase(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = TicketRegistry(IdSequencer())

    def issue(self, subject="breaker.close", generation=1, ttl=5, now=0, context=None):
        return self.registry.issue(subject, generation, ttl, context or {}, now)

    def test_issued_ticket_is_pending_and_unconsumed(self):
        ticket = self.issue()
        self.assertFalse(ticket.consumed)
        self.assertEqual(len(self.registry.pending(0)), 1)

    def test_consumed_ticket_cannot_be_used_twice(self):
        ticket = self.issue()
        self.registry.consume(ticket.ticket_id, "breaker.close", 1, 1)
        with self.assertRaises(TicketAlreadyUsed):
            self.registry.consume(ticket.ticket_id, "breaker.close", 1, 2)

    def test_expired_ticket_is_rejected(self):
        ticket = self.issue(ttl=2)
        with self.assertRaises(TicketExpired):
            self.registry.consume(ticket.ticket_id, "breaker.close", 1, 3)

    def test_ticket_bound_to_an_earlier_generation_is_rejected(self):
        ticket = self.issue(generation=1)
        with self.assertRaises(TicketStale):
            self.registry.consume(ticket.ticket_id, "breaker.close", 2, 1)

    def test_ticket_issued_for_another_subject_is_rejected(self):
        ticket = self.issue(subject="gov.frequency")
        with self.assertRaises(TicketSubjectMismatch):
            self.registry.consume(ticket.ticket_id, "breaker.close", 1, 1)

    def test_unknown_ticket_is_rejected(self):
        with self.assertRaises(UnknownTicket):
            self.registry.consume("TCK-000404", "breaker.close", 1, 1)

    def test_non_positive_lifetime_is_rejected(self):
        with self.assertRaises(InvalidTicketRequest):
            self.issue(ttl=0)

    def test_empty_subject_is_rejected(self):
        with self.assertRaises(InvalidTicketRequest):
            self.issue(subject="")

    def test_pending_and_expired_views_are_disjoint(self):
        self.issue(ttl=1)
        self.issue(ttl=50)
        pending = {item.ticket_id for item in self.registry.pending(5)}
        expired = {item.ticket_id for item in self.registry.expired(5)}
        self.assertEqual(len(pending), 1)
        self.assertEqual(len(expired), 1)
        self.assertEqual(pending & expired, set())

    def test_summary_counts_issue_consume_and_expire(self):
        live = self.issue(ttl=9)
        self.issue(ttl=1)
        self.registry.consume(live.ticket_id, "breaker.close", 1, 1)
        summary = self.registry.summary(5)
        self.assertEqual(summary["issued"], 2)
        self.assertEqual(summary["consumed"], 1)
        self.assertEqual(summary["expired"], 1)
        self.assertEqual(summary["pending"], 0)

    def test_peek_reports_the_consumption_tick(self):
        ticket = self.issue()
        self.registry.consume(ticket.ticket_id, "breaker.close", 1, 4)
        self.assertEqual(self.registry.peek(ticket.ticket_id).consumed_tick, 4)

    def test_context_is_copied_not_shared(self):
        context = {"delta_hz": 0.01}
        ticket = self.issue(context=context)
        context["delta_hz"] = 99.0
        self.assertEqual(ticket.context["delta_hz"], 0.01)

    def test_issued_count_can_be_scoped_to_a_subject(self):
        self.issue(subject="a")
        self.issue(subject="b")
        self.issue(subject="b")
        self.assertEqual(self.registry.issued_count(), 3)
        self.assertEqual(self.registry.issued_count("b"), 2)
