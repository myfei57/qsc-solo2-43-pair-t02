"""Snapshot files: the replay starting point for a restart."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from ..runtime import codec
from ..runtime.errors import SnapshotInvalid
from .errors import WatermarkRegression
from .log import AppendOnlyLog


@dataclass(frozen=True)
class SnapshotPayload:
    watermark: int
    generation: int
    tick: int
    machines: Dict[str, Any] = field(default_factory=dict)
    audit_watermark: int = 0

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "watermark": int(self.watermark),
            "generation": int(self.generation),
            "tick": int(self.tick),
            "machines": dict(self.machines),
            "audit_watermark": int(self.audit_watermark),
        }

    def to_line(self) -> str:
        body = self.to_mapping()
        return codec.encode({"payload": body, "digest": codec.digest(body)})

    @classmethod
    def from_line(cls, text: str) -> "SnapshotPayload":
        try:
            raw = codec.decode(text)
        except ValueError as exc:
            raise SnapshotInvalid("snapshot is not valid JSON") from exc
        for key in ("payload", "digest"):
            if key not in raw:
                raise SnapshotInvalid("snapshot is missing a field", field=key)
        body = raw["payload"]
        if not isinstance(body, dict):
            raise SnapshotInvalid("snapshot payload must be an object")
        if codec.digest(body) != raw["digest"]:
            raise SnapshotInvalid("snapshot digest mismatch")
        for key in ("watermark", "generation", "tick"):
            if key not in body:
                raise SnapshotInvalid("snapshot payload is missing a field", field=key)
        machines = body.get("machines", {})
        if not isinstance(machines, dict):
            raise SnapshotInvalid("snapshot machines must be an object")
        return cls(
            watermark=int(body["watermark"]),
            generation=int(body["generation"]),
            tick=int(body["tick"]),
            machines=dict(machines),
            audit_watermark=int(body.get("audit_watermark", 0)),
        )


def write_snapshot(path: Path, payload: SnapshotPayload) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(payload.to_line() + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    return target


def read_snapshot(path: Path) -> SnapshotPayload:
    source = Path(path)
    if not source.exists():
        raise SnapshotInvalid("snapshot file does not exist", path=str(source))
    text = source.read_text(encoding="utf-8").strip()
    if not text:
        raise SnapshotInvalid("snapshot file is empty", path=str(source))
    return SnapshotPayload.from_line(text)


def validate_against_log(payload: SnapshotPayload, log: AppendOnlyLog) -> None:
    """A snapshot may never point past what the log actually holds."""

    tail = log.max_data_seq()
    if payload.watermark > tail:
        raise WatermarkRegression(
            "snapshot watermark is ahead of the record log",
            snapshot=payload.watermark,
            tail=tail,
        )
    if payload.watermark < 0:
        raise SnapshotInvalid("snapshot watermark must not be negative", watermark=payload.watermark)
    if payload.audit_watermark > log.max_seq() and payload.audit_watermark < 0:
        raise SnapshotInvalid("snapshot audit watermark is invalid", audit_watermark=payload.audit_watermark)
