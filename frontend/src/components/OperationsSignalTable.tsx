import { formatDateTime, humanize } from "../lib/format";
import type { OperationalSignal } from "../types";
import { StatusBadge } from "./StatusBadge";

interface OperationsSignalTableProps {
  signals: OperationalSignal[];
  onInvestigate?: (signal: OperationalSignal) => void;
  investigatingId?: string | null;
}

export function OperationsSignalTable({ signals, onInvestigate, investigatingId }: OperationsSignalTableProps) {
  if (!signals.length) {
    return <div className="operations-empty-row">No critical or active operational signals are available from the selected sources.</div>;
  }

  return (
    <div className="operations-table-wrap">
      <table className="operations-table operations-signal-table">
        <thead>
          <tr>
            <th>Signal</th>
            <th>Domain</th>
            <th>Severity / priority</th>
            <th>Observed</th>
            <th>Source</th>
            {onInvestigate ? <th>Next step</th> : null}
          </tr>
        </thead>
        <tbody>
          {signals.map((signal) => (
            <tr key={signal.signal_id}>
              <td>
                <strong>{signal.title}</strong>
                <span className="table-subtext">{signal.summary}</span>
              </td>
              <td><span className="operations-domain-code">{signal.domain}</span></td>
              <td>
                <div className="operations-badge-stack">
                  <StatusBadge value={signal.severity} label={humanize(signal.severity)} dot />
                  <StatusBadge value={signal.priority} label={signal.priority} />
                </div>
              </td>
              <td><span className="muted">{formatDateTime(signal.observed_at)}</span></td>
              <td>
                <span className={signal.simulator ? "source-label source-simulator" : "source-label"}>
                  {signal.simulator ? "SIMULATED / CONTROLLED DEMONSTRATION" : signal.source.source_name}
                </span>
              </td>
              {onInvestigate ? (
                <td>
                  <button
                    className="table-action-button"
                    type="button"
                    disabled={investigatingId === signal.signal_id}
                    onClick={() => onInvestigate(signal)}
                  >
                    {investigatingId === signal.signal_id ? "Opening…" : "Investigate"}
                  </button>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
