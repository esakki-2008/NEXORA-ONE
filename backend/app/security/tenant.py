"""Tenant identifiers and resource-scope utilities."""

from __future__ import annotations

import re
from typing import Any

from backend.app.security.models import TENANT_ID_PATTERN, Principal

DEFAULT_TENANT_ID = "reference-tenant"
_TENANT_RE = re.compile(TENANT_ID_PATTERN)


class TenantValidationError(ValueError):
    """Raised when a tenant identifier is malformed or client-controlled."""


def validate_tenant_id(value: str) -> str:
    candidate = value.strip()
    if not _TENANT_RE.fullmatch(candidate):
        raise TenantValidationError("Tenant identifier is invalid")
    return candidate


def tenant_of(resource: Any) -> str | None:
    value = getattr(resource, "tenant_id", None)
    return value if isinstance(value, str) else None


def assert_tenant(principal: Principal, resource: Any) -> None:
    tenant_id = tenant_of(resource)
    if tenant_id is None or tenant_id != principal.tenant_id:
        raise TenantValidationError("Resource is outside the authenticated tenant")


__all__ = [
    "DEFAULT_TENANT_ID",
    "TenantValidationError",
    "assert_tenant",
    "tenant_of",
    "validate_tenant_id",
]
