"""Version semantics: every write moves the generation of a parameter."""

from linecontrol.config import ParameterRegistry
from linecontrol.runtime.errors import OutOfRange, UnknownParameter, ValidationError
from tests.helpers import HubTestCase


class ParameterRegistryCase(HubTestCase):
    def test_declared_parameters_start_at_generation_zero(self):
        registry = ParameterRegistry()
        self.assertEqual(registry.generation("gov.target_hz"), 0)
        self.assertEqual(registry.value("gov.target_hz"), 50.0)

    def test_config_file_override_moves_the_generation_once(self):
        self.assertEqual(self.hub.registry.generation("sync.freq_window_hz"), 1)
        self.assertAlmostEqual(self.hub.registry.value("sync.freq_window_hz"), 0.12)

    def test_setting_a_parameter_moves_its_generation(self):
        parameter = self.hub.registry.set("gov.target_hz", 50.05, self.hub.clock.tick)
        self.assertEqual(parameter.generation, 2)
        self.assertEqual(self.hub.registry.generation("gov.target_hz"), 2)

    def test_setting_the_same_value_still_counts_as_a_new_generation(self):
        self.hub.registry.set("gov.target_hz", 50.0)
        self.hub.registry.set("gov.target_hz", 50.0)
        self.assertEqual(self.hub.registry.generation("gov.target_hz"), 3)

    def test_revision_counts_every_write(self):
        before = self.hub.registry.revision
        self.hub.registry.set("gov.target_hz", 50.05)
        self.hub.registry.set("load.unit_capacity_kw", 410.0)
        self.assertEqual(self.hub.registry.revision, before + 2)

    def test_out_of_range_value_is_rejected(self):
        with self.assertRaises(OutOfRange):
            self.hub.registry.set("gov.target_hz", 80.0)

    def test_unknown_parameter_is_rejected(self):
        with self.assertRaises(UnknownParameter):
            self.hub.registry.set("gov.not_declared", 1.0)

    def test_boolean_value_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.hub.registry.set("gov.target_hz", True)

    def test_integral_parameter_rejects_a_fraction(self):
        with self.assertRaises(ValidationError):
            self.hub.registry.set("engine.crank_window_ticks", 3.5)

    def test_combine_sums_dependent_generations(self):
        keys = ("lube.low_pressure_bar", "lube.established_pressure_bar")
        self.assertEqual(self.hub.registry.combine(keys), 2)
        self.hub.registry.set("lube.low_pressure_bar", 1.3)
        self.assertEqual(self.hub.registry.combine(keys), 3)

    def test_generation_error_reports_both_sides(self):
        with self.assertRaises(Exception) as caught:
            self.hub.registry.check_generation("gov.target_hz", 7)
        self.assertEqual(caught.exception.code, "generation_mismatch")
        self.assertEqual(caught.exception.detail["observed"], 7)

    def test_parameter_command_is_recorded_and_committed(self):
        result = self.hub.set_parameter("gov.target_hz", 50.1)
        self.assertEqual(result["parameter"]["generation"], 2)
        self.assertIn(result["record"], [record.record_id for record in self.hub.log.visible()])

    def test_config_records_are_written_on_a_cold_start(self):
        kinds = {record.kind for record in self.hub.log.visible()}
        self.assertIn("config.param", kinds)

    def test_snapshot_lists_every_declared_parameter(self):
        snapshot = self.hub.registry.snapshot()
        self.assertEqual(len(snapshot), len(self.hub.registry.keys()))
        self.assertIn("unit", snapshot["gov.target_hz"])
