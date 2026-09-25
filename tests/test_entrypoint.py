"""The root entry point forwards CLI arguments to the service command line."""

import contextlib
import io
import os
import shutil
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import main as entrypoint  # noqa: E402

from tests.helpers import CONFIG_PATH, TEST_ROOT  # noqa: E402


class EntryPointCase(unittest.TestCase):
    def setUp(self) -> None:
        self.data_dir = os.path.join(TEST_ROOT, "entrypoint-state")
        shutil.rmtree(self.data_dir, ignore_errors=True)
        os.makedirs(self.data_dir, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.data_dir, ignore_errors=True)

    def run_entrypoint(self, argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = entrypoint.main(argv)
        return code, buffer.getvalue()

    def test_entrypoint_returns_two_without_a_subcommand(self):
        code, _ = self.run_entrypoint([])
        self.assertEqual(code, 2)

    def test_entrypoint_runs_the_state_command_for_a_data_directory(self):
        code, output = self.run_entrypoint(["--data-dir", self.data_dir, "state"])
        self.assertEqual(code, 0)
        self.assertIn("\"status\"", output)

    def test_entrypoint_runs_the_snapshot_command(self):
        code, output = self.run_entrypoint(["--data-dir", self.data_dir, "snapshot"])
        self.assertEqual(code, 0)
        self.assertIn("watermark", output)
        self.assertTrue(os.path.exists(os.path.join(self.data_dir, "state.snapshot.json")))

    def test_entrypoint_accepts_the_config_flag_before_the_subcommand(self):
        code, _ = self.run_entrypoint(
            ["--data-dir", self.data_dir, "--config", CONFIG_PATH, "state"]
        )
        self.assertEqual(code, 0)
