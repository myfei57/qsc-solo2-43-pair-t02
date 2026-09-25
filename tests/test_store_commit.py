"""Write semantics: appended records stay invisible until the watermark moves."""

import os
import shutil
import tempfile
import unittest

from linecontrol.runtime.errors import OutOfRange, UnknownItem, ValidationError
from linecontrol.runtime.ids import IdSequencer
from linecontrol.store import AppendOnlyLog, TombstoneConflict, UnknownRecord
from linecontrol.store.errors import WatermarkRegression
from linecontrol.store.kinds import KIND_BREAKER_CLOSE, KIND_COMMIT, KIND_ENGINE_START
from tests.helpers import HubTestCase

TEST_ROOT = os.path.join(tempfile.gettempdir(), "linecontrol-tests")


class AppendOnlyLogCase(unittest.TestCase):
    def setUp(self) -> None:
        parts = self.id().split(".")
        self.root = os.path.join(TEST_ROOT, parts[-2] + "-" + parts[-1])
        shutil.rmtree(self.root, ignore_errors=True)
        os.makedirs(self.root, exist_ok=True)
        sequencer = IdSequencer()
        self.log = AppendOnlyLog(os.path.join(self.root, "store.jsonl"), sequencer, "REC")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_appended_record_is_pending_until_commit(self):
        self.log.append(KIND_ENGINE_START, payload={"rpm": 1500}, tick=1)
        self.assertEqual(len(self.log.pending()), 1)
        self.assertEqual(self.log.visible(), [])
        self.assertEqual(self.log.watermark, 0)

    def test_commit_makes_appended_records_visible(self):
        self.log.append(KIND_ENGINE_START, payload={"rpm": 1500}, tick=1)
        self.log.commit(tick=2)
        self.assertEqual(len(self.log.visible()), 1)
        self.assertEqual(self.log.pending(), [])

    def test_watermark_matches_highest_committed_data_record(self):
        first = self.log.append(KIND_ENGINE_START, payload={"rpm": 1500}, tick=1)
        self.log.commit(tick=1)
        self.assertEqual(self.log.watermark, first.seq)
        self.log.append(KIND_BREAKER_CLOSE, batch_id="B-1", payload={}, tick=2)
        self.log.commit(tick=2)
        self.assertEqual(self.log.watermark, self.log.max_data_seq())

    def test_repeated_commit_never_moves_the_watermark_backwards(self):
        self.log.append(KIND_ENGINE_START, payload={"rpm": 1500}, tick=1)
        self.log.commit(tick=1)
        first = self.log.watermark
        self.log.commit(tick=2)
        self.log.commit(tick=3)
        self.assertEqual(self.log.watermark, first)

    def test_commit_records_are_not_visible_data(self):
        self.log.append(KIND_ENGINE_START, payload={"rpm": 1500}, tick=1)
        self.log.commit(tick=1)
        kinds = [record.kind for record in self.log.visible()]
        self.assertNotIn(KIND_COMMIT, kinds)

    def test_tombstone_hides_the_record_but_keeps_the_line(self):
        record = self.log.append(KIND_ENGINE_START, payload={"rpm": 1500}, tick=1)
        self.log.commit(tick=1)
        self.log.tombstone(record.record_id, "operator void", tick=2)
        self.assertEqual(self.log.visible(), [])
        self.assertEqual(len(self.log.records()), 3)
        self.assertTrue(self.log.is_tombstoned(record.record_id))

    def test_tombstone_of_an_unknown_record_is_rejected(self):
        with self.assertRaises(UnknownRecord):
            self.log.tombstone("REC-999999", "nope", tick=1)

    def test_second_tombstone_for_the_same_record_is_rejected(self):
        record = self.log.append(KIND_ENGINE_START, payload={"rpm": 1500}, tick=1)
        self.log.tombstone(record.record_id, "operator void", tick=2)
        with self.assertRaises(TombstoneConflict):
            self.log.tombstone(record.record_id, "again", tick=3)

    def test_unknown_record_lookup_is_rejected(self):
        with self.assertRaises(UnknownItem):
            self.log.find("REC-000404")

    def test_append_rejects_an_unknown_kind(self):
        with self.assertRaises(ValidationError):
            self.log.append("not.a.kind", tick=1)

    def test_append_rejects_a_control_kind(self):
        with self.assertRaises(ValidationError):
            self.log.append(KIND_COMMIT, tick=1)

    def test_validate_accepts_a_healthy_stream(self):
        self.log.append(KIND_ENGINE_START, payload={"rpm": 1500}, tick=1)
        self.log.commit(tick=1)
        self.log.validate()

    def test_summary_counts_every_scope(self):
        record = self.log.append(KIND_ENGINE_START, payload={"rpm": 1500}, tick=1)
        self.log.append(KIND_BREAKER_CLOSE, payload={}, tick=2)
        self.log.commit(tick=2)
        self.log.tombstone(record.record_id, "void", tick=3)
        summary = self.log.summary()
        self.assertEqual(summary["data_records"], 2)
        self.assertEqual(summary["visible"], 1)
        self.assertEqual(summary["tombstones"], 1)


class HubWriteSemanticsCase(HubTestCase):
    def test_uncommitted_records_do_not_move_machine_state(self):
        self.hub.log.append(
            KIND_ENGINE_START, payload={"rpm": 1500}, tick=self.hub.clock.tick
        )
        self.assertEqual(self.hub.view.engine(), "stopped")
        self.hub.log.commit(tick=self.hub.clock.tick)
        self.assertEqual(self.hub.view.engine(), "running")

    def test_pending_and_visible_views_partition_the_stream(self):
        self.prime_unit()
        self.assertEqual(self.hub.log.pending(), [])
        self.assertTrue(len(self.hub.log.visible()) > 0)

    def test_rollback_below_the_watermark_is_rejected(self):
        self.prime_unit()
        with self.assertRaises(WatermarkRegression):
            self.hub.log.rollback(0, "abort", tick=self.hub.clock.tick)

    def test_rollback_past_the_end_of_the_log_is_rejected(self):
        with self.assertRaises(OutOfRange):
            self.hub.log.rollback(9999, "abort", tick=1)

    def test_rollback_discards_the_uncommitted_tail(self):
        first = self.hub.log.append(KIND_ENGINE_START, payload={"rpm": 1500}, tick=1)
        second = self.hub.log.append(KIND_BREAKER_CLOSE, payload={}, tick=2)
        self.hub.log.rollback(first.seq, "aborted batch", tick=3)
        pending = [record.record_id for record in self.hub.log.pending()]
        discarded = [record.record_id for record in self.hub.log.discarded()]
        self.assertNotIn(second.record_id, pending)
        self.assertIn(second.record_id, discarded)
