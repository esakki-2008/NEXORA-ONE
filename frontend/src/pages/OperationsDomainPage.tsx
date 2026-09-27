import { useCallback, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getOperationDomain, investigateOperationalSignal } from "../api/operations";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { OperationsCorrelationList } from "../components/OperationsCorrelationList";
import { OperationsImpactPanel } from "../components/OperationsImpactPanel";
import { OperationsSignalTable } from "../components/OperationsSignalTable";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime, humanize } from "../lib/format";
import type { OperationalSignal, OperationsDomain } from "../types";

const domains: OperationsDomain[] = ["IT", "REVENUE", "SUPPORT", "SUPPLY_CHAIN", "CONTRACTS", "CLOUD", "DATA", "COMPLIANCE"];
const labels: Record<OperationsDomain, string> = {
  IT: "IT Operations",
  REVENUE: "Revenue",
  SUPPORT: "Customer Support",
  SUPPLY_CHAIN: "Supply Chain",
  CONTRACTS: "Contracts",
  CLOUD: "Cloud",
  DATA: "Data",
  COMPLIANCE: "Compliance"
};

export function OperationsDomainPage() {
  const { domain: domainParam } = useParams();
  const domain = useMemo(() => {
    const candidate = domainParam?.toUpperCase() as OperationsDomain | undefined;
    return candidate && domains.includes(candidate) ? candidate : "IT";
  }, [domainParam]);
  const [investigatingId, setInvestigatingId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const loader = useCallback(() => getOperationDomain(domain, { scenarioId: "payment-failure" }), [domain]);
  const { data, isLoading, error, reload } = useAsyncData(loader);

  const investigate = async (signal: OperationalSignal) => {
    setInvestigatingId(signal.signal_id);
    setMessage(null);
    try {
      const launch = await investigateOperationalSignal(signal.signal_id, {
        scenario_id: "payment-failure",
        request_id: `domain-ui-${signal.signal_id}-${Date.now()}`,
        auto_handoff: false
      });
      setMessage(`Investigation ${launch.investigation_id} opened. Remediation remains approval-gated.`);
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "Investigation request failed safely.");
    } finally {
      setInvestigatingId(null);
    }
  };

  if (isLoading && !data) return <LoadingState label={`Loading ${labels[domain]} intelligence…`} rows={7} />;
  if (error && !data) return <ErrorState title="Domain intelligence is unavailable" description={error} onRetry={reload} />;

  return (
    <section className="page-section">
      <PageHeader
        eyebrow={`OPERATIONS / ${domain}`}
        title={labels[domain]}
        description="A domain drill-down assembled from the unified operations snapshot. Related incidents and evidence link back to the existing NEXORA investigation architecture."
        meta={data ? <><Icon name="clock" size={13} /> Updated {data.health.last_updated ? formatDateTime(data.health.last_updated) : "not available"} <span className="meta-separator">·</span> {data.simulator ? "SIMULATED / CONTROLLED DEMONSTRATION" : data.source_status.source_name}</> : null}
        actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> Refresh domain</button>}
      />
      {data ? (
        <>
          <div className="operations-source-banner">
            <StatusBadge value={data.health.status} label={humanize(data.health.status)} dot />
            <span>{data.source_status.message}</span>
            <span className="muted">Source: {data.source_status.source_name}</span>
          </div>
          <div className="metric-grid metric-grid-three operations-top-metrics">
            <div className="metric-card"><span className="eyebrow">DOMAIN STATUS</span><strong>{humanize(data.health.status)}</strong><span className="muted">Server-owned health posture</span></div>
            <div className="metric-card metric-tone-info"><span className="eyebrow">HEALTH SCORE</span><strong>{data.health.health_score === null ? "—" : `${Math.round(data.health.health_score)}%`}</strong><span className="muted">No score when source is missing</span></div>
            <div className="metric-card metric-tone-warning"><span className="eyebrow">ACTIVE SIGNALS</span><strong>{data.health.active_signals.length}</strong><span className="muted">{data.metrics.length} connected metrics</span></div>
          </div>

          <Panel>
            <SectionHeading eyebrow="BUSINESS IMPACT" title="Domain impact context" description="Impact is deterministic and evidence-grounded. Synthetic values remain visibly labeled." />
            <OperationsImpactPanel impact={data.business_impact} />
          </Panel>

          <Panel>
            <SectionHeading eyebrow="SIGNALS" title="Operational signals" description="Use Investigate to create or open a Phase 5 investigation; no action is executed from this surface." />
            <OperationsSignalTable signals={data.signals} onInvestigate={investigate} investigatingId={investigatingId} />
          </Panel>
          {message ? <div className="inline-alert operations-action-message"><Icon name="investigation" size={15} /> {message}</div> : null}

          <div className="operations-two-column">
            <Panel>
              <SectionHeading eyebrow="METRICS" title="Observed metrics" description="Metric units and source metadata are preserved; missing values are not inferred." />
              {data.metrics.length ? (
                <div className="operations-table-wrap"><table className="operations-table"><thead><tr><th>Metric</th><th>Value</th><th>Observed</th></tr></thead><tbody>{data.metrics.map((metric) => <tr key={metric.metric_id}><td><strong>{metric.name}</strong><span className="table-subtext">{metric.source.source_name}</span></td><td className="table-number">{metric.value.toLocaleString(undefined, { maximumFractionDigits: 3 })} <span className="muted">{metric.unit}</span></td><td className="muted">{formatDateTime(metric.observed_at)}</td></tr>)}</tbody></table></div>
              ) : <div className="operations-empty-row">No metrics are connected for this domain.</div>}
            </Panel>
            <Panel>
              <SectionHeading eyebrow="RELATED RECORDS" title="Incidents and evidence" description="These identifiers are references into the existing incident/evidence surfaces." />
              <div className="operations-record-links">
                {data.related_incidents.length ? data.related_incidents.map((incidentId) => <Link to={`/incidents/${incidentId}`} key={incidentId}><span>Incident</span><strong>{incidentId}</strong><Icon name="arrow" size={13} /></Link>) : <span className="operations-empty-row">No related incident record.</span>}
                <div className="operations-evidence-count"><span>Related evidence references</span><strong>{data.related_evidence_ids.length || "None"}</strong></div>
              </div>
            </Panel>
          </div>

          <Panel>
            <SectionHeading eyebrow="CROSS-DOMAIN" title="Related signals" description="Relationships remain correlations and are not presented as causation." />
            <OperationsCorrelationList correlations={data.correlations} />
          </Panel>
          {data.recommended_investigation ? <div className="recommended-step"><span className="eyebrow">NEXT STEP</span><p>{data.recommended_investigation}</p></div> : null}
        </>
      ) : null}
    </section>
  );
}
