"""Application security service and HTTP-boundary helpers."""

from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from backend.app.security.authentication import AuthenticationError, TokenAuthenticator
from backend.app.security.authorization import (
    AuthorizationError,
    AuthorizationService,
    TenantAccessError,
)
from backend.app.security.models import (
    Permission,
    Principal,
    SecurityEvent,
    SecurityEventType,
    SecurityRole,
    SecuritySession,
)
from backend.app.security.policies import SecurityPolicy
from backend.app.security.rate_limit import InMemoryRateLimiter, RateLimitExceeded
from backend.app.security.security_events import SecurityEventStore
from backend.app.security.tenant import validate_tenant_id


class SecurityService:
    """Single server-owned security boundary for auth, policy, rate, and events."""

    def __init__(
        self,
        *,
        auth_secret: SecretStr | str | None = None,
        policy: SecurityPolicy | None = None,
        token_ttl_seconds: int = 900,
    ) -> None:
        self.policy = policy or SecurityPolicy()
        self.authenticator = TokenAuthenticator(
            auth_secret,
            ttl_seconds=token_ttl_seconds,
        )
        self.authorization = AuthorizationService()
        self.rate_limiter = InMemoryRateLimiter()
        self.events = SecurityEventStore()

    def issue_reference_token(
        self,
        *,
        subject: str,
        tenant_id: str,
        roles: set[SecurityRole] | frozenset[SecurityRole],
    ) -> str:
        """Issue a token only to a server-side bootstrap/test caller.

        There is deliberately no unauthenticated token-minting route. A real
        deployment must replace this reference hook with its identity provider.
        """

        return self.authenticator.issue(
            subject=subject,
            tenant_id=validate_tenant_id(tenant_id),
            roles=roles,
            ttl_seconds=self.authenticator.ttl_seconds,
        )

    def authenticate(self, authorization: str | None, *, source: str = "api") -> Principal:
        try:
            return self.authenticator.authenticate(authorization)
        except AuthenticationError as exc:
            self.record_event(
                SecurityEventType.AUTHENTICATION_FAILED,
                actor="anonymous",
                tenant_id="unknown",
                resource="authentication",
                source=source,
                result="DENIED",
                metadata={"reason": str(exc)},
            )
            raise

    def require_permission(self, principal: Principal, permission: Permission) -> None:
        try:
            self.authorization.require(principal, permission)
        except AuthorizationError as exc:
            self.record_event(
                SecurityEventType.AUTHORIZATION_DENIED,
                actor=principal.subject,
                tenant_id=principal.tenant_id,
                resource=permission.value,
                result="DENIED",
                metadata={"reason": str(exc)},
            )
            raise

    def require_actor(self, principal: Principal, supplied_actor: str, *, resource: str) -> None:
        if supplied_actor != principal.subject:
            self.record_event(
                SecurityEventType.AUTHORIZATION_DENIED,
                actor=principal.subject,
                tenant_id=principal.tenant_id,
                resource=resource,
                result="DENIED",
                metadata={"reason": "actor_identity_mismatch"},
            )
            raise AuthorizationError("Actor identity must match the authenticated principal")

    def require_tenant(self, principal: Principal, tenant_id: str, *, resource: str) -> None:
        try:
            self.authorization.require_tenant(principal, tenant_id)
        except TenantAccessError:
            self.record_event(
                SecurityEventType.CROSS_TENANT_ACCESS_DENIED,
                actor=principal.subject,
                tenant_id=principal.tenant_id,
                resource=resource,
                result="DENIED",
                metadata={"target_tenant": tenant_id},
            )
            raise

    def check_rate(self, principal: Principal, method: str, path: str) -> None:
        bucket = self.policy.rate_bucket(method, path)
        if bucket is None:
            return
        rule = self.policy.rate_rule(bucket)
        if rule is None:
            return
        try:
            self.rate_limiter.check(f"{principal.tenant_id}:{principal.subject}:{bucket}", rule)
        except RateLimitExceeded as exc:
            self.record_event(
                SecurityEventType.RATE_LIMIT_EXCEEDED,
                actor=principal.subject,
                tenant_id=principal.tenant_id,
                resource=path,
                result="DENIED",
                metadata={"bucket": bucket, "retry_after": str(exc.retry_after)},
            )
            raise

    def record_event(
        self,
        event_type: SecurityEventType,
        *,
        actor: str,
        tenant_id: str = "unknown",
        resource: str = "unknown",
        source: str = "api",
        result: str = "DENIED",
        metadata: dict[str, Any] | None = None,
    ) -> SecurityEvent:
        return self.events.append(
            event_type=event_type,
            actor=actor,
            tenant_id=tenant_id,
            resource=resource,
            source=source,
            result=result,
            metadata=metadata,
        )

    def session(self, principal: Principal) -> SecuritySession:
        return SecuritySession(
            subject=principal.subject,
            tenant_id=principal.tenant_id,
            roles=principal.roles,
            auth_state=principal.auth_state,
            expires_at=principal.expires_at,
        )


__all__ = ["AuthenticationError", "RateLimitExceeded", "SecurityService"]
