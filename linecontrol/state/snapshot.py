"""Snapshot the replayed state and resume from it after a restart."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..store.snapshot import (
    SnapshotPayload,
    read_snapshot,
    validate_against_log,
    write_snapshot,
)
from .projection import MachineState, StateProjector


@dataclass(frozen=True)
class RestoreResult:
    state: MachineState
    snapshot: Optional[SnapshotPayload]
    replayed: int
    from_snapshot: bool

    def describe(self) -> dict:
        return {
            "from_snapshot": self.from_snapshot,
            "snapshot_watermark": self.snapshot.watermark if self.snapshot else 0,
            "replayed": self.replayed,
            "state": self.state.describe(),
        }


class StateSnapshotter:
    """A snapshot narrows the replay window; it never replaces the log."""

    def __init__(self, log, audit_log, clock, registry, path: Path) -> None:
        self._log = log
        self._audit = audit_log
        self._clock = clock
        self._registry = registry
        self._path = Path(path)
        self._projector = StateProjector(log)

    @property
    def path(self) -> Path:
        return self._path

    def capture(self) -> SnapshotPayload:
        return SnapshotPayload(
            watermark=self._log.watermark,
            generation=self._registry.revision,
            tick=self._clock.tick,
            machines=self._projector.replay().describe(),
            audit_watermark=self._audit.watermark,
        )

    def write(self) -> Path:
        return write_snapshot(self._path, self.capture())

    def restore(self) -> RestoreResult:
        snapshot = read_snapshot(self._path) if self._path.exists() else None
        if snapshot is None:
            state = self._projector.replay()
            return RestoreResult(state=state, snapshot=None, replayed=state.records_applied, from_snapshot=False)
        validate_against_log(snapshot, self._log)
        base = MachineState.from_mapping(snapshot.machines)
        state = self._projector.replay(start_seq=snapshot.watermark, base=base)
        replayed = state.records_applied - int(snapshot.machines.get("records_applied", 0))
        return RestoreResult(state=state, snapshot=snapshot, replayed=max(replayed, 0), from_snapshot=True)
