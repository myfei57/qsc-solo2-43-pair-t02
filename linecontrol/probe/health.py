"""Health report shapes."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class HealthCheckResult:
    name: str
    ok: bool
    detail: Dict[str, Any] = field(default_factory=dict)

    def describe(self) -> Dict[str, Any]:
        return {"check": self.name, "ok": self.ok, "detail": dict(self.detail)}


@dataclass(frozen=True)
class HealthReport:
    checks: List[HealthCheckResult]

    @property
    def healthy(self) -> bool:
        return all(item.ok for item in self.checks)

    @property
    def status_code(self) -> int:
        return 200 if self.healthy else 503

    def failures(self) -> List[str]:
        return [item.name for item in self.checks if not item.ok]

    def describe(self) -> Dict[str, Any]:
        return {
            "status": "ok" if self.healthy else "degraded",
            "healthy": self.healthy,
            "failed": self.failures(),
            "checks": [item.describe() for item in self.checks],
        }
