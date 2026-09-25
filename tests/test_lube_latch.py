"""State machine and interlock: the oil pressure latch."""

from linecontrol.lube.errors import LatchStillEngaged
from linecontrol.runtime.errors import OutOfRange
from tests.helpers import HubTestCase


class LubeLatchCase(HubTestCase):
    def test_pressure_below_the_low_level_engages_the_latch(self):
        self.hub.build_pressure(0.5)
        self.assertTrue(self.hub.view.lube_latched())
        alarms = [item.alarm for item in self.hub.view.alarms()]
        self.assertIn("lube.low_pressure", alarms)

    def test_pressure_above_the_low_level_leaves_the_latch_clear(self):
        self.hub.build_pressure(2.6)
        self.assertFalse(self.hub.view.lube_latched())
        self.assertEqual(self.hub.view.alarms(), [])

    def test_latch_clear_without_acknowledgement_is_rejected(self):
        self.hub.build_pressure(0.5)
        with self.assertRaises(LatchStillEngaged):
            self.hub.clear_lube_latch()

    def test_latch_clear_without_pressure_recovery_is_rejected(self):
        self.hub.build_pressure(0.5)
        self.hub.acknowledge_lube()
        with self.assertRaises(LatchStillEngaged):
            self.hub.clear_lube_latch()

    def test_latch_clears_after_acknowledgement_and_recovery(self):
        self.hub.build_pressure(0.5)
        self.hub.build_pressure(2.6)
        self.hub.acknowledge_lube()
        self.hub.clear_lube_latch()
        self.assertFalse(self.hub.view.lube_latched())
        self.assertEqual(self.hub.view.alarms(), [])

    def test_latch_clear_without_an_engaged_latch_is_rejected(self):
        with self.assertRaises(LatchStillEngaged):
            self.hub.clear_lube_latch()

    def test_pressure_outside_the_measurable_band_is_rejected(self):
        with self.assertRaises(OutOfRange):
            self.hub.build_pressure(20.0)
        with self.assertRaises(OutOfRange):
            self.hub.build_pressure(-1.0)

    def test_established_flag_follows_the_build_level(self):
        self.hub.build_pressure(2.0)
        self.assertFalse(self.hub.lube.established())
        self.hub.build_pressure(2.6)
        self.assertTrue(self.hub.lube.established())

    def test_status_reports_the_clear_level_and_conversion(self):
        self.hub.build_pressure(2.6)
        status = self.hub.lube.status()
        self.assertEqual(status["clear_level_bar"], 1.5)
        self.assertEqual(status["kpa"], 260.0)
        self.assertTrue(status["established"])

    def test_acknowledgement_is_not_persisted(self):
        self.hub.build_pressure(0.5)
        self.hub.acknowledge_lube()
        self.assertTrue(self.hub.lube.acknowledged())
        restarted = self.reopen()
        restarted.restore()
        self.assertFalse(restarted.lube.acknowledged())
