"""State machine and interlock: the ordered start gate."""

from linecontrol.engine.errors import EngineGateClosed, EngineNotRunning
from linecontrol.runtime.errors import OrderViolation
from tests.helpers import HubTestCase


class EngineGateCase(HubTestCase):
    def test_crank_rejected_without_oil_pressure(self):
        with self.assertRaises(EngineGateClosed) as caught:
            self.hub.crank()
        self.assertEqual(caught.exception.detail["gate"], "oil.pressure.established")

    def test_crank_rejected_while_the_latch_is_engaged(self):
        self.hub.build_pressure(0.5)
        self.hub.build_pressure(2.6)
        with self.assertRaises(EngineGateClosed) as caught:
            self.hub.crank()
        self.assertEqual(caught.exception.detail["gate"], "oil.latch.clear")

    def test_crank_moves_the_unit_to_cranking(self):
        self.hub.build_pressure(2.6)
        self.hub.crank()
        self.assertEqual(self.hub.view.engine(), "cranking")

    def test_start_rejected_before_cranking(self):
        self.hub.build_pressure(2.6)
        with self.assertRaises(EngineGateClosed) as caught:
            self.hub.start_engine()
        self.assertEqual(caught.exception.detail["gate"], "crank.complete")

    def test_start_rejected_when_pressure_drops_below_the_build_level(self):
        self.hub.build_pressure(2.6)
        self.hub.crank()
        self.hub.build_pressure(2.0)
        with self.assertRaises(EngineGateClosed) as caught:
            self.hub.start_engine()
        self.assertEqual(caught.exception.detail["gate"], "oil.pressure.established")

    def test_start_moves_the_unit_to_running(self):
        self.hub.build_pressure(2.6)
        self.hub.crank()
        result = self.hub.start_engine()
        self.assertEqual(result["engine"], "running")
        self.assertEqual(self.hub.view.engine(), "running")

    def test_start_rejected_when_the_unit_is_already_running(self):
        self.prime_unit()
        with self.assertRaises(OrderViolation):
            self.hub.start_engine()

    def test_crank_rejected_when_the_unit_is_already_running(self):
        self.prime_unit()
        with self.assertRaises(OrderViolation):
            self.hub.crank()

    def test_stop_rejected_when_the_unit_is_not_running(self):
        with self.assertRaises(EngineNotRunning):
            self.hub.stop_engine()

    def test_stop_moves_the_unit_to_stopped(self):
        self.prime_unit()
        self.hub.stop_engine()
        self.assertEqual(self.hub.view.engine(), "stopped")

    def test_gate_report_lists_every_check(self):
        report = self.hub.engine.gate_report()
        self.assertEqual(len(report["checks"]), 3)
        self.assertFalse(report["open"])
        self.assertEqual(report["blocked_by"], "oil.pressure.established")
