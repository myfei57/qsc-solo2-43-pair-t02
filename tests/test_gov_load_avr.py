"""Ordering and limits for the governor, the load controller and the exciter."""

from linecontrol.avr.errors import ExcitationGateClosed, ExcitationOrderViolation
from linecontrol.confirm import TicketAlreadyUsed
from linecontrol.gov.errors import GovernorGateClosed
from linecontrol.load.errors import LoadGateClosed, LoadOverCapacity, ReversePowerDetected
from linecontrol.runtime.errors import OutOfRange, ValidationError
from tests.helpers import HubTestCase


class GovernorCase(HubTestCase):
    def test_governor_rejected_before_the_breaker_closes(self):
        self.prime_unit()
        self.persisted_sync("B-1")
        ticket = self.close_ticket(50.02)
        with self.assertRaises(GovernorGateClosed):
            self.hub.adjust_governor(50.05, ticket)

    def test_governor_adjust_requires_a_fresh_confirmation(self):
        self.online()
        first = self.close_ticket(50.02)
        self.hub.adjust_governor(50.05, first)
        with self.assertRaises(TicketAlreadyUsed):
            self.hub.adjust_governor(50.06, first)

    def test_governor_target_outside_the_window_is_rejected(self):
        self.online()
        ticket = self.close_ticket(50.02)
        with self.assertRaises(OutOfRange):
            self.hub.adjust_governor(55.0, ticket)

    def test_governor_adjust_sets_the_target(self):
        self.online()
        ticket = self.close_ticket(50.02)
        result = self.hub.adjust_governor(50.05, ticket)
        self.assertAlmostEqual(result["target_hz"], 50.05)
        self.assertAlmostEqual(self.hub.view.target_hz(), 50.05)

    def test_governor_status_reports_the_window(self):
        self.online()
        status = self.hub.gov.status()
        self.assertAlmostEqual(status["window"]["low"], 49.85)
        self.assertAlmostEqual(status["window"]["high"], 50.15)


class LoadCase(HubTestCase):
    def test_load_rejected_before_the_breaker_closes(self):
        with self.assertRaises(LoadGateClosed):
            self.hub.adjust_load(10.0)

    def test_load_over_the_unit_capacity_is_rejected(self):
        self.online()
        with self.assertRaises(LoadOverCapacity):
            self.hub.adjust_load(500.0)

    def test_reverse_power_raises_and_records_an_alarm(self):
        self.online()
        with self.assertRaises(ReversePowerDetected):
            self.hub.adjust_load(-40.0)
        alarms = [item.alarm for item in self.hub.view.alarms()]
        self.assertIn("load.reverse_power", alarms)

    def test_reverse_power_alarm_survives_as_history(self):
        self.online()
        with self.assertRaises(ReversePowerDetected):
            self.hub.adjust_load(-40.0)
        self.assertEqual(len(self.hub.projector.alarms()), 1)

    def test_share_distributes_the_total_evenly(self):
        result = self.hub.share_load(300.0, 3)
        self.assertEqual(result["shares"], [100.0, 100.0, 100.0])

    def test_share_rejected_when_a_share_exceeds_the_capacity(self):
        with self.assertRaises(LoadOverCapacity):
            self.hub.share_load(1500.0, 3)

    def test_share_rejected_without_units(self):
        with self.assertRaises(ValidationError):
            self.hub.share_load(100.0, 0)

    def test_load_status_reports_headroom(self):
        self.online(load_kw=150.0)
        self.assertAlmostEqual(self.hub.load.status()["headroom_kw"], 250.0)


class ExcitationCase(HubTestCase):
    def test_excite_rejected_when_the_prime_mover_is_stopped(self):
        with self.assertRaises(ExcitationGateClosed):
            self.hub.excite()

    def test_excite_rejected_when_voltage_is_out_of_band(self):
        self.prime_unit()
        with self.assertRaises(OutOfRange):
            self.hub.excite(9000.0)

    def test_deexcite_rejected_while_the_breaker_is_closed(self):
        self.online()
        self.hub.excite()
        with self.assertRaises(ExcitationOrderViolation):
            self.hub.deexcite()

    def test_deexcite_succeeds_after_the_breaker_opens(self):
        self.online()
        self.hub.excite()
        self.hub.open_breaker("planned stop")
        self.hub.deexcite()
        self.assertEqual(self.hub.view.excitation_v(), 0.0)

    def test_deexcite_rejected_when_excitation_is_already_removed(self):
        self.prime_unit()
        with self.assertRaises(ExcitationOrderViolation):
            self.hub.deexcite()

    def test_excitation_status_reports_the_nominal_voltage(self):
        self.prime_unit()
        self.hub.excite()
        status = self.hub.avr.status()
        self.assertTrue(status["excited"])
        self.assertEqual(status["nominal_voltage"], 400.0)
