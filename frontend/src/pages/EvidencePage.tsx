import { useCallback, useMemo, useState } from "react";

import { getInvestigation, listInvestigations } from "../api/investigations";
import { listIncidentEvidence, listIncidents } from "../api/incidents";
import { getScenario, listScenarioSummaries } from "../api/simulator";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { EvidenceTable, type EvidenceView } from "../components/EvidenceTable";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { formatDateTime, formatUnknown } from "../lib/format";
import type { Evidence, EvidenceRecord, ScenarioFixture } from "../types";

interface EvidenceData {
  records: EvidenceView[];
  scenarioCount: number;
}

function legacyEvidence(incidents: Awaited<ReturnType<typeof listIncidents>>): Promise<EvidenceView[]> {
  return Promise.all(incidents.map(async (incident) => {
    const items = await listIncidentEvidence(incident.id);
    return items.map((item: Evidence): EvidenceView => ({
      id: item.id,
      incidentId: item.incident_id,
      incidentTitle: incident.title,
      type: item.type,
      source: item.source,
      timestamp: item.timestamp,
      summary: item.summary,
      relevance: item.relevance,
      status: "recorded"
    }));
  })).then((groups) => groups.flat());
}

function investigationEvidence(record: EvidenceRecord, title: string): EvidenceView {
  return {
    id: record.evidence_id,
    incidentId: record.incident_id,
    incidentTitle: title,
    type: record.evidence_type,
    source: record.source,
    timestamp: record.timestamp,
    summary: record.summary,
    relevance: record.relevance,
    status: record.simulated ? "simulator" : "recorded",
    confidence: record.confidence,
    collectedBy: record.collected_by,
    collectionStatus: record.collection_status,
    rawReference: record.raw_reference,
    metadata: record.metadata
  };
}

function simulatorEvidence(fixtures: ScenarioFixture[]): EvidenceView[] {
  return fixtures.flatMap((fixture) => [
    ...fixture.state.logs.map((item) => ({ id: `${fixture.scenario_id}-log-${item.id}`, incidentTitle: fixture.incident.title, type: "log", source: `SIMULATED / CONTROLLED DEMONSTRATION · ShopFlow / ${item.service}`, timestamp: item.timestamp, summary: item.message, relevance: null, status: "simulator" as const })),
    ...fixture.state.metrics.map((item) => ({ id: `${fixture.scenario_id}-metric-${item.name}`, incidentTitle: fixture.incident.title, type: "metric", source: `SIMULATED / CONTROLLED DEMONSTRATION · ShopFlow / ${item.service}`, timestamp: item.observed_at, summary: `${item.name}: ${item.value} ${item.unit}`, relevance: null, status: "simulator" as const })),
    ...fixture.state.deployments.map((item) => ({ id: `${fixture.scenario_id}-deployment-${item.id}`, incidentTitle: fixture.incident.title, type: "deployment", source: `SIMULATED / CONTROLLED DEMONSTRATION · ShopFlow / ${item.service}`, timestamp: item.deployed_at, summary: `${item.version} — ${item.change_summary}`, relevance: null, status: "simulator" as const })),
    ...fixture.state.configurations.map((item) => ({ id: `${fixture.scenario_id}-configuration-${item.service}-${item.key}`, incidentTitle: fixture.incident.title, type: "configuration", source: `SIMULATED / CONTROLLED DEMONSTRATION · ShopFlow / ${item.service}`, timestamp: item.updated_at, summary: `${item.key}: ${formatUnknown(item.value)}`, relevance: null, status: "simulator" as const })),
    ...fixture.state.transactions.map((item) => ({ id: `${fixture.scenario_id}-transaction-${item.id}`, incidentTitle: fixture.incident.title, type: "transaction", source: `SIMULATED / CONTROLLED DEMONSTRATION · ShopFlow / ${item.service}`, timestamp: item.timestamp, summary: `${item.status}${item.failure_reason ? ` — ${item.failure_reason}` : ""}`, relevance: null, status: "simulator" as const }))
  ]);
}

async function loadEvidence(): Promise<EvidenceData> {
  const [incidents, summaries, investigations] = await Promise.all([
    listIncidents(),
    listScenarioSummaries(),
    listInvestigations()
  ]);
  const live = await legacyEvidence(incidents);
  const investigationResults = await Promise.allSettled(investigations.map(async (summary) => {
    const context = await getInvestigation(summary.investigation_id);
    return context.evidence.map((item) => investigationEvidence(item, context.incident.title));
  }));
  const investigated = investigationResults.filter((result): result is PromiseFulfilledResult<EvidenceView[]> => result.status === "fulfilled").flatMap((result) => result.value);
  const fixtureResults = await Promise.allSettled(summaries.map((summary) => getScenario(summary.scenario_id)));
  const fixtures = fixtureResults.filter((result): result is PromiseFulfilledResult<ScenarioFixture> => result.status === "fulfilled").map((result) => result.value);
  return { records: [...investigated, ...live, ...simulatorEvidence(fixtures)], scenarioCount: fixtures.length };
}

