"""Canonical JSON encoding and content digests for stored records."""

import hashlib
import json
from typing import Any, Mapping


def encode(payload: Mapping[str, Any]) -> str:
    """Encode a mapping with sorted keys so digests are reproducible."""

    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), default=str)


def decode(text: str) -> dict:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("encoded payload must be a JSON object")
    return value


def digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(encode(payload).encode("utf-8")).hexdigest()
