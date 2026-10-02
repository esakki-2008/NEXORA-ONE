"""Server-side permission and resource authorization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.security.models import Permission, Principal
from backend.app.security.permissions import permissions_for


class AuthorizationError(PermissionError):
    """Raised when an authenticated principal lacks a required permission."""


class TenantAccessError(PermissionError):
    """Raised when a principal crosses a tenant boundary."""


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    reason: str


class AuthorizationService:
    """Evaluate RBAC and tenant ownership independently of the frontend."""

    def authorize(self, principal: Principal, permission: Permission) -> AuthorizationDecision:
        if permission in permissions_for(principal.roles):
            return AuthorizationDecision(True, "Permission granted by server role policy")
        return AuthorizationDecision(False, f"Role policy denied permission {permission.value}")

    def require(self, principal: Principal, permission: Permission) -> None:
        decision = self.authorize(principal, permission)
        if not decision.allowed:
            raise AuthorizationError(decision.reason)

    def same_tenant(self, principal: Principal, tenant_id: str) -> bool:
        return principal.tenant_id == tenant_id

    def require_tenant(self, principal: Principal, tenant_id: str) -> None:
        if not self.same_tenant(principal, tenant_id):
            raise TenantAccessError("Resource is outside the authenticated tenant")

    def require_resource(self, principal: Principal, resource: Any) -> None:
        tenant_id = getattr(resource, "tenant_id", None)
        if not isinstance(tenant_id, str):
            raise TenantAccessError("Resource has no server-owned tenant binding")
        self.require_tenant(principal, tenant_id)


__all__ = [
    "AuthorizationDecision",
    "AuthorizationError",
    "AuthorizationService",
    "TenantAccessError",
]
