"""Integrity checks that a serving instance can answer at any time."""

from pathlib import Path

from ..runtime.errors import ControlError
from ..store.snapshot import read_snapshot, validate_against_log
from .health import HealthCheckResult, HealthReport


class HealthProbe:
    def __init__(self, log, audit_log, snapshot_path: Path) -> None:
        self._log = log
        self._audit = audit_log
        self._snapshot_path = Path(snapshot_path)

    def _store_check(self) -> HealthCheckResult:
        try:
            self._log.validate()
        except ControlError as exc:
            return HealthCheckResult("store.readable", False, exc.to_payload())
        return HealthCheckResult("store.readable", True, self._log.summary())

    def _audit_check(self) -> HealthCheckResult:
        try:
            self._audit.validate()
        except ControlError as exc:
            return HealthCheckResult("audit.readable", False, exc.to_payload())
        return HealthCheckResult("audit.readable", True, self._audit.summary())

    def _watermark_check(self) -> HealthCheckResult:
        watermark = self._log.watermark
        tail = self._log.max_data_seq()
        ok = watermark <= max(tail, self._log.max_seq())
        return HealthCheckResult(
            "store.watermark",
            ok,
            {"watermark": watermark, "tail": tail, "monotone": ok},
        )

    def _snapshot_check(self) -> HealthCheckResult:
        if not self._snapshot_path.exists():
            return HealthCheckResult("snapshot.consistent", True, {"present": False})
        try:
            payload = read_snapshot(self._snapshot_path)
            validate_against_log(payload, self._log)
        except ControlError as exc:
            return HealthCheckResult("snapshot.consistent", False, exc.to_payload())
        return HealthCheckResult(
            "snapshot.consistent",
            True,
            {"present": True, "watermark": payload.watermark, "tick": payload.tick},
        )

    def run(self) -> HealthReport:
        return HealthReport(
            checks=[
                self._store_check(),
                self._audit_check(),
                self._watermark_check(),
                self._snapshot_check(),
            ]
        )
