import { humanize } from "../lib/format";
import type { PriorityItem } from "../types";
import { StatusBadge } from "./StatusBadge";

export function OperationsPriorityQueue({ priorities }: { priorities: PriorityItem[] }) {
  if (!priorities.length) {
    return <div className="operations-empty-row">No priority items are available from connected operational sources.</div>;
  }

  return (
    <div className="operations-priority-list">
      {priorities.slice(0, 12).map((item, index) => (
        <article className="operations-priority-row" key={item.priority_id}>
          <span className="operations-priority-rank">{String(index + 1).padStart(2, "0")}</span>
          <div className="operations-priority-copy">
            <strong>{item.title}</strong>
            <span>{item.domain} · deterministic score {item.score.toFixed(2)}</span>
          </div>
          <StatusBadge value={item.priority} label={humanize(item.priority)} dot />
        </article>
      ))}
    </div>
  );
}
