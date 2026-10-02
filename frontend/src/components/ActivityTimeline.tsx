import { formatShortTime } from "../lib/format";
import type { ActivityEvent, AIActivityEvent } from "../types";
import { EmptyState } from "./EmptyState";
import { Icon } from "./Icon";

interface ActivityTimelineProps {
  events: ActivityEvent[];
  compact?: boolean;
}

function isAIActivityEvent(event: ActivityEvent): event is AIActivityEvent {
  return "provider" in event && "model" in event && "purpose" in event;
}

export function ActivityTimeline({ events, compact = false }: ActivityTimelineProps) {
  if (events.length === 0) {
    return (
      <EmptyState
        compact={compact}
        eyebrow="NO OBSERVABLE EVENTS"
        title="No activity recorded"
        description="Only backend activity is shown here. No AI activity has been generated for this record."
      />
    );
  }

  return (
    <ol className={`activity-timeline${compact ? " activity-timeline-compact" : ""}`}>
      {events.map((event) => (
        <li key={event.id} className="activity-item">
          <span className="activity-marker"><Icon name="activity" size={13} /></span>
          <div className="activity-content">
            <div className="activity-title-row">
              <strong>{event.message}</strong>
              <time dateTime={event.created_at}>{formatShortTime(event.created_at)}</time>
            </div>
            <span className="activity-type">
              {event.event_type}
              {isAIActivityEvent(event) ? ` · ${event.provider} · ${event.model}` : ""}
            </span>
            {isAIActivityEvent(event) ? (
              <span className="activity-context">{event.purpose} · {event.status} · {event.context}</span>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
