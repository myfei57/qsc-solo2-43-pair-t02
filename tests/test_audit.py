"""Audit trail over every command."""

from tests.helpers import HubTestCase


class AuditCase(HubTestCase):
    def test_successful_command_leaves_one_ok_entry(self):
        self.hub.build_pressure(2.6)
        entries = self.hub.journal.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].action, "lube.pressure")
        self.assertTrue(entries[0].ok)

    def test_rejected_command_leaves_the_error_code(self):
        with self.assertRaises(Exception):
            self.hub.open_breaker("nothing to open")
        entries = self.hub.journal.entries()
        self.assertEqual(entries[0].outcome, "order_violation")
        self.assertFalse(entries[0].ok)

    def test_rejected_entry_carries_a_message(self):
        with self.assertRaises(Exception):
            self.hub.crank()
        self.assertIn("message", self.hub.journal.entries()[0].detail)

    def test_audit_query_filters_by_action(self):
        self.hub.build_pressure(2.6)
        self.hub.crank()
        selected = self.hub.audit_query(action="engine.crank")
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["action"], "engine.crank")

    def test_audit_query_filters_by_outcome(self):
        self.hub.build_pressure(2.6)
        with self.assertRaises(Exception):
            self.hub.open_breaker("nothing to open")
        accepted = self.hub.audit_query(outcome="ok")
        rejected = self.hub.audit_query(outcome="order_violation")
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 1)

    def test_audit_query_filters_by_batch(self):
        self.hub.calibrate(0.0, 50.0)
        self.hub.persist_sync("B-1")
        selected = self.hub.audit_query(batch_id="B-1")
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["batch"], "B-1")

    def test_audit_entries_are_append_only(self):
        self.hub.build_pressure(2.6)
        self.hub.crank()
        first = self.hub.journal.entries()
        self.hub.start_engine()
        second = self.hub.journal.entries()
        self.assertEqual(second[: len(first)], first)
        self.assertEqual(len(second), len(first) + 1)

    def test_audit_stats_count_failures(self):
        self.hub.build_pressure(2.6)
        with self.assertRaises(Exception):
            self.hub.start_engine()
        report = self.hub.metrics_report()
        self.assertEqual(report["audit"]["total"], 2)
        self.assertEqual(report["audit"]["failures"], 1)

    def test_audit_actions_are_sorted(self):
        self.hub.build_pressure(2.6)
        self.hub.crank()
        self.hub.start_engine()
        actions = self.hub.journal.actions()
        self.assertEqual(actions, sorted(actions))

    def test_audit_pending_entries_stay_hidden_until_commit(self):
        self.hub.journal.record("manual", "test", "ok", "", {"note": "held"})
        self.assertEqual(len(self.hub.journal.pending()), 1)
        self.assertEqual(self.hub.journal.entries(), [])
        self.hub.journal.commit()
        self.assertEqual(len(self.hub.journal.entries()), 1)

    def test_audit_journal_records_the_actor(self):
        self.hub.build_pressure(2.6)
        self.assertEqual(self.hub.journal.entries()[0].actor, "operator")
