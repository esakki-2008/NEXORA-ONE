"""Snapshot assembly helpers shared by API operations."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime

from backend.app.operations.context import (
    DomainHealth,
    DomainHealthStatus,
    OperationsDomain,
    OperationsSourceStatus,
    SourceAvailability,
    SourceMetadata,
    SourceType,
)
from backend.app.operations.domains import DOMAIN_ORDER
from backend.app.operations.signals import source_metadata


def overall_status(domains: Sequence[DomainHealth]) -> DomainHealthStatus:
    statuses = {item.status for item in domains}
    if DomainHealthStatus.CRITICAL in statuses:
        return DomainHealthStatus.CRITICAL
    if DomainHealthStatus.DEGRADED in statuses:
        return DomainHealthStatus.DEGRADED
    if DomainHealthStatus.WARNING in statuses:
        return DomainHealthStatus.WARNING
    if statuses and statuses <= {DomainHealthStatus.NOT_CONFIGURED}:
        return DomainHealthStatus.NOT_CONFIGURED
    if DomainHealthStatus.UNKNOWN in statuses:
        return DomainHealthStatus.UNKNOWN
    return DomainHealthStatus.HEALTHY


def refresh_id(timestamp: datetime, scenario_id: str | None, incident_id: str | None) -> str:
    raw = f"{timestamp.isoformat()}|{scenario_id or ''}|{incident_id or ''}"
    return f"snapshot:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def not_configured_source(domain: OperationsDomain, timestamp: datetime) -> OperationsSourceStatus:
    source = source_metadata(
        source_type=SourceType.NOT_CONFIGURED,
        source_name="No connected source",
        collected_at=timestamp,
        simulator=False,
        availability=SourceAvailability.NOT_CONFIGURED,
    )
    return OperationsSourceStatus(
        domain=domain,
        source_type=SourceType.NOT_CONFIGURED,
        source_name=source.source_name,
        status=SourceAvailability.NOT_CONFIGURED,
        message="No operational data source is connected for this domain.",
        last_updated=None,
        simulator=False,
        source=source,
    )


def source_is_simulator(source: SourceMetadata) -> bool:
    return source.simulator


def ordered_domains() -> tuple[OperationsDomain, ...]:
    return DOMAIN_ORDER


__all__ = [
    "not_configured_source",
    "ordered_domains",
    "overall_status",
    "refresh_id",
    "source_is_simulator",
]
