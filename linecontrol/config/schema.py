"""Declared parameter surface: bounds, units and defaults."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from ..runtime.errors import SnapshotInvalid, UnknownParameter


@dataclass(frozen=True)
class ParameterSpec:
    key: str
    default: float
    low: float
    high: float
    unit: str
    label: str
    integral: bool = False

    def describe(self) -> dict:
        return {
            "key": self.key,
            "default": self.default,
            "low": self.low,
            "high": self.high,
            "unit": self.unit,
            "label": self.label,
            "integral": self.integral,
        }


PARAMETER_SPECS: Tuple[ParameterSpec, ...] = (
    ParameterSpec("lube.low_pressure_bar", 1.2, 0.2, 4.0, "bar", "low pressure alarm level"),
    ParameterSpec("lube.established_pressure_bar", 2.4, 1.0, 8.0, "bar", "pressure build level"),
    ParameterSpec("lube.latch_clear_margin_bar", 0.3, 0.0, 2.0, "bar", "latch clear margin"),
    ParameterSpec("engine.crank_window_ticks", 8, 1, 120, "tick", "crank window", integral=True),
    ParameterSpec("sync.phase_window_deg", 6.0, 0.5, 30.0, "deg", "phase match window"),
    ParameterSpec("sync.freq_window_hz", 0.12, 0.01, 1.0, "Hz", "frequency match window"),
    ParameterSpec("sync.baseline_ttl_ticks", 40, 1, 600, "tick", "baseline lifetime", integral=True),
    ParameterSpec("breaker.close_ticket_ttl_ticks", 10, 1, 300, "tick", "close ticket lifetime", integral=True),
    ParameterSpec("gov.target_hz", 50.0, 45.0, 55.0, "Hz", "governor target frequency"),
    ParameterSpec("gov.freq_window_hz", 0.15, 0.01, 1.0, "Hz", "governor acceptance window"),
    ParameterSpec("load.unit_capacity_kw", 400.0, 50.0, 5000.0, "kW", "unit capacity"),
    ParameterSpec("load.reverse_power_limit_kw", 25.0, 1.0, 500.0, "kW", "reverse power limit"),
    ParameterSpec("avr.excite_voltage_v", 400.0, 100.0, 1200.0, "V", "excitation voltage"),
    ParameterSpec("fuel.tank_capacity_l", 900.0, 10.0, 20000.0, "L", "tank capacity"),
)

_SPECS_BY_KEY: Dict[str, ParameterSpec] = {item.key: item for item in PARAMETER_SPECS}


def spec(key: str) -> ParameterSpec:
    found = _SPECS_BY_KEY.get(key)
    if found is None:
        raise UnknownParameter("parameter is not declared", key=key)
    return found


def load_overrides(path: Path) -> Dict[str, float]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SnapshotInvalid("parameter file is not valid JSON", path=str(source)) from exc
    if not isinstance(raw, dict):
        raise SnapshotInvalid("parameter file must hold an object", path=str(source))
    return {str(key): value for key, value in raw.items()}
