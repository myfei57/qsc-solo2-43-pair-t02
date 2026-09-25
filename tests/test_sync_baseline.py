"""Version semantics and windows: the calibration baseline."""

from linecontrol.runtime.errors import DuplicateRejected, OutOfRange
from linecontrol.sync.errors import (
    BaselineExpired,
    BaselineMissing,
    BaselineStale,
    FrequencyOutOfWindow,
    PhaseOutOfWindow,
)
from tests.helpers import HubTestCase


class SyncBaselineCase(HubTestCase):
    def test_baseline_missing_when_nothing_was_recorded(self):
        with self.assertRaises(BaselineMissing):
            self.hub.persist_sync("B-1")

    def test_baseline_expires_after_its_lifetime(self):
        self.hub.calibrate(0.0, 50.0, ttl_ticks=2)
        self.advance(4)
        with self.assertRaises(BaselineExpired):
            self.hub.sync.require_baseline()

    def test_expired_baseline_is_rejected_on_persist(self):
        self.hub.calibrate(0.0, 50.0, ttl_ticks=1)
        self.advance(3)
        with self.assertRaises(BaselineExpired):
            self.hub.persist_sync("B-1")

    def test_baseline_becomes_stale_after_a_parameter_change(self):
        self.hub.calibrate(0.0, 50.0)
        self.hub.set_parameter("sync.freq_window_hz", 0.2)
        with self.assertRaises(BaselineStale):
            self.hub.persist_sync("B-1")

    def test_status_flags_a_stale_baseline(self):
        self.hub.calibrate(0.0, 50.0)
        self.hub.set_parameter("sync.freq_window_hz", 0.2)
        status = self.hub.sync.status()
        self.assertTrue(status["stale"])
        self.assertFalse(status["expired"])

    def test_frequency_outside_the_matching_window_is_rejected(self):
        self.hub.calibrate(0.0, 50.0)
        with self.assertRaises(FrequencyOutOfWindow):
            self.hub.confirm_frequency(50.5)

    def test_frequency_inside_the_matching_window_returns_the_delta(self):
        self.hub.calibrate(0.0, 50.0)
        report = self.hub.sync.verify_frequency(50.05)
        self.assertAlmostEqual(report["delta_hz"], 0.05)
        self.assertEqual(report["window"]["half_width"], 0.12)

    def test_phase_outside_the_matching_window_is_rejected(self):
        self.hub.calibrate(2.0, 50.0)
        with self.assertRaises(PhaseOutOfWindow):
            self.hub.sync.verify_phase(40.0)

    def test_phase_inside_the_matching_window_returns_the_delta(self):
        self.hub.calibrate(2.0, 50.0)
        report = self.hub.sync.verify_phase(3.0)
        self.assertAlmostEqual(report["delta_deg"], 1.0)

    def test_out_of_band_frequency_is_rejected_when_calibrating(self):
        with self.assertRaises(OutOfRange):
            self.hub.calibrate(0.0, 90.0)

    def test_persisted_sync_result_is_visible_only_after_the_commit(self):
        self.hub.calibrate(0.0, 50.0)
        self.hub.persist_sync("B-1")
        self.assertFalse(self.hub.sync.is_persisted("B-1"))
        self.assertEqual(len(self.hub.log.pending()), 1)
        self.hub.commit_sync("B-1")
        self.assertTrue(self.hub.sync.is_persisted("B-1"))
        self.assertEqual(self.hub.log.pending(), [])

    def test_duplicate_batch_persist_is_rejected(self):
        self.hub.calibrate(0.0, 50.0)
        self.hub.persist_sync("B-1")
        with self.assertRaises(DuplicateRejected):
            self.hub.persist_sync("B-1")

    def test_commit_without_a_pending_result_is_rejected(self):
        with self.assertRaises(Exception) as caught:
            self.hub.commit_sync("B-404")
        self.assertEqual(caught.exception.code, "not_persisted")

    def test_commit_advances_the_watermark(self):
        self.hub.calibrate(0.0, 50.0)
        self.hub.persist_sync("B-1")
        before = self.hub.log.watermark
        result = self.hub.commit_sync("B-1")
        self.assertGreater(result["watermark"], before)

    def test_confirmation_ticket_is_bound_to_the_frequency_generation(self):
        self.hub.calibrate(0.0, 50.0)
        result = self.hub.confirm_frequency(50.02)
        ticket = self.hub.tickets.peek(result["ticket"])
        self.assertEqual(ticket.generation, self.hub.sync.frequency_generation())
        self.assertEqual(ticket.subject, self.hub.sync.frequency_subject())

    def test_baseline_remaining_ticks_counts_down(self):
        self.hub.calibrate(0.0, 50.0, ttl_ticks=10)
        self.advance(3)
        self.assertEqual(self.hub.sync.baseline().remaining(self.hub.clock.tick), 7)
