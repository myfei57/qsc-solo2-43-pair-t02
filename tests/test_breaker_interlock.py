"""Interlocks: the breaker closes only on a committed, confirmed result."""

from linecontrol.breaker.errors import BreakerLatched, ContactAngleOutOfRange
from linecontrol.confirm import TicketAlreadyUsed, TicketExpired, UnknownTicket
from linecontrol.runtime.errors import NotPersisted, OrderViolation
from tests.helpers import HubTestCase


class BreakerInterlockCase(HubTestCase):
    def test_close_rejected_before_the_sync_result_is_persisted(self):
        self.prime_unit()
        self.hub.calibrate(0.0, 50.0)
        self.hub.persist_sync("B-1")
        ticket = self.close_ticket(50.02)
        with self.assertRaises(NotPersisted):
            self.hub.close_breaker("B-1", ticket, 1.0)

    def test_close_rejected_without_a_confirmation(self):
        self.prime_unit()
        self.persisted_sync("B-1")
        with self.assertRaises(UnknownTicket):
            self.hub.close_breaker("B-1", "TCK-000001", 1.0)

    def test_close_rejected_with_an_expired_confirmation(self):
        self.prime_unit()
        self.persisted_sync("B-1")
        ticket = self.close_ticket(50.02)
        self.advance(11)
        with self.assertRaises(TicketExpired):
            self.hub.close_breaker("B-1", ticket, 1.0)

    def test_close_rejected_while_the_trip_latch_is_engaged(self):
        self.prime_unit()
        self.persisted_sync("B-1")
        ticket = self.close_ticket(50.02)
        self.hub.trip_breaker("protection")
        with self.assertRaises(BreakerLatched):
            self.hub.close_breaker("B-1", ticket, 1.0)

    def test_close_rejected_when_the_phase_delta_leaves_the_window(self):
        self.prime_unit()
        self.persisted_sync("B-1")
        ticket = self.close_ticket(50.02)
        with self.assertRaises(ContactAngleOutOfRange):
            self.hub.close_breaker("B-1", ticket, 30.0)

    def test_close_succeeds_with_a_committed_result_and_a_live_confirmation(self):
        self.prime_unit()
        self.persisted_sync("B-1")
        ticket = self.close_ticket(50.02)
        result = self.hub.close_breaker("B-1", ticket, 1.0)
        self.assertEqual(result["breaker"], "closed")
        self.assertTrue(self.hub.view.closed())

    def test_close_rejected_when_the_breaker_is_already_closed(self):
        self.online()
        ticket = self.close_ticket(50.02)
        with self.assertRaises(OrderViolation):
            self.hub.close_breaker("B-1", ticket, 1.0)

    def test_each_confirmation_is_spent_once(self):
        self.prime_unit()
        self.persisted_sync("B-1")
        ticket = self.close_ticket(50.02)
        self.hub.close_breaker("B-1", ticket, 1.0)
        self.hub.open_breaker("reclose test")
        with self.assertRaises(TicketAlreadyUsed):
            self.hub.close_breaker("B-1", ticket, 1.0)

    def test_close_rejected_when_a_newer_batch_was_confirmed(self):
        self.prime_unit()
        self.hub.calibrate(0.0, 50.0)
        self.hub.persist_sync("B-1")
        self.hub.commit_sync("B-1")
        ticket = self.close_ticket(50.02)
        with self.assertRaises(NotPersisted):
            self.hub.close_breaker("B-2", ticket, 1.0)

    def test_open_rejected_when_the_breaker_is_already_open(self):
        with self.assertRaises(OrderViolation):
            self.hub.open_breaker("nothing to open")

    def test_trip_opens_and_latches_the_breaker(self):
        self.hub.trip_breaker("protection")
        self.assertFalse(self.hub.view.closed())
        self.assertTrue(self.hub.view.breaker_latched())

    def test_latch_release_rejected_while_load_is_held(self):
        self.online(load_kw=120.0)
        self.hub.trip_breaker("protection")
        with self.assertRaises(BreakerLatched):
            self.hub.release_breaker_latch()

    def test_latch_release_succeeds_with_an_open_breaker_and_no_load(self):
        self.online(load_kw=0.0)
        self.hub.trip_breaker("protection")
        self.hub.release_breaker_latch()
        self.assertFalse(self.hub.view.breaker_latched())

    def test_latch_release_rejected_when_no_latch_is_engaged(self):
        with self.assertRaises(BreakerLatched):
            self.hub.release_breaker_latch()
