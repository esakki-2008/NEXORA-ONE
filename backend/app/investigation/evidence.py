"""Evidence provenance and normalization for bounded read-only collection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.app.investigation.context import (
    EvidenceCollectionStatus,
    EvidenceRecord,
    InvestigationEvidenceType,
)
from backend.app.models.enums import EvidenceType
from backend.app.tools.contracts import ToolExecutionResult, ToolExecutionStatus

_TYPE_MAP: dict[str, InvestigationEvidenceType] = {
    "log": InvestigationEvidenceType.LOG,
    "metric": InvestigationEvidenceType.METRIC,
    "deployment": InvestigationEvidenceType.DEPLOYMENT,
    "configuration": InvestigationEvidenceType.CONFIGURATION,
    "health_check": InvestigationEvidenceType.HEALTH_CHECK,
    "transaction": InvestigationEvidenceType.TRANSACTION,
    "document": InvestigationEvidenceType.DOCUMENTATION,
    "documentation": InvestigationEvidenceType.DOCUMENTATION,
    "test": InvestigationEvidenceType.TEST_RESULT,
    "test_result": InvestigationEvidenceType.TEST_RESULT,
    "alert": InvestigationEvidenceType.ALERT,
    "customer_signal": InvestigationEvidenceType.CUSTOMER_SIGNAL,
    "system_event": InvestigationEvidenceType.SYSTEM_EVENT,
}

_DOMAIN_TYPE_MAP: dict[InvestigationEvidenceType, EvidenceType] = {
    InvestigationEvidenceType.LOG: EvidenceType.LOG,
    InvestigationEvidenceType.METRIC: EvidenceType.METRIC,
    InvestigationEvidenceType.DEPLOYMENT: EvidenceType.DEPLOYMENT,
    InvestigationEvidenceType.CONFIGURATION: EvidenceType.CONFIGURATION,
    InvestigationEvidenceType.HEALTH_CHECK: EvidenceType.HEALTH_CHECK,
    InvestigationEvidenceType.TRANSACTION: EvidenceType.TRANSACTION,
    InvestigationEvidenceType.DOCUMENTATION: EvidenceType.DOCUMENTATION,
    InvestigationEvidenceType.TEST_RESULT: EvidenceType.TEST_RESULT,
    InvestigationEvidenceType.ALERT: EvidenceType.ALERT,
    InvestigationEvidenceType.CUSTOMER_SIGNAL: EvidenceType.CUSTOMER_SIGNAL,
    InvestigationEvidenceType.SYSTEM_EVENT: EvidenceType.SYSTEM_EVENT,
}


class EvidenceNormalizationError(ValueError):
    """Raised when a controlled tool returns unusable evidence metadata."""


class EvidenceNormalizer:
    """Convert controlled tool evidence into a provenance-preserving contract."""

    def normalize_result(
        self,
        result: ToolExecutionResult,
        *,
        incident_id: UUID,
        collected_by: str,
        simulated: bool,
    ) -> list[EvidenceRecord]:
        if result.status is not ToolExecutionStatus.SUCCESS:
            return []
        normalized: list[EvidenceRecord] = []
        for raw in result.evidence:
            normalized.append(
                self.normalize_item(
                    raw,
                    incident_id=incident_id,
                    collected_by=collected_by,
                    tool_name=result.tool_name,
                    execution_id=str(result.execution_id),
                    simulated=simulated,
                )
            )
        return normalized

    def normalize_item(
        self,
        raw: dict[str, Any],
        *,
        incident_id: UUID,
        collected_by: str,
        tool_name: str,
        execution_id: str,
        simulated: bool,
    ) -> EvidenceRecord:
        evidence_id = str(raw.get("id", "")).strip()
        source = str(raw.get("source", "")).strip()
        summary = str(raw.get("summary", "")).strip()
        if not evidence_id or not source or not summary:
            raise EvidenceNormalizationError("Controlled evidence is missing provenance fields")
        raw_type = str(raw.get("type", "system_event")).strip().lower()
        evidence_type = _TYPE_MAP.get(raw_type)
        if evidence_type is None:
            raise EvidenceNormalizationError(f"Unsupported evidence type {raw_type!r}")
        source_label = f"SIMULATED / CONTROLLED DEMONSTRATION · {source}" if simulated else source
        raw_reference = self._safe_reference(raw.get("raw_reference"))
        raw_reference.setdefault("execution_id", execution_id)
        raw_reference.setdefault("tool_name", tool_name)
        relevance = self._bounded_float(raw.get("relevance", 0.5))
        confidence = self._confidence_for(evidence_type, raw)
        metadata = {
            "tool_name": tool_name,
            "execution_id": execution_id,
            "simulated": str(simulated).lower(),
            "service": self._service_from_source(source),
        }
        if raw.get("status") is not None:
            metadata["source_status"] = str(raw["status"])
        return EvidenceRecord(
            evidence_id=evidence_id,
            incident_id=incident_id,
            source=source_label,
            evidence_type=evidence_type,
            timestamp=self._timestamp(raw.get("timestamp")),
            summary=summary,
            raw_reference=raw_reference,
            relevance=relevance,
            confidence=confidence,
            collected_by=collected_by,
            collection_status=EvidenceCollectionStatus.COLLECTED,
            metadata=metadata,
            simulated=simulated,
        )

    @staticmethod
    def _safe_reference(value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        # References are identifiers only. Values are stringified and bounded;
        # raw log payloads and possible secrets never enter the public context.
        return {
            str(key)[:80]: str(item)[:300]
            for key, item in value.items()
            if isinstance(key, (str, int)) and item is not None
        }

    @staticmethod
    def _timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
            except ValueError as exc:
                raise EvidenceNormalizationError("Evidence timestamp is invalid") from exc
        raise EvidenceNormalizationError("Evidence timestamp is missing")

    @staticmethod
    def _bounded_float(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.5

    @staticmethod
    def _confidence_for(evidence_type: InvestigationEvidenceType, raw: dict[str, Any]) -> float:
        if evidence_type in {
            InvestigationEvidenceType.LOG,
            InvestigationEvidenceType.METRIC,
            InvestigationEvidenceType.DEPLOYMENT,
            InvestigationEvidenceType.CONFIGURATION,
        }:
            return 0.9
        if raw.get("status") in {"PASS", "healthy", "HEALTHY"}:
            return 0.85
        return 0.75

    @staticmethod
    def _service_from_source(source: str) -> str:
        if "/" in source:
            return source.split("/", 1)[1].strip()
        return source


def domain_evidence_type(evidence_type: InvestigationEvidenceType) -> EvidenceType:
    """Map Phase 5 evidence to the legacy incident evidence contract."""

    return _DOMAIN_TYPE_MAP[evidence_type]


__all__ = ["EvidenceNormalizationError", "EvidenceNormalizer", "domain_evidence_type"]
