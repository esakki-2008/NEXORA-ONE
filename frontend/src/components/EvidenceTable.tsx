import { formatPercent, formatShortTime, humanize } from "../lib/format";

export interface EvidenceView {
  id: string;
  incidentId?: string;
  incidentTitle?: string;
  type: string;
  source: string;
  timestamp: string;
  summary: string;
  relevance: number | null;
  status: "recorded" | "simulator";
}

interface EvidenceTableProps {
  records: EvidenceView[];
}

export function EvidenceTable({ records }: EvidenceTableProps) {
  return (
    <div className="table-wrap">
      <table className="data-table evidence-table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Source</th>
            <th>Timestamp</th>
            <th>Summary</th>
            <th>Relevance</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <tr key={record.id}>
              <td><span className="type-label">{humanize(record.type)}</span></td>
              <td><span className="source-label">{record.source}</span>{record.incidentTitle ? <span className="table-subtext">{record.incidentTitle}</span> : null}</td>
              <td className="muted">{formatShortTime(record.timestamp)}</td>
              <td className="evidence-summary">{record.summary}</td>
              <td>{record.relevance === null ? <span className="muted">Not scored</span> : <span className="relevance-value">{formatPercent(record.relevance)}</span>}</td>
              <td><span className={`source-badge source-${record.status}`}>{record.status === "simulator" ? "Simulator" : "Recorded"}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
