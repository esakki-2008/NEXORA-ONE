"""Security policy defaults and endpoint permission mapping."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.security.models import Permission
from backend.app.security.rate_limit import RateLimitRule


@dataclass(frozen=True, slots=True)
class SecurityPolicy:
    max_request_bytes: int = 256 * 1024
    token_ttl_seconds: int = 900
    cors_origins: tuple[str, ...] = ()
    sensitive_rules: tuple[tuple[str, RateLimitRule], ...] = (
        ("ai", RateLimitRule(5, 60)),
        ("action-create", RateLimitRule(20, 60)),
        ("action-control", RateLimitRule(10, 60)),
        ("verification-retry", RateLimitRule(10, 60)),
        ("recovery", RateLimitRule(5, 60)),
    )

    def rate_rule(self, bucket: str) -> RateLimitRule | None:
        return dict(self.sensitive_rules).get(bucket)

    def permission_for(self, method: str, path: str) -> Permission | None:
        """Return the coarse permission; resource tenant checks happen after routing."""

        if not path.startswith("/api/"):
            return None
        upper = method.upper()
        if path.startswith("/api/security/config"):
            return Permission.MANAGE_SECURITY
        if path.startswith("/api/security/events") or path.startswith("/api/security/integrity"):
            return Permission.VIEW_SECURITY_EVENTS
        if path.startswith("/api/security/session"):
            return None
        if path.startswith("/api/actions"):
            if upper == "GET":
                return (
                    Permission.VIEW_EVIDENCE
                    if path.endswith("/audit")
                    else Permission.VIEW_VERIFICATION
                    if path.endswith("/verification")
                    else Permission.VIEW_INCIDENTS
                )
            if path.endswith("/approve") or path.endswith("/reject"):
                return Permission.APPROVE_ACTION
            if path.endswith("/execute") or path.endswith("/rollback"):
                return Permission.EXECUTE_ACTION
            if path.endswith("/cancel"):
                return Permission.CANCEL_OPERATION
            if path == "/api/actions":
                return Permission.PROPOSE_ACTION
        if path.startswith("/api/verification"):
            if upper == "GET":
                return Permission.VIEW_VERIFICATION
            if path.endswith("/retry"):
                return Permission.RETRY_VERIFICATION
            if path.endswith("/cancel"):
                return Permission.CANCEL_OPERATION
            return Permission.RETRY_VERIFICATION
        if path.startswith("/api/incidents"):
            return Permission.VIEW_INCIDENTS if upper == "GET" else Permission.CREATE_INVESTIGATION
        if path.startswith("/api/evidence"):
            return Permission.VIEW_EVIDENCE
        if path.startswith("/api/investigations"):
            return Permission.VIEW_EVIDENCE if upper == "GET" else Permission.CREATE_INVESTIGATION
        if path.startswith("/api/operations"):
            return Permission.VIEW_OPERATIONS if upper == "GET" else Permission.CREATE_INVESTIGATION
        if path.startswith("/api/orchestrator"):
            if upper == "GET":
                return Permission.VIEW_INCIDENTS
            if "/approvals/" in path and (path.endswith("/approve") or path.endswith("/reject")):
                return Permission.APPROVE_ACTION
            return Permission.CREATE_INVESTIGATION
        if path.startswith("/api/ai"):
            return Permission.VIEW_OPERATIONS if upper == "GET" else Permission.RUN_AI
        if path.startswith("/api/simulator"):
            return Permission.VIEW_OPERATIONS
        return Permission.VIEW_INCIDENTS

    def rate_bucket(self, method: str, path: str) -> str | None:
        upper = method.upper()
        if path.startswith("/api/ai") and upper == "POST":
            return "ai"
        if path == "/api/actions" and upper == "POST":
            return "action-create"
        if path.startswith("/api/actions/") and upper == "POST":
            return "action-control"
        if path.startswith("/api/verification/") and path.endswith("/retry"):
            return "verification-retry"
        if path.startswith("/api/verification/") and "/recovery" in path:
            return "recovery"
        return None


__all__ = ["SecurityPolicy"]
