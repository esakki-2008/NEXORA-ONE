"""Deterministic reference authentication using signed bearer sessions.

This is a reference security boundary, not a replacement for an enterprise
identity provider.  Tokens are HMAC signed with a server-only environment
secret and contain only subject, tenant, roles, expiry, and a token id.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from pydantic import SecretStr

from backend.app.security.models import Principal, SecurityRole


class AuthenticationError(ValueError):
    """Raised when a bearer session is absent, malformed, invalid, or expired."""


class TokenAuthenticator:
    """Issue and validate compact HMAC-signed reference bearer tokens."""

    VERSION = "n1"
    MAX_TOKEN_LENGTH = 4_096

    def __init__(self, secret: SecretStr | str | None, *, ttl_seconds: int = 900) -> None:
        if secret is None or not self._secret_value(secret):
            # A missing secret creates an ephemeral server-only secret.  It is
            # intentionally not a credential and invalidates sessions on restart.
            secret_bytes = secrets.token_bytes(32)
        else:
            secret_bytes = self._secret_value(secret).encode("utf-8")
        if len(secret_bytes) < 32:
            raise ValueError("Security authentication secret must be at least 32 bytes")
        if ttl_seconds < 60 or ttl_seconds > 86_400:
            raise ValueError("Security token TTL must be between 60 and 86400 seconds")
        self._secret = secret_bytes
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _secret_value(secret: SecretStr | str) -> str:
        value = secret.get_secret_value() if isinstance(secret, SecretStr) else secret
        return value.strip()

    def issue(
        self,
        *,
        subject: str,
        tenant_id: str,
        roles: set[SecurityRole] | frozenset[SecurityRole],
        ttl_seconds: int | None = None,
    ) -> str:
        now = datetime.now(UTC)
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl < 60 or ttl > 86_400:
            raise ValueError("Security token TTL is outside the allowed bound")
        principal = Principal(
            subject=subject,
            tenant_id=tenant_id,
            roles=frozenset(roles),
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl),
            token_id=uuid4(),
        )
        payload = {
            "v": self.VERSION,
            "sub": principal.subject,
            "tenant": principal.tenant_id,
            "roles": sorted(role.value for role in principal.roles),
            "iat": int(principal.issued_at.timestamp()),
            "exp": int(principal.expires_at.timestamp()),
            "jti": str(principal.token_id),
        }
        encoded = self._encode(payload)
        return f"{self.VERSION}.{encoded}.{self._signature(encoded)}"

    def authenticate(self, authorization: str | None) -> Principal:
        if not authorization:
            raise AuthenticationError("Authentication is required")
        scheme, separator, token = authorization.partition(" ")
        if separator == "" or scheme.lower() != "bearer":
            raise AuthenticationError("Bearer authentication is required")
        if len(token) > self.MAX_TOKEN_LENGTH:
            raise AuthenticationError("Authentication token is too large")
        parts = token.split(".")
        if len(parts) != 3 or parts[0] != self.VERSION:
            raise AuthenticationError("Authentication token is malformed")
        _, encoded, signature = parts
        expected = self._signature(encoded)
        if not hmac.compare_digest(signature, expected):
            raise AuthenticationError("Authentication token is invalid")
        try:
            payload = self._decode(encoded)
            if payload.get("v") != self.VERSION:
                raise AuthenticationError("Authentication token is invalid")
            now = int(datetime.now(UTC).timestamp())
            issued = int(payload["iat"])
            expires = int(payload["exp"])
            if issued > now + 30 or expires <= now or expires - issued > 86_400:
                raise AuthenticationError("Authentication token is expired or invalid")
            roles_raw = payload["roles"]
            if not isinstance(roles_raw, list) or not roles_raw:
                raise AuthenticationError("Authentication token roles are invalid")
            roles = frozenset(SecurityRole(item) for item in roles_raw)
            return Principal(
                subject=str(payload["sub"]),
                tenant_id=str(payload["tenant"]),
                roles=roles,
                issued_at=datetime.fromtimestamp(issued, UTC),
                expires_at=datetime.fromtimestamp(expires, UTC),
                token_id=UUID(str(payload["jti"])),
            )
        except (AuthenticationError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, AuthenticationError):
                raise
            raise AuthenticationError("Authentication token is invalid") from exc

    def fingerprint(self, authorization: str | None) -> str:
        """Return a non-reversible rate-limit key for a supplied token."""

        if not authorization:
            return "anonymous"
        return hashlib.sha256(authorization.encode("utf-8")).hexdigest()[:24]

    def _signature(self, encoded: str) -> str:
        return hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()

    @staticmethod
    def _encode(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode(encoded: str) -> dict[str, Any]:
        padded = encoded + "=" * (-len(encoded) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Token payload is not an object")
        return payload


__all__ = ["AuthenticationError", "TokenAuthenticator"]