export function EvidencePage() {
  const loader = useCallback(() => loadEvidence(), []);
  const { data, isLoading, error, reload } = useAsyncData(loader);
  const [query, setQuery] = useState("");
  const [type, setType] = useState("all");
  const [source, setSource] = useState("all");
  const [relevance, setRelevance] = useState("all");
  const [incident, setIncident] = useState("all");
  const [selected, setSelected] = useState<EvidenceView | null>(null);

  const filtered = useMemo(() => {
    const records = data?.records ?? [];
    return records.filter((record) => {
      const matchesQuery = `${record.summary} ${record.source} ${record.incidentTitle ?? ""}`.toLowerCase().includes(query.toLowerCase());
      const matchesRelevance = relevance === "all"
        || (relevance === "unscored" && record.relevance === null)
        || (relevance === "high" && record.relevance !== null && record.relevance >= 0.75)
        || (relevance === "medium" && record.relevance !== null && record.relevance >= 0.4 && record.relevance < 0.75)
        || (relevance === "low" && record.relevance !== null && record.relevance < 0.4);
      return matchesQuery && (type === "all" || record.type === type) && (source === "all" || record.status === source) && matchesRelevance && (incident === "all" || record.incidentTitle === incident);
    });
  }, [data, incident, query, relevance, source, type]);
  const types = [...new Set((data?.records ?? []).map((record) => record.type))].sort();
  const incidents = [...new Set((data?.records ?? []).map((record) => record.incidentTitle).filter((value): value is string => Boolean(value)))].sort();

  if (isLoading && !data) return <LoadingState label="Loading evidence sources…" rows={6} />;
  if (error && !data) return <ErrorState title="Evidence explorer unavailable" description={error} onRetry={reload} />;

  return (
    <section className="page-section">
      <PageHeader eyebrow="INTELLIGENCE / EVIDENCE" title="Evidence explorer" description="Search provenance-preserving incident evidence alongside ShopFlow observations labeled synthetic/demo data. Relevance and confidence are never invented for simulator records." actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> Refresh evidence</button>} />
      <Panel>
        <SectionHeading eyebrow="EVIDENCE LEDGER" title={`${data?.records.length ?? 0} records available`} description={`${data?.scenarioCount ?? 0} ShopFlow simulator fixtures loaded. Recorded investigation evidence includes collection provenance.`} action={<StatusBadge value="source-aware" label="Source-aware" dot />} />
        <div className="filter-bar" aria-label="Evidence filters">
          <label className="filter-search"><Icon name="search" size={15} /><span className="sr-only">Search evidence</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search source, incident, summary" /></label>
          <label><span className="sr-only">Filter by evidence type</span><select value={type} onChange={(event) => setType(event.target.value)}><option value="all">All evidence types</option>{types.map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
          <label><span className="sr-only">Filter by source</span><select value={source} onChange={(event) => setSource(event.target.value)}><option value="all">All sources</option><option value="recorded">Recorded</option><option value="simulator">Simulator</option></select></label>
          <label><span className="sr-only">Filter by relevance</span><select value={relevance} onChange={(event) => setRelevance(event.target.value)}><option value="all">All relevance</option><option value="high">High relevance</option><option value="medium">Medium relevance</option><option value="low">Low relevance</option><option value="unscored">Not scored</option></select></label>
          <label><span className="sr-only">Filter by incident</span><select value={incident} onChange={(event) => setIncident(event.target.value)}><option value="all">All incidents</option>{incidents.map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
        </div>
        {!filtered.length ? <EmptyState title="No evidence matches these filters" description={data?.records.length ? "Adjust the filters to see other available records." : "No evidence is available from the connected sources."} /> : <EvidenceTable records={filtered} onSelect={setSelected} />}
        {selected ? <div className="evidence-detail-panel"><div className="evidence-detail-head"><div><span className="eyebrow">EVIDENCE DETAIL</span><h3>{selected.summary}</h3></div><button className="icon-button" type="button" aria-label="Close evidence detail" onClick={() => setSelected(null)}><Icon name="close" size={15} /></button></div><div className="evidence-detail-grid"><div><span>Source</span><strong>{selected.source}</strong></div><div><span>Collected by</span><strong>{selected.collectedBy ?? "Source record"}</strong></div><div><span>Collected at</span><strong>{formatDateTime(selected.timestamp)}</strong></div><div><span>Collection status</span><strong>{selected.collectionStatus ?? "RECORDED"}</strong></div></div>{selected.metadata ? <div className="evidence-detail-meta"><span className="eyebrow">PROVENANCE METADATA</span><pre>{JSON.stringify(selected.metadata, null, 2)}</pre></div> : null}{selected.rawReference ? <div className="evidence-detail-meta"><span className="eyebrow">RAW REFERENCE</span><pre>{JSON.stringify(selected.rawReference, null, 2)}</pre></div> : null}</div> : null}
      </Panel>
    </section>
  );
}
