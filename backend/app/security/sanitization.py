"""Secret-safe sanitization and explicit untrusted-data prompt framing."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any

_SECRET_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[^\s,;]+"),
    re.compile(r"(?i)\b(?:token|secret|password|api[_ -]?key)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----", re.S),
)
_INJECTION_PATTERNS = (
    re.compile(r"(?i)ignore\s+(?:all\s+)?previous\s+instructions"),
    re.compile(r"(?i)disregard\s+(?:the\s+)?(?:system|developer|policy)"),
    re.compile(r"(?i)\b(fake|forged)\s+(?:system|admin|administrator|approval)\b"),
    re.compile(r"(?i)\byou\s+are\s+(?:now\s+)?(?:an?\s+)?(?:admin|administrator|system)\b"),
    re.compile(r"(?i)\b(?:execute|run)\s+(?:a\s+)?(?:shell|command|tool)\b"),
    re.compile(r"(?i)\bapprove\s+(?:this|the)\s+(?:action|request)\b"),
)


def redact_secrets(value: str) -> str:
    result = value
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result[:10_000]


def prompt_injection_detected(value: str) -> bool:
    if any(pattern.search(value) for pattern in _INJECTION_PATTERNS):
        return True
    compact = "".join(value.split())
    if len(compact) >= 24:
        try:
            decoded = base64.b64decode(compact, validate=True).decode("utf-8", errors="ignore")
        except (binascii.Error, ValueError):
            decoded = ""
        if decoded and any(pattern.search(decoded) for pattern in _INJECTION_PATTERNS):
            return True
    return False


def untrusted_data_block(label: str, value: Any) -> str:
    """Serialize evidence as data with policy delimiters; never as instructions."""

    safe_label = redact_secrets(str(label))[:120]
    if isinstance(value, str):
        safe_value = redact_secrets(value)
    else:
        safe_value = redact_secrets(str(value))
    return f"<UNTRUSTED_DATA source={safe_label}>\n{safe_value}\n</UNTRUSTED_DATA>"


def safe_metadata(metadata: dict[str, Any] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in (metadata or {}).items():
        key_text = redact_secrets(str(key))[:120]
        value_text = redact_secrets(str(value))[:500]
        if len(result) >= 30:
            break
        result[key_text] = value_text
    return result


__all__ = ["prompt_injection_detected", "redact_secrets", "safe_metadata", "untrusted_data_block"]
