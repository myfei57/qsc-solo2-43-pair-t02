"""Health probes, metrics and fuel accounting."""

import os

from linecontrol.fuel.errors import TankOverflow
from linecontrol.metrics import MetricRegistry
from linecontrol.runtime.errors import ValidationError
from linecontrol.store import SnapshotPayload, write_snapshot
from tests.helpers import HubTestCase


class ProbeCase(HubTestCase):
    def test_probe_reports_healthy_on_a_fresh_store(self):
        report = self.hub.probe.run()
        self.assertTrue(report.healthy)
        self.assertEqual(report.status_code, 200)

    def test_probe_reports_healthy_state_after_a_full_sequence(self):
        self.online()
        report = self.hub.probe.run()
        self.assertTrue(report.healthy)
        self.assertEqual(report.failures(), [])

    def test_probe_snapshot_check_reports_absence(self):
        checks = {item.name: item for item in self.hub.probe.run().checks}
        self.assertFalse(checks["snapshot.consistent"].detail["present"])

    def test_probe_is_unhealthy_when_the_snapshot_is_ahead_of_the_log(self):
        path = os.path.join(self.data_dir, "state.snapshot.json")
        write_snapshot(path, SnapshotPayload(watermark=500, generation=0, tick=0))
        report = self.hub.probe.run()
        self.assertFalse(report.healthy)
        self.assertEqual(report.status_code, 503)
        self.assertIn("snapshot.consistent", report.failures())

    def test_probe_reports_the_store_summary(self):
        checks = {item.name: item for item in self.hub.probe.run().checks}
        self.assertIn("records", checks["store.readable"].detail)


class MetricsCase(HubTestCase):
    def test_metrics_count_accepted_and_rejected_commands(self):
        self.hub.build_pressure(2.6)
        with self.assertRaises(Exception):
            self.hub.open_breaker("nothing to open")
        summary = self.hub.metrics_report()["commands"]
        self.assertEqual(summary["accepted"], 1)
        self.assertEqual(summary["rejected"], 1)
        self.assertEqual(summary["total"], 2)

    def test_metrics_report_includes_confirmations(self):
        self.hub.calibrate(0.0, 50.0)
        self.hub.confirm_frequency(50.02)
        report = self.hub.metrics_report()
        self.assertEqual(report["confirmations"]["issued"], 1)

    def test_metric_registry_rejects_an_empty_name(self):
        with self.assertRaises(ValidationError):
            MetricRegistry().incr("")

    def test_metric_registry_snapshots_counters_and_gauges(self):
        metrics = MetricRegistry()
        metrics.incr("a")
        metrics.incr("a", 2)
        metrics.gauge("b", 4.5)
        summary = metrics.summary()
        self.assertEqual(summary["counters"]["a"], 3.0)
        self.assertEqual(summary["gauges"]["b"], 4.5)

    def test_metric_registry_reset_clears_state(self):
        metrics = MetricRegistry()
        metrics.incr("a")
        metrics.reset()
        self.assertEqual(metrics.counters(), {})


class FuelCase(HubTestCase):
    def test_fuel_delivery_accumulates(self):
        self.hub.deliver_fuel(120.0)
        self.hub.deliver_fuel(80.0)
        self.assertAlmostEqual(self.hub.fuel.delivered_liters(), 200.0)

    def test_fuel_overflow_is_rejected(self):
        self.hub.deliver_fuel(800.0)
        with self.assertRaises(TankOverflow):
            self.hub.deliver_fuel(200.0)

    def test_fuel_non_positive_delivery_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.hub.deliver_fuel(0.0)
        with self.assertRaises(ValidationError):
            self.hub.deliver_fuel(-5.0)

    def test_fuel_status_reports_the_remaining_volume(self):
        self.hub.deliver_fuel(300.0)
        status = self.hub.fuel.status()
        self.assertEqual(status["remaining_liters"], 600.0)
        self.assertAlmostEqual(status["fill_ratio"], 0.333333)
