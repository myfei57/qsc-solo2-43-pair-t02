"""Failure modes specific to the record store."""

from ..runtime.errors import ControlError, DuplicateRejected, UnknownItem


class StoreError(ControlError):
    """Base class for record store failures."""

    code = "store_error"


class WatermarkRegression(StoreError):
    """The commit watermark would move backwards."""

    code = "watermark_regression"


class UnknownRecord(UnknownItem):
    code = "unknown_record"


class TombstoneConflict(DuplicateRejected):
    code = "tombstone_conflict"
