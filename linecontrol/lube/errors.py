"""Failure modes of the oil circulation subsystem."""

from ..runtime.errors import InterlockLatched


class LatchStillEngaged(InterlockLatched):
    code = "latch_still_engaged"
