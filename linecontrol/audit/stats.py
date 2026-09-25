"""Aggregates over the audit trail."""

from dataclasses import dataclass, field
from typing import Dict, List

from .journal import AuditEntry


@dataclass(frozen=True)
class AuditStats:
    total: int
    failures: int
    actions: Dict[str, int] = field(default_factory=dict)
    outcomes: Dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 1.0
        return round((self.total - self.failures) / self.total, 6)

    def describe(self) -> dict:
        return {
            "total": self.total,
            "failures": self.failures,
            "success_rate": self.success_rate,
            "actions": dict(self.actions),
            "outcomes": dict(self.outcomes),
        }


def summarize(entries: List[AuditEntry]) -> AuditStats:
    actions: Dict[str, int] = {}
    outcomes: Dict[str, int] = {}
    failures = 0
    for entry in entries:
        actions[entry.action] = actions.get(entry.action, 0) + 1
        outcomes[entry.outcome] = outcomes.get(entry.outcome, 0) + 1
        if not entry.ok:
            failures += 1
    return AuditStats(
        total=len(entries),
        failures=failures,
        actions=dict(sorted(actions.items())),
        outcomes=dict(sorted(outcomes.items())),
    )
