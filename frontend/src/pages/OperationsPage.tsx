import { useCallback, useState } from "react";

import { getOperationsSnapshot, investigateOperationalSignal } from "../api/operations";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { OperationsCorrelationList } from "../components/OperationsCorrelationList";
import { OperationsDomainHealthGrid } from "../components/OperationsDomainHealthGrid";
import { OperationsImpactPanel } from "../components/OperationsImpactPanel";
import { OperationsPriorityQueue } from "../components/OperationsPriorityQueue";
import { OperationsSignalTable } from "../components/OperationsSignalTable";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime, humanize } from "../lib/format";
import type { OperationalSignal, OperationalSnapshot } from "../types";

const DEMO_SCENARIO = "payment-failure";

interface OperationsData {
  snapshot: OperationalSnapshot | null;
}

export function OperationsPage() {
  const [scenarioId, setScenarioId] = useState<string | undefined>(DEMO_SCENARIO);
  const [investigatingId, setInvestigatingId] = useState<string | null>(null);
  const [investigationMessage, setInvestigationMessage] = useState<string | null>(null);
  const loader = useCallback(async (): Promise<OperationsData> => {
    const snapshot = await getOperationsSnapshot({ scenarioId });
    return { snapshot };
  }, [scenarioId]);
  const { data, isLoading, error, reload } = useAsyncData<OperationsData>(loader);

  const investigate = async (signal: OperationalSignal) => {
    setInvestigatingId(signal.signal_id);
    setInvestigationMessage(null);
    try {
      const launch = await investigateOperationalSignal(signal.signal_id, {
        scenario_id: data?.snapshot?.scenario_id ?? undefined,
        request_id: `operations-ui-${signal.signal_id}-${Date.now()}`,
        auto_handoff: false
      });
      setInvestigationMessage(`${launch.message} Investigation ${launch.investigation_id} is ready for review.`);
    } catch (requestError) {
      setInvestigationMessage(requestError instanceof Error ? requestError.message : "Investigation request failed safely.");
    } finally {
      setInvestigatingId(null);
    }
  };

  if (isLoading && !data) return <LoadingState label="Loading enterprise operations intelligence…" rows={8} />;
  if (error && !data) return <ErrorState title="Operations view is unavailable" description={error} onRetry={reload} />;

  const snapshot = data?.snapshot;

  return (
    <section className="page-section">
      <PageHeader
        eyebrow="MONITOR / PHASE 6 OPERATIONS"
        title="Unified operations"
        description="One operational view across IT, revenue, support, supply chain, contracts, cloud, data, and compliance. Missing sources remain visible as not configured."
        meta={<><Icon name="clock" size={13} /> {snapshot ? `Updated ${formatDateTime(snapshot.timestamp)}` : "No snapshot available"} <span className="meta-separator">·</span> Server-generated intelligence</>}
        actions={
          <div className="operations-header-actions">
            <label className="operations-scenario-select">
              <span className="sr-only">Operations data source</span>
              <select value={scenarioId ?? ""} onChange={(event) => setScenarioId(event.target.value || undefined)}>
                <option value="payment-failure">ShopFlow payment demonstration</option>
                <option value="database-failure">ShopFlow database demonstration</option>
                <option value="latency-spike">ShopFlow latency demonstration</option>
                <option value="bad-deployment">ShopFlow deployment demonstration</option>
                <option value="configuration-mismatch">ShopFlow configuration demonstration</option>
                <option value="">Connected records only</option>
              </select>
            </label>
            <button className="secondary-button" type="button" onClick={reload} disabled={isLoading}>
              <Icon name="refresh" size={14} /> {isLoading ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        }
      />

      {snapshot ? (
        <>
          <div className="operations-source-banner">
            <StatusBadge value={snapshot.simulator ? "simulator" : "connected-source"} label={snapshot.simulator ? "SIMULATED / CONTROLLED DEMONSTRATION" : "Connected source"} dot />
            <span>{snapshot.source.source_name}</span>
            <span className="muted">Refresh ID {snapshot.refresh_id}</span>
          </div>

          <div className="metric-grid metric-grid-command operations-top-metrics">
            <div className="metric-card"><span className="eyebrow">ENTERPRISE STATUS</span><strong>{humanize(snapshot.overall_status)}</strong><span className="muted">Eight-domain posture</span></div>
            <div className="metric-card metric-tone-critical"><span className="eyebrow">CRITICAL SIGNALS</span><strong>{snapshot.critical_signals.length}</strong><span className="muted">Server-selected attention queue</span></div>
            <div className="metric-card metric-tone-warning"><span className="eyebrow">BUSINESS IMPACT</span><strong>{humanize(snapshot.business_impact.impact_level)}</strong><span className="muted">Deterministic calculation</span></div>
            <div className="metric-card metric-tone-info"><span className="eyebrow">CROSS-DOMAIN LINKS</span><strong>{snapshot.cross_domain_correlations.length}</strong><span className="muted">Related signals, not causation</span></div>
          </div>

          <Panel>
            <SectionHeading eyebrow="ENTERPRISE OPERATIONAL STATUS" title="Domain health" description="Health scores are calculated only when an explicit source is available. Simulator sources are labeled on every record." action={<StatusBadge value={snapshot.overall_status} label={humanize(snapshot.overall_status)} dot />} />
            <OperationsDomainHealthGrid domains={snapshot.domains} />
          </Panel>

          <div className="operations-two-column">
            <Panel>
              <SectionHeading eyebrow="CRITICAL SIGNALS" title="Attention queue" description="Signals are informational. Investigate opens the existing Phase 5 workflow and does not execute remediation." />
              <OperationsSignalTable signals={snapshot.critical_signals} onInvestigate={investigate} investigatingId={investigatingId} />
            </Panel>
            <Panel>
              <SectionHeading eyebrow="PRIORITIZATION" title="Priority queue" description="Rankings use deterministic, explainable server factors rather than AI-generated authority." />
              <OperationsPriorityQueue priorities={snapshot.priority_items} />
            </Panel>
          </div>

          {investigationMessage ? <div className="inline-alert operations-action-message"><Icon name="investigation" size={15} /> {investigationMessage}</div> : null}

          <Panel>
            <SectionHeading eyebrow="BUSINESS IMPACT" title="Operational scope" description="Financial and customer values are simulator estimates when the selected source is synthetic; they are not enterprise financial reporting." />
            <OperationsImpactPanel impact={snapshot.business_impact} />
          </Panel>

          <Panel>
            <SectionHeading eyebrow="RELATED SIGNALS" title="Cross-domain correlations" description="Temporal, dependency, and business-impact relationships remain correlations. The server never upgrades them to causation." />
            <OperationsCorrelationList correlations={snapshot.cross_domain_correlations} />
          </Panel>

          <div className="operations-two-column">
            <Panel>
              <SectionHeading eyebrow="RECENT OPERATIONAL EVENTS" title="Observable timeline" description="Recent signal activity from the selected source boundary." />
              <div className="operations-event-list">
                {snapshot.recent_events.length ? snapshot.recent_events.slice(0, 8).map((event) => (
                  <div className="operations-event-row" key={event.event_id}>
                    <span className="operations-event-marker" />
                    <div><strong>{event.summary}</strong><span>{event.event_type} · {formatDateTime(event.timestamp)}</span></div>
                  </div>
                )) : <EmptyState compact title="No recent events" description="The connected sources returned no recent operational events." />}
              </div>
            </Panel>
            <Panel>
              <SectionHeading eyebrow="SOURCE STATUS" title="Data boundaries" description="Unavailable domain sources are not converted into zeroes or healthy scores." />
              <div className="operations-source-list">
                {snapshot.source_status.map((source) => (
                  <div className="operations-source-row" key={source.domain}>
                    <div><strong>{source.domain}</strong><span>{source.source_name}</span></div>
                    <StatusBadge value={source.status} label={source.status === "AVAILABLE" && source.simulator ? "SIMULATED" : humanize(source.status)} dot />
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </>
      ) : (
        <Panel>
          <EmptyState eyebrow="SOURCE BOUNDARY" title="No operations snapshot available" description="NEXORA did not receive a valid server-generated operations snapshot. No operational numbers are inferred." action={<button className="secondary-button" type="button" onClick={reload}>Retry snapshot</button>} />
        </Panel>
      )}
    </section>
  );
}
