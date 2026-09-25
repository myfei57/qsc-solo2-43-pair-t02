"""Query filters shared by the store views and the audit trail."""

from dataclasses import dataclass
from typing import Iterable, List, Tuple


@dataclass(frozen=True)
class RecordFilter:
    """Every field is optional; an empty field does not restrict the result."""

    kinds: Tuple[str, ...] = ()
    batch_id: str = ""
    min_generation: int = -1
    max_generation: int = -1
    since_tick: int = -1
    until_tick: int = -1
    target: str = ""

    def matches(self, record) -> bool:
        if self.kinds and record.kind not in self.kinds:
            return False
        if self.batch_id and record.batch_id != self.batch_id:
            return False
        if self.min_generation >= 0 and record.generation < self.min_generation:
            return False
        if self.max_generation >= 0 and record.generation > self.max_generation:
            return False
        if self.since_tick >= 0 and record.tick < self.since_tick:
            return False
        if self.until_tick >= 0 and record.tick > self.until_tick:
            return False
        if self.target and record.target != self.target:
            return False
        return True

    def apply(self, records: Iterable) -> List:
        return [record for record in records if self.matches(record)]

    def describe(self) -> dict:
        return {
            "kinds": list(self.kinds),
            "batch": self.batch_id,
            "min_generation": self.min_generation,
            "max_generation": self.max_generation,
            "since_tick": self.since_tick,
            "until_tick": self.until_tick,
            "target": self.target,
        }
