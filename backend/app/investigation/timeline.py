"""Auditable investigation timeline events."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from backend.app.investigation.context import InvestigationContext, InvestigationTimelineEvent


class InvestigationTimeline:
    """Append concise operational events; no prompts or private reasoning are stored."""

    @staticmethod
    def record(
        context: InvestigationContext,
        event_type: str,
        summary: str,
        *,
        actor: str = "investigation_engine",
        evidence_ids: Iterable[str] = (),
        status: str = "RECORDED",
    ) -> InvestigationTimelineEvent:
        event = InvestigationTimelineEvent(
            incident_id=context.incident_id,
            event_type=event_type,
            actor=actor,
            summary=summary,
            related_evidence_ids=list(evidence_ids),
            status=status,
        )
        context.timeline.append(event)
        context.timeline = context.timeline[-500:]
        return event

    @staticmethod
    def event_for(
        context: InvestigationContext, event_id: UUID
    ) -> InvestigationTimelineEvent | None:
        return next((item for item in context.timeline if item.event_id == event_id), None)


__all__ = ["InvestigationTimeline"]
