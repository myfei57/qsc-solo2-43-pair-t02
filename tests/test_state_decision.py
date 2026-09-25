"""Decision semantics: current versus historical state and batch identity."""

import unittest

from linecontrol.rules import RecordFilter, Window, centered_window
from linecontrol.rules.uniqueness import BatchRegistry
from linecontrol.runtime.errors import DuplicateRejected, ValidationError
from linecontrol.store.kinds import KIND_ENGINE_START, KIND_LUBE_LATCH_SET, KIND_SYNC_PERSIST
from tests.helpers import HubTestCase


class AlarmDecisionCase(HubTestCase):
    def test_current_alarms_list_only_engaged_latches(self):
        self.hub.build_pressure(0.5)
        current = [item.alarm for item in self.hub.view.alarms()]
        self.assertEqual(current, ["lube.low_pressure"])
        self.hub.build_pressure(2.6)
        self.hub.acknowledge_lube()
        self.hub.clear_lube_latch()
        self.assertEqual(self.hub.view.alarms(), [])

    def test_historical_alarms_keep_the_cleared_entry(self):
        self.hub.build_pressure(0.5)
        self.hub.build_pressure(2.6)
        self.hub.acknowledge_lube()
        self.hub.clear_lube_latch()
        history = self.hub.projector.alarms()
        self.assertEqual([item.state for item in history], ["set", "cleared"])

    def test_current_alarms_ignore_pending_records(self):
        self.hub.log.append(
            KIND_LUBE_LATCH_SET, payload={"alarm": "lube.low_pressure"}, tick=self.hub.clock.tick
        )
        self.assertEqual(self.hub.projector.alarms(), [])
        self.hub.log.commit(tick=self.hub.clock.tick)
        self.assertEqual(len(self.hub.projector.alarms()), 1)

    def test_trip_latch_is_reflected_in_current_alarms(self):
        self.hub.trip_breaker("protection")
        alarms = [item.alarm for item in self.hub.view.alarms()]
        self.assertIn("breaker.trip", alarms)


class BatchIdentityCase(HubTestCase):
    def test_one_batch_may_only_carry_one_payload(self):
        self.prime_unit()
        self.hub.calibrate(0.0, 50.0)
        self.hub.log.append(
            KIND_SYNC_PERSIST,
            batch_id="B-1",
            payload={"phase_deg": 1.0},
            tick=self.hub.clock.tick,
        )
        self.hub.log.append(
            KIND_SYNC_PERSIST,
            batch_id="B-1",
            payload={"phase_deg": 2.0},
            tick=self.hub.clock.tick,
        )
        self.hub.log.commit(tick=self.hub.clock.tick)
        with self.assertRaises(DuplicateRejected):
            self.hub.projector.batch_registry()

    def test_identical_payloads_for_one_batch_are_idempotent(self):
        registry = BatchRegistry()
        registry.register("B-1", "abc", 1, KIND_SYNC_PERSIST)
        registry.register("B-1", "abc", 2, KIND_SYNC_PERSIST)
        self.assertEqual(registry.size(), 1)
        self.assertEqual(registry.conflicts, 0)

    def test_batch_registry_rejects_an_empty_identifier(self):
        with self.assertRaises(DuplicateRejected):
            BatchRegistry().register("", "abc", 1, KIND_SYNC_PERSIST)

    def test_committed_batches_are_counted_from_the_stream(self):
        self.persisted_sync("B-1")
        self.persisted_sync("B-2")
        self.assertEqual(self.hub.projector.batch_registry().size(), 2)

    def test_kind_counts_report_committed_work(self):
        self.prime_unit()
        counts = self.hub.projector.kind_counts()
        self.assertIn(KIND_ENGINE_START, counts)


class WindowDecisionCase(unittest.TestCase):
    def test_window_classification_boundaries(self):
        window = Window(1.0, 2.0)
        self.assertEqual(window.classify(0.5), "below")
        self.assertEqual(window.classify(1.5), "inside")
        self.assertEqual(window.classify(3.0), "above")
        self.assertTrue(window.contains(1.0))
        self.assertTrue(window.contains(2.0))

    def test_exclusive_window_rejects_its_edges(self):
        window = Window(1.0, 2.0, inclusive=False)
        self.assertFalse(window.contains(1.0))
        self.assertTrue(window.contains(1.5))

    def test_window_clamps_outliers(self):
        window = Window(1.0, 2.0)
        self.assertEqual(window.clamp(0.0), 1.0)
        self.assertEqual(window.clamp(9.0), 2.0)

    def test_inverted_window_is_rejected(self):
        with self.assertRaises(ValidationError):
            Window(2.0, 1.0)

    def test_centered_window_rejects_a_negative_half_width(self):
        with self.assertRaises(ValidationError):
            centered_window(5.0, -0.1)

    def test_centered_window_describes_its_half_width(self):
        window = centered_window(10.0, 0.5)
        self.assertEqual(window.describe()["half_width"], 0.5)


class RecordFilterCase(HubTestCase):
    def records(self):
        self.prime_unit()
        return self.hub.log.visible()

    def test_filter_by_kind(self):
        selected = RecordFilter(kinds=(KIND_ENGINE_START,)).apply(self.records())
        self.assertTrue(selected)
        self.assertTrue(all(record.kind == KIND_ENGINE_START for record in selected))

    def test_filter_by_tick_range(self):
        records = self.records()
        highest = max(record.tick for record in records)
        selected = RecordFilter(since_tick=highest, until_tick=highest).apply(records)
        self.assertTrue(selected)
        self.assertTrue(all(record.tick == highest for record in selected))

    def test_filter_by_batch(self):
        self.persisted_sync("B-7")
        selected = RecordFilter(batch_id="B-7").apply(self.hub.log.visible())
        self.assertTrue(selected)
        self.assertTrue(all(record.batch_id == "B-7" for record in selected))

    def test_filter_by_generation_band(self):
        records = self.records()
        wide = RecordFilter(min_generation=0, max_generation=99).apply(records)
        narrow = RecordFilter(min_generation=99).apply(records)
        self.assertEqual(len(wide), len(records))
        self.assertEqual(narrow, [])

    def test_empty_filter_keeps_every_record(self):
        records = self.records()
        self.assertEqual(len(RecordFilter().apply(records)), len(records))
