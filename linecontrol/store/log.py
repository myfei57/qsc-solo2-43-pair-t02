"""File backed append only log with a monotone commit watermark."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..runtime import codec
from ..runtime.errors import OutOfRange, ValidationError
from ..runtime.ids import IdSequencer
from .errors import StoreError, TombstoneConflict, UnknownRecord, WatermarkRegression
from .kinds import (
    KIND_COMMIT,
    KIND_ROLLBACK,
    KIND_TOMBSTONE,
    require_data_kind,
)
from .records import Record


class AppendOnlyLog:
    """Records are only ever appended; visibility is derived from the watermark."""

    def __init__(self, path: Path, ids: IdSequencer, prefix: str = "REC") -> None:
        self._path = Path(path)
        self._ids = ids
        self._prefix = prefix
        self._records: List[Record] = []
        self._index: Dict[str, Record] = {}
        self._seq = 0
        self._watermark = 0
        self._rollback_floor = -1
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def watermark(self) -> int:
        return self._watermark

    def _load(self) -> None:
        if not self._path.exists():
            return
        text = self._path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            record = Record.from_line(line)
            self._records.append(record)
            self._index[record.record_id] = record
            self._seq = max(self._seq, record.seq)
            if record.kind == KIND_COMMIT:
                self._watermark = max(self._watermark, int(record.payload.get("watermark", 0)))
            elif record.kind == KIND_ROLLBACK:
                self._rollback_floor = int(record.payload.get("to", -1))
        self._ids.seed(self._prefix, self._seq)

    def _write(
        self,
        kind: str,
        batch_id: str,
        generation: int,
        payload: Dict[str, Any],
        tick: int,
        target: str = "",
    ) -> Record:
        seq = self._seq + 1
        record = Record(
            seq=seq,
            record_id=self._ids.next(self._prefix),
            kind=kind,
            batch_id=batch_id,
            generation=int(generation),
            tick=int(tick),
            payload=dict(payload),
            digest=codec.digest(payload),
            target=target,
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(record.to_line() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._records.append(record)
        self._index[record.record_id] = record
        self._seq = seq
        return record

    def append(
        self,
        kind: str,
        batch_id: str = "",
        generation: int = 0,
        payload: Optional[Dict[str, Any]] = None,
        tick: int = 0,
    ) -> Record:
        require_data_kind(kind)
        return self._write(kind, batch_id, generation, payload or {}, tick)

    def commit(self, tick: int = 0) -> Record:
        """Move the watermark up to the highest data record and persist it."""

        watermark = self.max_data_seq()
        record = self._write(KIND_COMMIT, "", 0, {"watermark": watermark}, tick)
        self._watermark = max(self._watermark, watermark)
        return record

    def rollback(self, to_seq: int, reason: str, tick: int = 0) -> Record:
        """Discard the uncommitted tail above ``to_seq``; committed data is untouchable."""

        if to_seq < self._watermark:
            raise WatermarkRegression(
                "rollback target is below the commit watermark",
                target=to_seq,
                watermark=self._watermark,
            )
        if to_seq > self._seq:
            raise OutOfRange("rollback target is past the end of the log", target=to_seq, tail=self._seq)
        dropped = [record for record in self.pending() if record.seq > to_seq]
        record = self._write(
            KIND_ROLLBACK, "", 0, {"to": to_seq, "reason": reason, "dropped": len(dropped)}, tick
        )
        self._rollback_floor = to_seq
        return record

    def tombstone(self, record_id: str, reason: str, tick: int = 0) -> Record:
        target = self.find(record_id)
        if target.is_control:
            raise TombstoneConflict("control records cannot be tombstoned", record_id=record_id)
        if self.tombstone_for(record_id) is not None:
            raise TombstoneConflict("record already carries a tombstone", record_id=record_id)
        record = self._write(
            KIND_TOMBSTONE,
            target.batch_id,
            target.generation,
            {"reason": reason},
            tick,
            target=record_id,
        )
        return record

    def records(self) -> List[Record]:
        return list(self._records)

    def data_records(self) -> List[Record]:
        return [record for record in self._records if not record.is_control]

    def max_seq(self) -> int:
        return self._seq

    def max_data_seq(self) -> int:
        highest = 0
        for record in self._records:
            if not record.is_control and record.seq > highest:
                highest = record.seq
        return highest

    def find(self, record_id: str) -> Record:
        record = self._index.get(record_id)
        if record is None:
            raise UnknownRecord("no such record", record_id=record_id)
        return record

    def tombstone_for(self, record_id: str) -> Optional[Record]:
        for record in self._records:
            if record.kind == KIND_TOMBSTONE and record.target == record_id:
                return record
        return None

    def tombstones(self) -> List[Record]:
        return [record for record in self._records if record.kind == KIND_TOMBSTONE]

    def is_tombstoned(self, record_id: str) -> bool:
        return self.tombstone_for(record_id) is not None

    def _pending_ceiling(self) -> int:
        if self._rollback_floor < 0:
            return self._seq
        return min(self._rollback_floor, self._seq)

    def visible(self) -> List[Record]:
        """Committed, un-tombstoned data records."""

        return [
            record
            for record in self._records
            if not record.is_control
            and record.seq <= self._watermark
            and not self.is_tombstoned(record.record_id)
        ]

    def pending(self) -> List[Record]:
        """Appended but not yet committed data records."""

        ceiling = self._pending_ceiling()
        return [
            record
            for record in self._records
            if not record.is_control
            and self._watermark < record.seq <= ceiling
            and not self.is_tombstoned(record.record_id)
        ]

    def discarded(self) -> List[Record]:
        """Records dropped by a rollback: still on disk, no longer pending or visible."""

        if self._rollback_floor < 0:
            return []
        return [
            record
            for record in self._records
            if not record.is_control
            and record.seq > self._rollback_floor
            and record.seq > self._watermark
            and not self.is_tombstoned(record.record_id)
        ]

    def by_kind(self, kind: str) -> List[Record]:
        return [record for record in self.visible() if record.kind == kind]

    def committed_batch(self, batch_id: str, kind: str = "") -> List[Record]:
        return [
            record
            for record in self.visible()
            if record.batch_id == batch_id and (not kind or record.kind == kind)
        ]

    def is_committed(self, batch_id: str, kind: str = "") -> bool:
        return bool(self.committed_batch(batch_id, kind))

    def validate(self) -> None:
        """Structural self check used by the health probe."""

        previous = 0
        for record in self._records:
            if record.seq <= previous:
                raise StoreError("record sequence is not increasing", record_id=record.record_id)
            previous = record.seq
        if self._watermark > self._seq:
            raise StoreError(
                "commit watermark is past the end of the log",
                watermark=self._watermark,
                tail=self._seq,
            )

    def summary(self) -> Dict[str, Any]:
        return {
            "path": str(self._path),
            "records": len(self._records),
            "data_records": len(self.data_records()),
            "visible": len(self.visible()),
            "pending": len(self.pending()),
            "discarded": len(self.discarded()),
            "tombstones": len(self.tombstones()),
            "watermark": self._watermark,
            "tail": self._seq,
        }
