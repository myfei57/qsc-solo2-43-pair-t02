"""Immutable record shape written to the append only log."""

from dataclasses import dataclass, field
from typing import Any, Dict

from ..runtime import codec
from ..runtime.errors import ValidationError
from .errors import UnknownRecord
from .kinds import KIND_COMMIT, KIND_ROLLBACK, KIND_TOMBSTONE


@dataclass(frozen=True)
class Record:
    """One line of the append only stream."""

    seq: int
    record_id: str
    kind: str
    batch_id: str
    generation: int
    tick: int
    payload: Dict[str, Any] = field(default_factory=dict)
    digest: str = ""
    target: str = ""

    @property
    def is_control(self) -> bool:
        return self.kind in (KIND_COMMIT, KIND_ROLLBACK, KIND_TOMBSTONE)

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "id": self.record_id,
            "kind": self.kind,
            "batch": self.batch_id,
            "gen": self.generation,
            "tick": self.tick,
            "payload": dict(self.payload),
            "digest": self.digest,
            "target": self.target,
        }

    def to_line(self) -> str:
        return codec.encode(self.to_mapping())

    def describe(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "id": self.record_id,
            "kind": self.kind,
            "batch": self.batch_id,
            "generation": self.generation,
            "tick": self.tick,
            "control": self.is_control,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_line(cls, text: str) -> "Record":
        try:
            raw = codec.decode(text)
        except ValueError as exc:
            raise UnknownRecord("record line is not valid JSON", line=text[:80]) from exc
        required = ("seq", "id", "kind", "gen", "tick", "payload", "digest")
        for key in required:
            if key not in raw:
                raise UnknownRecord("record line is missing a field", field=key)
        payload = raw["payload"]
        if not isinstance(payload, dict):
            raise UnknownRecord("record payload must be an object", record_id=raw["id"])
        if codec.digest(payload) != raw["digest"]:
            raise UnknownRecord("record payload digest mismatch", record_id=raw["id"])
        seq = raw["seq"]
        if not isinstance(seq, int) or seq <= 0:
            raise ValidationError("record seq must be a positive integer", seq=seq)
        return cls(
            seq=seq,
            record_id=str(raw["id"]),
            kind=str(raw["kind"]),
            batch_id=str(raw.get("batch", "")),
            generation=int(raw["gen"]),
            tick=int(raw["tick"]),
            payload=dict(payload),
            digest=str(raw["digest"]),
            target=str(raw.get("target", "")),
        )
