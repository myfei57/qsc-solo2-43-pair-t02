"""Every command leaves one appended audit entry."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..rules.filters import RecordFilter
from ..store.kinds import KIND_AUDIT


@dataclass(frozen=True)
class AuditEntry:
    entry_id: str
    action: str
    actor: str
    outcome: str
    batch_id: str
    tick: int
    detail: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.outcome == "ok"

    def describe(self) -> Dict[str, Any]:
        return {
            "entry": self.entry_id,
            "action": self.action,
            "actor": self.actor,
            "outcome": self.outcome,
            "batch": self.batch_id,
            "tick": self.tick,
            "detail": dict(self.detail),
        }


class AuditJournal:
    def __init__(self, log, clock) -> None:
        self._log = log
        self._clock = clock

    def record(
        self,
        action: str,
        actor: str,
        outcome: str,
        batch_id: str = "",
        detail: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        record = self._log.append(
            KIND_AUDIT,
            batch_id=batch_id,
            generation=0,
            payload={
                "action": action,
                "actor": actor,
                "outcome": outcome,
                "detail": dict(detail or {}),
            },
            tick=self._clock.tick,
        )
        return self._entry(record)

    def commit(self) -> None:
        self._log.commit(tick=self._clock.tick)

    def _entry(self, record) -> AuditEntry:
        payload = record.payload
        return AuditEntry(
            entry_id=record.record_id,
            action=str(payload.get("action", "")),
            actor=str(payload.get("actor", "")),
            outcome=str(payload.get("outcome", "")),
            batch_id=record.batch_id,
            tick=record.tick,
            detail=dict(payload.get("detail", {})),
        )

    def entries(self) -> List[AuditEntry]:
        return [self._entry(record) for record in self._log.visible()]

    def pending(self) -> List[AuditEntry]:
        return [self._entry(record) for record in self._log.pending()]

    def query(self, criteria: RecordFilter) -> List[AuditEntry]:
        selected = criteria.apply(self._log.visible())
        return [self._entry(record) for record in selected]

    def find(self, entry_id: str) -> AuditEntry:
        return self._entry(self._log.find(entry_id))

    def actions(self) -> List[str]:
        return sorted({entry.action for entry in self.entries()})
