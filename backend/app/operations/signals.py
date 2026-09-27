"""Safe construction helpers for bounded operational signals."""

from __future__ import annotations

import re
from datetime import datetime

from backend.app.operations.context import (
    OperationalSignalStatus,
    SourceAvailability,
    SourceMetadata,
    SourceType,
)

_SIMULATOR_LABEL = "SIMULATED / CONTROLLED DEMONSTRATION"


def slug(value: str) -> str:
    """Create a stable, non-executable identifier from an untrusted label."""

    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:100] or "unknown"


def source_metadata(
    *,
    source_type: SourceType,
    source_name: str,
    collected_at: datetime,
    simulator: bool,
    availability: SourceAvailability = SourceAvailability.AVAILABLE,
) -> SourceMetadata:
    return SourceMetadata(
        source_type=source_type,
        source_name=source_name,
        label=_SIMULATOR_LABEL if simulator else source_name,
        collected_at=collected_at,
        availability=availability,
        simulator=simulator,
    )


def evidence_ref(scenario_id: str, kind: str, identifier: str) -> str:
    return f"simulator:{slug(scenario_id)}:{slug(kind)}:{slug(identifier)}"


def signal_is_active(status: OperationalSignalStatus) -> bool:
    return status in {
        OperationalSignalStatus.ACTIVE,
        OperationalSignalStatus.WATCH,
    }


__all__ = [
    "evidence_ref",
    "signal_is_active",
    "slug",
    "source_metadata",
]
