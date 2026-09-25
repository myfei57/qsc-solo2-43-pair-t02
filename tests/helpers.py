"""Shared fixtures. Data directories are derived from the test name."""

import os
import shutil
import tempfile
import unittest

from linecontrol.hub import ControlHub

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "linecontrol.json")
TEST_ROOT = os.path.join(tempfile.gettempdir(), "linecontrol-tests")


class HubTestCase(unittest.TestCase):
    def setUp(self) -> None:
        parts = self.id().split(".")
        name = parts[-2] + "-" + parts[-1]
        self.data_dir = os.path.join(TEST_ROOT, name)
        shutil.rmtree(self.data_dir, ignore_errors=True)
        os.makedirs(self.data_dir, exist_ok=True)
        self.hub = ControlHub(self.data_dir, CONFIG_PATH)

    def tearDown(self) -> None:
        shutil.rmtree(self.data_dir, ignore_errors=True)

    def reopen(self) -> ControlHub:
        return ControlHub(self.data_dir, CONFIG_PATH)

    def advance(self, ticks: int) -> None:
        self.hub.clock.advance(ticks)

    def prime_unit(self, pressure_bar: float = 2.6):
        return self.hub.run_flow("start", {"pressure_bar": pressure_bar})

    def calibrate(self, phase_deg: float = 2.0, freq_hz: float = 50.0, ttl_ticks=None):
        return self.hub.calibrate(phase_deg, freq_hz, ttl_ticks)

    def persisted_sync(self, batch: str = "B-1", freq_hz: float = 50.0, ttl_ticks=None):
        self.calibrate(0.0, freq_hz, ttl_ticks)
        self.hub.persist_sync(batch)
        return self.hub.commit_sync(batch)

    def close_ticket(self, measured_hz: float = 50.02) -> str:
        return self.hub.confirm_frequency(measured_hz)["ticket"]

    def online(self, batch: str = "B-1", load_kw: float = 180.0, phase_deg: float = 1.5):
        self.prime_unit()
        self.hub.excite()
        self.persisted_sync(batch, 50.0)
        ticket = self.close_ticket(50.02)
        self.hub.close_breaker(batch, ticket, phase_deg)
        self.hub.adjust_load(load_kw)
        return self.hub
