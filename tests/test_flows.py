"""Ordered flows, plan validation and the runner."""

from linecontrol.breaker.errors import ContactAngleOutOfRange
from linecontrol.control import FLOW_PARALLEL, FLOW_START, FLOW_STOP
from linecontrol.runtime.errors import OrderViolation, UnknownItem, ValidationError
from linecontrol.sync.errors import FrequencyOutOfWindow
from tests.helpers import HubTestCase


class FlowCase(HubTestCase):
    def test_start_flow_runs_its_steps_in_order(self):
        outcome = self.hub.run_flow(FLOW_START, {"pressure_bar": 2.6})
        names = [step["step"] for step in outcome["steps"]]
        self.assertEqual(names[:3], ["lube.pressure", "engine.crank", "engine.start"])
        self.assertEqual(outcome["status"], "ok")

    def test_parallel_flow_runs_its_steps_in_order(self):
        self.prime_unit()
        outcome = self.hub.run_flow(
            FLOW_PARALLEL,
            {"batch": "B-1", "measured_hz": 50.02, "phase_deg": 1.0, "load_kw": 120.0},
        )
        names = [step["step"] for step in outcome["steps"]]
        self.assertEqual(
            names[:6],
            [
                "sync.baseline",
                "sync.persist",
                "sync.commit",
                "sync.confirm",
                "breaker.close",
                "load.adjust",
            ],
        )
        self.assertTrue(self.hub.view.online())

    def test_stop_flow_requires_an_online_unit(self):
        with self.assertRaises(OrderViolation):
            self.hub.run_flow(FLOW_STOP, {})

    def test_stop_flow_returns_the_unit_to_stopped(self):
        self.online()
        outcome = self.hub.run_flow(FLOW_STOP, {"reason": "planned"})
        self.assertEqual(outcome["status"], "ok")
        self.assertEqual(self.hub.view.engine(), "stopped")

    def test_parallel_flow_rejects_an_out_of_window_frequency(self):
        self.prime_unit()
        with self.assertRaises(FrequencyOutOfWindow):
            self.hub.run_flow(
                FLOW_PARALLEL,
                {"batch": "B-1", "measured_hz": 55.0, "phase_deg": 1.0, "load_kw": 120.0},
            )

    def test_parallel_flow_rejects_an_out_of_window_phase(self):
        self.prime_unit()
        with self.assertRaises(ContactAngleOutOfRange):
            self.hub.run_flow(
                FLOW_PARALLEL,
                {"batch": "B-1", "measured_hz": 50.02, "phase_deg": 30.0, "load_kw": 120.0},
            )

    def test_parallel_flow_commits_the_sync_result(self):
        self.prime_unit()
        self.hub.run_flow(
            FLOW_PARALLEL,
            {"batch": "B-9", "measured_hz": 50.02, "phase_deg": 1.0, "load_kw": 10.0},
        )
        self.assertTrue(self.hub.sync.is_persisted("B-9"))

    def test_flow_missing_arguments_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.hub.run_flow(FLOW_PARALLEL, {"batch": "B-1"})

    def test_unknown_flow_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.hub.run_flow("orbit", {})

    def test_flow_arguments_are_described(self):
        params = self.hub.flow_params()
        self.assertEqual(params[FLOW_PARALLEL], ["batch", "measured_hz", "phase_deg", "load_kw"])
        self.assertEqual(params[FLOW_STOP], [])


class PlannerCase(HubTestCase):
    def test_planner_rejects_an_out_of_order_execution(self):
        with self.assertRaises(OrderViolation):
            self.hub.planner.validate(FLOW_START, ["engine.crank", "lube.pressure"])

    def test_planner_accepts_an_ordered_prefix(self):
        self.hub.planner.validate(FLOW_START, ["lube.pressure", "engine.crank"])

    def test_planner_rejects_more_steps_than_the_plan(self):
        with self.assertRaises(OrderViolation):
            self.hub.planner.validate(FLOW_STOP, ["breaker.open", "avr.deexcite", "engine.stop", "extra"])

    def test_planner_reports_prerequisites(self):
        prerequisites = self.hub.planner.prerequisites(FLOW_PARALLEL)
        self.assertEqual(prerequisites["breaker.close"], ["sync.confirm"])

    def test_planner_rejects_an_unknown_flow(self):
        with self.assertRaises(UnknownItem):
            self.hub.planner.plan("orbit")

    def test_planner_rejects_an_unknown_step(self):
        with self.assertRaises(UnknownItem):
            self.hub.planner.plan(FLOW_START).step("nope")

    def test_plan_describe_lists_the_order(self):
        described = self.hub.planner.plan(FLOW_START).describe()
        self.assertEqual(described["order"], ["lube.pressure", "engine.crank", "engine.start"])

    def test_duplicate_flow_names_are_rejected(self):
        from linecontrol.planner.plan import SequencePlanner
        from linecontrol.control.flows import start_flow

        with self.assertRaises(ValidationError):
            SequencePlanner([start_flow(), start_flow()])


class RunnerCase(HubTestCase):
    def test_runner_reports_the_failed_step(self):
        from linecontrol.sync.errors import FrequencyOutOfWindow

        def handler(step, context):
            if step.name == "engine.crank":
                raise FrequencyOutOfWindow("noise")
            return {"step": step.name}

        outcome = self.hub.runner.run(FLOW_START, handler)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.failed_step(), "engine.crank")
        self.assertEqual(outcome.error.code, "frequency_out_of_window")

    def test_runner_flags_a_skipped_step_as_a_plan_violation(self):
        def handler(step, context):
            if step.name == "engine.crank":
                return None
            return {"step": step.name}

        outcome = self.hub.runner.run(FLOW_START, handler)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.error.code, "order_violation")
        statuses = [result.status for result in outcome.results]
        self.assertIn("skipped", statuses)

    def test_runner_passes_previous_results_to_the_next_step(self):
        seen = {}

        def handler(step, context):
            if step.name == "engine.crank":
                seen["first"] = context["lube.pressure"]["marker"]
            return {"marker": step.name}

        outcome = self.hub.runner.run(FLOW_START, handler)
        self.assertTrue(outcome.ok)
        self.assertEqual(seen["first"], "lube.pressure")
