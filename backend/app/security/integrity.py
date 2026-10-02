"""Generic tamper-evident hashing helpers used by security records."""

from __future__ import annotations

import hashlib
import json
from typing import Any


class IntegrityError(RuntimeError):
    """Raised when a signed or chained record is no longer authentic."""


def canonical_hash(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def chain_hash(payload: Any, previous_hash: str) -> str:
    return canonical_hash({"previous_hash": previous_hash, "payload": payload})


__all__ = ["IntegrityError", "canonical_hash", "chain_hash"]
