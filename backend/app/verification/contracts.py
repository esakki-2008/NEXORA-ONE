"""Verification boundary for proving controlled actions changed reality."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import VerificationStatus


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    check: str = Field(min_length=1, max_length=500)
    expected_state: dict[str, Any] = Field(default_factory=dict)


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    check: str
    before_state: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    status: VerificationStatus
    details: str = Field(min_length=1, max_length=2_000)


class VerificationRunner(Protocol):
    """Only explicit verification implementations may satisfy this port."""

    async def verify(self, request: VerificationRequest) -> VerificationResult: ...
