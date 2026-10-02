import { formatShortTime } from "../lib/format";
import type { ActivityEvent } from "../types";
import { EmptyState } from "./EmptyState";
import { Icon } from "./Icon";

interface ActivityTimelineProps {
  events: ActivityEvent[];
  compact?: boolean;
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
            <span className="activity-type">{event.event_type}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}
