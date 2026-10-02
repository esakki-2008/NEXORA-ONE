import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import {
  collectInvestigationEvidence,
  getInvestigationForIncident,
  handoffInvestigation,
  startInvestigation,
  testInvestigationHypothesis
} from "../api/investigations";
import { getIncident } from "../api/incidents";
import { listScenarioSummaries } from "../api/simulator";
import { ActivityTimeline } from "../components/ActivityTimeline";
import { ConfidenceFactors } from "../components/ConfidenceFactors";
import { CorrelationList } from "../components/CorrelationList";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { EvidenceTable, type EvidenceView } from "../components/EvidenceTable";
import { Icon } from "../components/Icon";
import { InvestigationHypothesisCard } from "../components/InvestigationHypothesisCard";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { OrchestrationPanel } from "../components/OrchestrationPanel";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { SeverityBadge, StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime, humanize } from "../lib/format";
import type { ActivityEvent, Incident, InvestigationContext, ScenarioSummary } from "../types";

interface InvestigationData {
  incident: Incident;
  investigation: InvestigationContext | null;
  scenarios: ScenarioSummary[];
}

function isNotStarted(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

function toEvidenceView(context: InvestigationContext): EvidenceView[] {
  return context.evidence.map((item) => ({
    id: item.evidence_id,
    incidentId: item.incident_id,
    incidentTitle: context.incident.title,
    type: item.evidence_type,
    source: item.source,
    timestamp: item.timestamp,
    summary: item.summary,
    relevance: item.relevance,
    status: item.simulated ? "simulator" : "recorded",
    confidence: item.confidence,
    collectedBy: item.collected_by,
    collectionStatus: item.collection_status,
    rawReference: item.raw_reference,
    metadata: item.metadata
  }));
}

function toTimelineEvents(context: InvestigationContext): ActivityEvent[] {
  return context.timeline.map((item) => ({
    id: item.event_id,
    incident_id: item.incident_id,
    event_type: item.event_type,
    message: item.summary,
    created_at: item.timestamp,
    metadata: { actor: item.actor, status: item.status }
  }));
}

async function loadInvestigation(incidentId: string): Promise<InvestigationData> {
  const [incident, scenarios] = await Promise.all([getIncident(incidentId), listScenarioSummaries()]);
  let investigation: InvestigationContext | null = null;
  try {
    investigation = await getInvestigationForIncident(incidentId);
  } catch (error) {
    if (!isNotStarted(error)) throw error;
  }
  return { incident, investigation, scenarios };
}

export function InvestigationDetailPage() {
  const { incidentId } = useParams<{ incidentId: string }>();
  const loader = useCallback(() => {
    if (!incidentId) throw new Error("No incident id was supplied.");
    return loadInvestigation(incidentId);
  }, [incidentId]);
  const { data, isLoading, error, reload } = useAsyncData(loader, [incidentId]);
  const [selectedScenario, setSelectedScenario] = useState("");
  const [localContext, setLocalContext] = useState<InvestigationContext | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const context = localContext ?? data?.investigation ?? null;

  async function runAction(action: () => Promise<InvestigationContext>) {
    setBusy(true);
    setActionError(null);
    try {
      setLocalContext(await action());
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "The investigation request failed.");
    } finally {
      setBusy(false);
    }
  }

  if (isLoading && !data) return <LoadingState label="Loading investigation workspace…" rows={7} />;
  if (error && !data) return <ErrorState title="Investigation record unavailable" description={error} onRetry={reload} />;
  if (!data) return null;

  const evidence = context ? toEvidenceView(context) : [];
  const timeline = context ? toTimelineEvents(context) : [];
  const handoffReady = context?.orchestrator_handoff.status === "READY";

  return (
    <section className="page-section">
      <Link className="back-link" to="/investigation"><Icon name="arrow" size={14} /> Back to investigation queue</Link>
      <PageHeader
        eyebrow={`INVESTIGATION INTELLIGENCE · ${data.incident.id.slice(0, 8)}`}
        title={data.incident.title}
        description="Evidence-driven investigation with provenance, explainable correlations, server-scored hypotheses, and a controlled Phase 4 handoff."
        meta={<><Icon name="clock" size={13} /> Intake received {formatDateTime(data.incident.created_at)}</>}
        actions={<div className="detail-badges"><SeverityBadge severity={data.incident.severity} /><StatusBadge value={context?.status ?? "NOT_STARTED"} label={context ? humanize(context.status) : "Not started"} dot /></div>}
      />
      {actionError ? <div className="inline-alert inline-alert-danger"><Icon name="incidents" size={15} /> {actionError}</div> : null}

      {!context ? (
        <Panel className="investigation-start-panel">
          <SectionHeading eyebrow="INVESTIGATION INTAKE" title="Start an evidence-driven investigation" description="Read-only collection runs through the existing Phase 4 tool registry. Choose a ShopFlow fixture only for a clearly marked controlled demonstration." />
          <div className="investigation-start-controls">
            <label><span className="eyebrow">SOURCE</span><select value={selectedScenario} onChange={(event) => setSelectedScenario(event.target.value)}><option value="">Live incident record</option>{data.scenarios.map((scenario) => <option key={scenario.scenario_id} value={scenario.scenario_id}>{scenario.name} · synthetic demo</option>)}</select></label>
            <button className="primary-button" type="button" disabled={busy} onClick={() => void runAction(() => startInvestigation(data.incident.id, selectedScenario || undefined))}><Icon name="investigation" size={14} /> {busy ? "Investigating…" : "Start investigation"}</button>
          </div>
          <div className="source-note"><Icon name="shield" size={15} /> Evidence is normalized with provenance. The engine does not execute medium/high-risk actions and does not expose private model reasoning.</div>
        </Panel>
      ) : (
        <>
          <div className="investigation-overview-grid">
            <div className="metric-card"><span className="eyebrow">STATUS</span><strong className="metric-text">{humanize(context.status)}</strong><span className="muted">Server-owned lifecycle</span></div>
            <div className="metric-card metric-tone-info"><span className="eyebrow">EVIDENCE</span><strong>{context.evidence.length}</strong><span className="muted">Provenance records</span></div>
            <div className="metric-card"><span className="eyebrow">CORRELATIONS</span><strong>{context.correlations.length}</strong><span className="muted">Explainable relationships</span></div>
            <div className="metric-card"><span className="eyebrow">CONFIDENCE</span><strong>{Math.round(context.confidence * 100)}%</strong><span className="muted">Deterministic server score</span></div>
          </div>
          <div className="investigation-toolbar">
            <div><span className="eyebrow">SOURCE</span><strong>{context.source_type}</strong></div>
            <div><span className="eyebrow">HANDOFF</span><StatusBadge value={context.orchestrator_handoff.status} label={humanize(context.orchestrator_handoff.status)} /></div>
            <div className="investigation-toolbar-actions"><button className="secondary-button" type="button" disabled={busy} onClick={() => void runAction(() => collectInvestigationEvidence(context.investigation_id))}><Icon name="refresh" size={14} /> Collect read-only evidence</button>{handoffReady ? <button className="primary-button" type="button" disabled={busy} onClick={() => void runAction(() => handoffInvestigation(context.investigation_id))}><Icon name="arrow" size={14} /> Hand off to orchestrator</button> : null}</div>
          </div>
          {context.ai_summary ? <div className="investigation-ai-summary"><span className="eyebrow">NEMOTRON SUMMARY</span><p>{context.ai_summary}</p><span className="muted">Structured assist only · {context.ai_status ?? "status unavailable"}</span></div> : null}
          {context.errors.length ? <div className="inline-alert"><Icon name="incidents" size={15} /> {context.errors[context.errors.length - 1]}</div> : null}

          <OrchestrationPanel incidentId={data.incident.id} compact />

          <div className="detail-grid detail-grid-wide">
            <Panel>
              <SectionHeading eyebrow="EVIDENCE LEDGER" title={`${context.evidence.length} normalized records`} description="Every record retains source, collection tool, timestamp, relevance, confidence, and simulator labeling." />
              {evidence.length ? <EvidenceTable records={evidence} /> : <EmptyState title="No evidence collected" description="The engine will not invent evidence when a source is unavailable." />}
            </Panel>
            <Panel>
              <SectionHeading eyebrow="CORRELATION VIEW" title={`${context.correlations.length} explainable relationships`} description="Relationships describe observed alignment; they do not claim causation." />
              <CorrelationList correlations={context.correlations} />
            </Panel>
          </div>

          <div className="detail-grid detail-grid-wide">
            <Panel>
              <SectionHeading eyebrow="HYPOTHESIS LIFECYCLE" title={`${context.hypotheses.length} candidates`} description="Status transitions and confidence are server-controlled. Test probes remain read-only." />
              {context.hypotheses.length ? <div className="investigation-hypothesis-stack">{context.hypotheses.map((hypothesis) => <InvestigationHypothesisCard key={hypothesis.hypothesis_id} hypothesis={hypothesis} busy={busy} onTest={(hypothesisId) => void runAction(() => testInvestigationHypothesis(context.investigation_id, { hypothesis_id: hypothesisId }))} />)}</div> : <EmptyState title="No hypotheses available" description="Hypotheses are generated only from collected evidence." />}
            </Panel>
            <Panel>
              <SectionHeading eyebrow="CONFIDENCE FACTORS" title="Why this score exists" description="Explainable deterministic factors are shown without exposing private model reasoning." />
              <ConfidenceFactors confidence={context.confidence} factors={context.confidence_factors} explanation={context.confidence_explanation} />
            </Panel>
          </div>

          <div className="detail-grid detail-grid-wide">
            <Panel>
              <SectionHeading eyebrow="ROOT-CAUSE CANDIDATES" title="Evidence-grounded candidates" description="Candidates remain qualified as candidates until separately validated." />
              {context.root_cause_candidates.length ? <div className="candidate-list">{context.root_cause_candidates.map((candidate) => <div className="candidate-row" key={candidate.candidate_id}><StatusBadge value="candidate" label="Root-cause candidate" /><div><strong>{candidate.title}</strong><p>{candidate.summary}</p></div><b>{Math.round(candidate.confidence * 100)}%</b></div>)}</div> : <EmptyState compact title="No root-cause candidate" description="Insufficient evidence or unresolved contradictions prevent a safe candidate." />}
              {context.evidence_gaps.length ? <div className="evidence-gap-block"><span className="eyebrow">EVIDENCE GAPS</span><ul>{context.evidence_gaps.map((gap) => <li key={gap}>{gap}</li>)}</ul></div> : null}
              {context.recommended_next_step ? <div className="recommended-step"><span className="eyebrow">RECOMMENDED NEXT STEP</span><p>{context.recommended_next_step}</p></div> : null}
            </Panel>
            <Panel>
              <SectionHeading eyebrow="INVESTIGATION TIMELINE" title="Observable worklog" description="Collection, normalization, correlation, testing, and handoff events only." />
              <ActivityTimeline events={timeline} compact />
            </Panel>
          </div>
        </>
      )}
    </section>
  );
}
