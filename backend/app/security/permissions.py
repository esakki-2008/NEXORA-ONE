"""Explicit role-to-permission mapping for the reference RBAC boundary."""

from __future__ import annotations

from backend.app.security.models import Permission, SecurityRole

ROLE_PERMISSIONS: dict[SecurityRole, frozenset[Permission]] = {
    SecurityRole.VIEWER: frozenset(
        {
            Permission.VIEW_INCIDENTS,
            Permission.VIEW_EVIDENCE,
            Permission.VIEW_OPERATIONS,
            Permission.VIEW_VERIFICATION,
            Permission.VIEW_REPORTS,
        }
    ),
    SecurityRole.OPERATOR: frozenset(
        {
            Permission.VIEW_INCIDENTS,
            Permission.VIEW_EVIDENCE,
            Permission.VIEW_OPERATIONS,
            Permission.VIEW_VERIFICATION,
            Permission.VIEW_REPORTS,
            Permission.CREATE_INVESTIGATION,
            Permission.COLLECT_EVIDENCE,
            Permission.PROPOSE_ACTION,
            Permission.EXECUTE_ACTION,
            Permission.CANCEL_OPERATION,
            Permission.RETRY_VERIFICATION,
            Permission.RUN_AI,
        }
    ),
    SecurityRole.APPROVER: frozenset(
        {
            Permission.VIEW_INCIDENTS,
            Permission.VIEW_EVIDENCE,
            Permission.VIEW_OPERATIONS,
            Permission.VIEW_VERIFICATION,
            Permission.VIEW_REPORTS,
            Permission.REVIEW_ACTION,
            Permission.APPROVE_ACTION,
            Permission.EXECUTE_ACTION,
            Permission.CANCEL_OPERATION,
            Permission.RETRY_VERIFICATION,
            Permission.RUN_AI,
        }
    ),
    SecurityRole.ADMIN: frozenset(Permission),
}


def permissions_for(roles: frozenset[SecurityRole] | set[SecurityRole]) -> frozenset[Permission]:
    result: set[Permission] = set()
    for role in roles:
        result.update(ROLE_PERMISSIONS[role])
    return frozenset(result)


__all__ = ["ROLE_PERMISSIONS", "permissions_for"]
