"""Service metadata for the console."""

from typing import Any, Dict

from .. import __version__
from ..ns.names import label, subsystem_ids


def service_meta(hub, pages) -> Dict[str, Any]:
    return {
        "service": "linecontrol",
        "version": __version__,
        "subsystems": subsystem_ids(),
        "subsystem_labels": {name: label(name) for name in subsystem_ids()},
        "flows": hub.planner.names(),
        "flow_params": hub.flow_params(),
        "pages": pages.names(),
        "parameters": len(hub.registry.keys()),
        "identifiers": hub.ids.counters(),
        "clock": hub.clock.stamp(),
        "store": hub.log.summary(),
    }
