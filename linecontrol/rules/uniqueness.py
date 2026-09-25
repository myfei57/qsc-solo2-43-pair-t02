"""Batch uniqueness bookkeeping."""

from dataclasses import dataclass
from typing import Dict, Optional

from ..runtime.errors import DuplicateRejected


@dataclass(frozen=True)
class BatchEntry:
    batch_id: str
    digest: str
    tick: int
    kind: str

    def describe(self) -> dict:
        return {
            "batch": self.batch_id,
            "digest": self.digest,
            "tick": self.tick,
            "kind": self.kind,
        }


class BatchRegistry:
    """A batch identifier may only ever describe one payload."""

    def __init__(self) -> None:
        self._entries: Dict[str, BatchEntry] = {}
        self._conflicts = 0

    @property
    def conflicts(self) -> int:
        return self._conflicts

    def size(self) -> int:
        return len(self._entries)

    def seen(self, batch_id: str) -> bool:
        return batch_id in self._entries

    def entry(self, batch_id: str) -> Optional[BatchEntry]:
        return self._entries.get(batch_id)

    def entries(self) -> Dict[str, BatchEntry]:
        return dict(sorted(self._entries.items()))

    def register(self, batch_id: str, digest: str, tick: int, kind: str) -> BatchEntry:
        if not batch_id:
            raise DuplicateRejected("batch identifier must not be empty")
        existing = self._entries.get(batch_id)
        if existing is not None:
            if existing.digest == digest:
                return existing
            self._conflicts += 1
            raise DuplicateRejected(
                "batch identifier is already bound to a different payload",
                batch=batch_id,
                existing=existing.digest,
                incoming=digest,
            )
        entry = BatchEntry(batch_id=batch_id, digest=digest, tick=tick, kind=kind)
        self._entries[batch_id] = entry
        return entry
