"""Restart recovery: replay from the snapshot watermark onwards."""

import os
import unittest

from linecontrol.runtime.errors import SnapshotInvalid
from linecontrol.store import SnapshotPayload, read_snapshot, write_snapshot
from linecontrol.store.errors import WatermarkRegression
from tests.helpers import HubTestCase


class RestartCase(HubTestCase):
    def test_restart_replays_only_committed_records(self):
        self.hub.calibrate(0.0, 50.0)
        pending = self.hub.log.append(
            "engine.start", payload={"rpm": 1500}, tick=self.hub.clock.tick
        )
        self.assertTrue(pending.record_id)
        restarted = self.reopen()
        restarted.restore()
        self.assertEqual(restarted.view.engine(), "stopped")
        self.assertEqual(len(restarted.log.pending()), 1)

    def test_restart_keeps_the_committed_state(self):
        self.prime_unit()
        self.persisted_sync("B-1")
        restarted = self.reopen()
        restarted.restore()
        self.assertEqual(restarted.view.engine(), "running")
        self.assertTrue(restarted.sync.is_persisted("B-1"))

    def test_restore_without_a_snapshot_replays_every_visible_record(self):
        self.prime_unit()
        restarted = self.reopen()
        result = restarted.restore()
        self.assertFalse(result.from_snapshot)
        self.assertEqual(result.replayed, len(restarted.log.visible()))

    def test_snapshot_narrows_the_replay_window(self):
        self.prime_unit()
        self.hub.write_snapshot()
        self.hub.build_pressure(2.7)
        restarted = self.reopen()
        result = restarted.restore()
        self.assertTrue(result.from_snapshot)
        self.assertEqual(result.replayed, 1)
        self.assertEqual(restarted.view.pressure_bar(), 2.7)

    def test_snapshot_watermark_ahead_of_the_log_is_rejected(self):
        self.prime_unit()
        payload = SnapshotPayload(
            watermark=999, generation=0, tick=0, machines={}, audit_watermark=0
        )
        path = os.path.join(self.data_dir, "state.snapshot.json")
        write_snapshot(path, payload)
        restarted = self.reopen()
        with self.assertRaises(WatermarkRegression):
            restarted.restore()

    def test_missing_snapshot_file_is_rejected_on_read(self):
        with self.assertRaises(SnapshotInvalid):
            read_snapshot(os.path.join(self.data_dir, "absent.snapshot.json"))

    def test_tampered_snapshot_is_rejected(self):
        path = os.path.join(self.data_dir, "state.snapshot.json")
        write_snapshot(path, SnapshotPayload(watermark=0, generation=0, tick=0))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('{"payload":{"watermark":0,"generation":0,"tick":0},"digest":"deadbeef"}\n')
        with self.assertRaises(SnapshotInvalid):
            read_snapshot(path)

    def test_clock_resumes_from_the_last_recorded_tick(self):
        self.prime_unit()
        self.persisted_sync("B-1")
        last = self.hub.clock.tick
        restarted = self.reopen()
        self.assertEqual(restarted.clock.tick, last)

    def test_baseline_expiry_survives_a_restart(self):
        self.hub.calibrate(0.0, 50.0, ttl_ticks=2)
        for _ in range(3):
            self.hub.build_pressure(2.6)
        restarted = self.reopen()
        restarted.restore()
        with self.assertRaises(Exception) as caught:
            restarted.sync.require_baseline()
        self.assertEqual(caught.exception.code, "baseline_expired")

    def test_latch_state_is_rebuilt_from_the_record_stream(self):
        self.hub.build_pressure(0.4)
        restarted = self.reopen()
        restarted.restore()
        self.assertTrue(restarted.view.lube_latched())
        self.assertFalse(restarted.lube.acknowledged())
