"""Shared security input validation limits."""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse


class SecurityValidationError(ValueError):
    """Raised when an input crosses a security boundary."""


class RequestBodyLimitExceeded(SecurityValidationError):
    """Raised while streaming a request body beyond the configured bound."""


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{1,159}$")


def validate_identifier(value: str, *, label: str = "Identifier") -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise SecurityValidationError(f"{label} is invalid")
    return value


def validate_request_size(content_length: str | None, maximum: int) -> None:
    if content_length is None:
        return
    try:
        size = int(content_length)
    except ValueError as exc:
        raise SecurityValidationError("Content-Length is invalid") from exc
    if size < 0 or size > maximum:
        raise RequestBodyLimitExceeded("Request body exceeds the configured limit")


def validate_outbound_https_url(value: str, *, label: str = "Outbound URL") -> str:
    """Validate a server-configured HTTPS endpoint without enabling arbitrary fetches."""

    if not isinstance(value, str) or len(value) > 2_048:
        raise SecurityValidationError(f"{label} is invalid")
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
        raise SecurityValidationError(f"{label} must be an HTTPS URL without credentials")
    if parsed.fragment:
        raise SecurityValidationError(f"{label} must not contain a fragment")
    if parsed.port not in (None, 443):
        raise SecurityValidationError(f"{label} uses an unsupported port")
    blocked_names = {
        "localhost",
        "metadata.google.internal",
        "metadata",
        "instance-data.ec2.internal",
    }
    if hostname in blocked_names or hostname.endswith(".localhost"):
        raise SecurityValidationError(f"{label} targets a blocked host")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
        or str(address) == "169.254.169.254"
    ):
        raise SecurityValidationError(f"{label} targets a private or link-local address")
    return value.rstrip("/") + "/"


def bounded_mapping(value: Any, *, max_items: int = 40) -> dict[str, Any]:
    if not isinstance(value, dict) or len(value) > max_items:
        raise SecurityValidationError("Object exceeds the configured item limit")
    return value


__all__ = [
    "RequestBodyLimitExceeded",
    "SecurityValidationError",
    "bounded_mapping",
    "validate_identifier",
    "validate_outbound_https_url",
    "validate_request_size",
]
