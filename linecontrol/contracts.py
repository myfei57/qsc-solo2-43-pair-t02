"""The cross module contracts expressed as parameter generation keys."""

from typing import Dict, List, Tuple

BASELINE_KEYS: Tuple[str, ...] = (
    "sync.phase_window_deg",
    "sync.freq_window_hz",
    "sync.baseline_ttl_ticks",
)

PHASE_KEYS: Tuple[str, ...] = ("sync.phase_window_deg", "sync.freq_window_hz")

FREQUENCY_KEYS: Tuple[str, ...] = (
    "sync.freq_window_hz",
    "gov.target_hz",
    "gov.freq_window_hz",
)

CLOSE_KEYS: Tuple[str, ...] = (
    "sync.phase_window_deg",
    "sync.freq_window_hz",
    "gov.target_hz",
    "breaker.close_ticket_ttl_ticks",
)

RELEASE_KEYS: Tuple[str, ...] = ("load.reverse_power_limit_kw",)

START_KEYS: Tuple[str, ...] = (
    "lube.low_pressure_bar",
    "lube.established_pressure_bar",
    "lube.latch_clear_margin_bar",
)

LOAD_KEYS: Tuple[str, ...] = ("load.unit_capacity_kw", "load.reverse_power_limit_kw")

CONTRACTS: Tuple[Dict[str, object], ...] = (
    {
        "name": "record stream",
        "keys": ("store.watermark",),
        "description": "append only records, monotone commit watermark, replay from the watermark",
    },
    {
        "name": "baseline generation",
        "keys": BASELINE_KEYS,
        "description": "a phase baseline expires and never survives a parameter generation bump",
    },
    {
        "name": "frequency confirmation",
        "keys": FREQUENCY_KEYS,
        "description": "a frequency confirmation is single use, expires and is generation bound",
    },
    {
        "name": "breaker close",
        "keys": CLOSE_KEYS,
        "description": "the breaker closes only after a committed sync result and a live confirmation",
    },
    {
        "name": "oil pressure gate",
        "keys": START_KEYS,
        "description": "the prime mover cranks only with established oil pressure and a cleared latch",
    },
    {
        "name": "load acceptance",
        "keys": LOAD_KEYS,
        "description": "load stays inside the unit capacity and above the reverse power limit",
    },
)


def baseline_generation(registry) -> int:
    return registry.combine(BASELINE_KEYS)


def phase_generation(registry) -> int:
    return registry.combine(PHASE_KEYS)


def frequency_generation(registry) -> int:
    return registry.combine(FREQUENCY_KEYS)


def close_generation(registry) -> int:
    return registry.combine(CLOSE_KEYS)


def release_generation(registry) -> int:
    return registry.combine(RELEASE_KEYS)


def start_generation(registry) -> int:
    return registry.combine(START_KEYS)


def load_generation(registry) -> int:
    return registry.combine(LOAD_KEYS)


def contract_table() -> List[Dict[str, object]]:
    return [
        {"name": item["name"], "keys": list(item["keys"]), "description": item["description"]}
        for item in CONTRACTS
    ]
