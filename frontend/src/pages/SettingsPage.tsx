import { useCallback } from "react";

import { getHealth } from "../api/health";
import { listScenarioSummaries } from "../api/simulator";
import { ErrorState } from "../components/ErrorState";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";
import { SectionHeading } from "../components/SectionHeading";
import { StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import type { HealthResponse, ScenarioSummary } from "../types";

interface SettingsData { health: HealthResponse; scenarios: ScenarioSummary[]; }

export function SettingsPage() {
  const loader = useCallback(async (): Promise<SettingsData> => {
    const [health, scenarios] = await Promise.all([getHealth(), listScenarioSummaries()]);
    return { health, scenarios };
  }, []);
  const { data, isLoading, error, reload } = useAsyncData(loader);
  if (isLoading && !data) return <LoadingState label="Loading system settings…" rows={4} />;
  if (error && !data) return <ErrorState title="Settings sources unavailable" description={error} onRetry={reload} />;
  if (!data) return null;

  return (
    <section className="page-section">
      <PageHeader eyebrow="SYSTEM / SETTINGS" title="Settings" description="Configuration visibility for the current local operations workspace. Secrets and provider credentials are never exposed in the frontend." actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> Refresh status</button>} />
      <div className="settings-grid">
        <Panel><SectionHeading eyebrow="SYSTEM" title="Runtime" /><div className="settings-list"><div><span>Environment</span><StatusBadge value={data.health.environment} label={data.health.environment} /></div><div><span>API status</span><StatusBadge value={data.health.status} label={data.health.status} dot /></div><div><span>API service</span><strong>{data.health.service}</strong></div><div><span>Last health check</span><strong>{new Date(data.health.timestamp).toLocaleString()}</strong></div></div></Panel>
        <Panel><SectionHeading eyebrow="AI" title="Provider boundary" /><div className="settings-callout"><Icon name="shield" size={18} /><div><strong>Not configured in Phase 2</strong><p>Nebius Token Factory and NVIDIA Nemotron remain behind the Phase 3 provider boundary. No provider credential is sent to this UI.</p></div></div><div className="settings-list"><div><span>AI provider</span><StatusBadge value="not-configured" label="Not configured" /></div><div><span>Model</span><strong>Not configured in Phase 2</strong></div></div></Panel>
        <Panel><SectionHeading eyebrow="SIMULATOR" title="ShopFlow" /><div className="settings-callout"><Icon name="layers" size={18} /><div><strong>Structured simulator ready</strong><p>{data.scenarios.length} scenario definitions are available through the read-only simulator API.</p></div></div><div className="settings-list"><div><span>Fixture source</span><StatusBadge value="ready" label="Ready" dot /></div><div><span>Mutates live incidents</span><strong>No</strong></div></div></Panel>
        <Panel><SectionHeading eyebrow="SECURITY" title="Runtime posture" /><div className="security-list"><div><Icon name="check" size={15} /><span>Frontend contains no provider secrets</span></div><div><Icon name="check" size={15} /><span>Environment-based configuration</span></div><div><Icon name="check" size={15} /><span>Actions remain approval-gated by architecture</span></div><div><Icon name="check" size={15} /><span>Authentication is not enabled in Phase 2</span></div></div></Panel>
      </div>
    </section>
  );
}
