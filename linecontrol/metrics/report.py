"""Composite report used by the console and the CLI."""

from typing import Any, Dict

from .counters import MetricRegistry


def operation_report(metrics: MetricRegistry, audit_stats, tickets_summary: Dict[str, Any]) -> Dict[str, Any]:
    total = metrics.counter("command.total")
    rejected = metrics.counter("command.rejected")
    accepted = metrics.counter("command.ok")
    return {
        "commands": {
            "total": total,
            "accepted": accepted,
            "rejected": rejected,
            "reject_ratio": round(rejected / total, 6) if total else 0.0,
        },
        "audit": audit_stats.describe(),
        "confirmations": dict(tickets_summary),
        "metrics": metrics.summary(),
    }
