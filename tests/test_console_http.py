"""HTTP surface: JSON endpoints, error mapping and the operator pages."""

import http.client
import json
import threading

from linecontrol.console import Console, build_server
from tests.helpers import HubTestCase


class ConsoleCase(HubTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.console = Console(self.hub)

    def get(self, path, query=None):
        return self.console.dispatch("GET", path, query or {}, {})

    def post(self, path, body=None):
        return self.console.dispatch("POST", path, {}, body or {})

    def test_healthz_returns_ok(self):
        response = self.get("/healthz")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.as_json()["status"], "ok")

    def test_healthz_reports_degraded_after_a_snapshot_mismatch(self):
        import os

        from linecontrol.store import SnapshotPayload, write_snapshot

        write_snapshot(
            os.path.join(self.data_dir, "state.snapshot.json"),
            SnapshotPayload(watermark=999, generation=0, tick=0),
        )
        response = self.get("/healthz")
        self.assertEqual(response.status, 503)
        self.assertEqual(response.as_json()["status"], "degraded")

    def test_state_endpoint_reports_the_machine(self):
        self.prime_unit()
        payload = self.get("/api/state").as_json()
        self.assertEqual(payload["engine"], "running")
        self.assertFalse(payload["online"])

    def test_alarm_endpoint_serves_both_scopes(self):
        self.hub.build_pressure(0.5)
        current = self.get("/api/state/alarms", {"scope": "current"}).as_json()
        history = self.get("/api/state/alarms", {"scope": "historical"}).as_json()
        self.assertEqual(len(current["alarms"]), 1)
        self.assertEqual(len(history["alarms"]), 1)

    def test_alarm_endpoint_rejects_an_unknown_scope(self):
        response = self.get("/api/state/alarms", {"scope": "tomorrow"})
        self.assertEqual(response.status, 422)
        self.assertEqual(response.as_json()["error"], "validation_error")

    def test_config_endpoint_lists_every_parameter(self):
        payload = self.get("/api/config").as_json()
        self.assertIn("gov.target_hz", payload["parameters"])
        self.assertEqual(payload["revision"], len(payload["parameters"]))

    def test_config_post_updates_a_parameter(self):
        response = self.post("/api/config", {"key": "gov.target_hz", "value": 50.05})
        self.assertEqual(response.status, 200)
        self.assertAlmostEqual(self.hub.registry.value("gov.target_hz"), 50.05)
        payload = self.get("/api/config").as_json()
        self.assertEqual(payload["revision"], len(payload["parameters"]) + 1)

    def test_config_post_rejects_a_non_numeric_value(self):
        response = self.post("/api/config", {"key": "gov.target_hz", "value": "fast"})
        self.assertEqual(response.status, 422)

    def test_config_post_rejects_an_out_of_range_value(self):
        response = self.post("/api/config", {"key": "gov.target_hz", "value": 99.0})
        self.assertEqual(response.status, 422)
        self.assertEqual(response.as_json()["error"], "out_of_range")

    def test_contracts_endpoint_reports_generations(self):
        payload = self.get("/api/contracts").as_json()
        self.assertIn("close", payload["generations"])
        self.assertTrue(payload["contracts"])

    def test_records_endpoint_serves_each_scope(self):
        self.hub.calibrate(0.0, 50.0)
        self.hub.persist_sync("B-1")
        visible = self.get("/api/store/records", {"scope": "visible"}).as_json()
        pending = self.get("/api/store/records", {"scope": "pending"}).as_json()
        self.assertTrue(visible["records"])
        self.assertEqual(len(pending["records"]), 1)
        self.assertGreater(pending["tail"], pending["watermark"])

    def test_records_endpoint_rejects_an_unknown_scope(self):
        response = self.get("/api/store/records", {"scope": "everything"})
        self.assertEqual(response.status, 422)

    def test_records_endpoint_filters_by_batch(self):
        self.persisted_sync("B-5")
        payload = self.get("/api/store/records", {"scope": "visible", "batch": "B-5"}).as_json()
        self.assertTrue(all(item["batch"] == "B-5" for item in payload["records"]))

    def test_audit_endpoint_lists_entries(self):
        self.hub.build_pressure(2.6)
        payload = self.get("/api/audit", {"action": "lube.pressure"}).as_json()
        self.assertEqual(payload["count"], 1)

    def test_audit_stats_endpoint_reports_command_counts(self):
        self.hub.build_pressure(2.6)
        payload = self.get("/api/audit/stats").as_json()
        self.assertEqual(payload["commands"]["total"], 1)

    def test_flows_endpoint_lists_the_plans(self):
        payload = self.get("/api/flows").as_json()
        self.assertEqual(len(payload["flows"]), 3)
        self.assertIn("start", payload["flow_params"])

    def test_flow_detail_endpoint_lists_required_arguments(self):
        payload = self.get("/api/flows/parallel").as_json()
        self.assertEqual(
            payload["required_arguments"], ["batch", "measured_hz", "phase_deg", "load_kw"]
        )
        self.assertEqual(payload["prerequisites"]["breaker.close"], ["sync.confirm"])

    def test_flow_detail_endpoint_rejects_an_unknown_flow(self):
        response = self.get("/api/flows/orbit")
        self.assertEqual(response.status, 404)
        self.assertEqual(response.as_json()["error"], "unknown_item")

    def test_flow_run_endpoint_executes_the_start_sequence(self):
        response = self.post("/api/flows/start/run", {"pressure_bar": 2.6})
        payload = response.as_json()
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(self.hub.view.engine(), "running")

    def test_flow_run_endpoint_maps_a_rejection_to_a_conflict(self):
        response = self.post("/api/flows/stop/run", {})
        self.assertEqual(response.status, 409)
        self.assertEqual(response.as_json()["error"], "order_violation")

    def test_lube_pressure_endpoint_updates_the_reading(self):
        response = self.post("/api/lube/pressure", {"bar": 2.6})
        self.assertEqual(response.status, 200)
        self.assertTrue(response.as_json()["established"])

    def test_engine_start_endpoint_reports_the_closed_gate(self):
        response = self.post("/api/engine/start", {})
        self.assertEqual(response.status, 409)
        self.assertEqual(response.as_json()["error"], "engine_gate_closed")

    def test_breaker_close_endpoint_requires_a_committed_result(self):
        self.prime_unit()
        self.hub.calibrate(0.0, 50.0)
        self.hub.persist_sync("B-1")
        ticket = self.close_ticket(50.02)
        response = self.post(
            "/api/breaker/close", {"batch": "B-1", "ticket": ticket, "phase_deg": 1.0}
        )
        self.assertEqual(response.status, 409)
        self.assertEqual(response.as_json()["error"], "not_persisted")

    def test_unknown_path_returns_not_found(self):
        response = self.get("/api/nothing")
        self.assertEqual(response.status, 404)
        self.assertEqual(response.as_json()["error"], "path_not_found")

    def test_method_mismatch_returns_not_found(self):
        response = self.post("/api/state", {})
        self.assertEqual(response.status, 404)

    def test_pages_are_served_as_html(self):
        for path in ("/", "/overview", "/operations", "/audit"):
            response = self.get(path)
            self.assertEqual(response.status, 200, path)
            self.assertIn("text/html", response.content_type)
            self.assertIn("<html", response.body)

    def test_meta_endpoint_lists_subsystems_and_pages(self):
        payload = self.get("/api/meta").as_json()
        self.assertIn("engine", payload["subsystems"])
        self.assertEqual(payload["flows"], ["parallel", "start", "stop"])
        self.assertEqual(payload["pages"], ["audit", "operations", "overview"])

    def test_routes_endpoint_lists_registered_paths(self):
        payload = self.get("/api/routes").as_json()
        patterns = [item["pattern"] for item in payload["routes"]]
        self.assertIn("/api/flows/{name}/run", patterns)

    def test_socket_server_serves_healthz(self):
        server = build_server(self.console, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.bound_port, timeout=5)
            connection.request("GET", "/healthz")
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["status"], "ok")

    def test_socket_server_accepts_a_post(self):
        server = build_server(self.console, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.bound_port, timeout=5)
            connection.request(
                "POST",
                "/api/config",
                body=json.dumps({"key": "gov.target_hz", "value": 50.02}),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(response.status, 200)
        self.assertAlmostEqual(payload["parameter"]["value"], 50.02)
