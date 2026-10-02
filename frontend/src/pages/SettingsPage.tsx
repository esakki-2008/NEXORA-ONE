import { useCallback, useState } from "react";

import { getAIHealth, testAI as verifyAI } from "../api/ai";
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
import type { AIHealthResponse, AITestResponse, HealthResponse, ScenarioSummary } from "../types";

interface SettingsData {
  health: HealthResponse;
  aiHealth: AIHealthResponse;
  scenarios: ScenarioSummary[];
}

export function SettingsPage() {
  const [testResult, setTestResult] = useState<AITestResponse | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);
  const loader = useCallback(async (): Promise<SettingsData> => {
    const [health, aiHealth, scenarios] = await Promise.all([
      getHealth(),
      getAIHealth(),
      listScenarioSummaries()
    ]);
    return { health, aiHealth, scenarios };
  }, []);
  const { data, isLoading, error, reload } = useAsyncData(loader);

  async function verifyProvider() {
    setTestLoading(true);
    setTestError(null);
    try {
      const result = await verifyAI();
      setTestResult(result);
      await reload();
    } catch (requestError) {
      setTestError(requestError instanceof Error ? requestError.message : "AI verification request failed");
    } finally {
      setTestLoading(false);
    }
  }

  if (isLoading && !data) return <LoadingState label="Loading system settings…" rows={4} />;
  if (error && !data) return <ErrorState title="Settings sources unavailable" description={error} onRetry={reload} />;
  if (!data) return null;

  const aiLabel = data.aiHealth.verified
    ? "Connected"
    : data.aiHealth.status === "not_configured"
      ? "Not configured"
      : "Not verified";
  const aiClass = aiLabel.toLowerCase().replace(/ /g, "-");

  return (
    <section className="page-section">
      <PageHeader eyebrow="SYSTEM / SETTINGS" title="Settings" description="Configuration visibility for the current local operations workspace. Secrets and provider credentials are never exposed in the frontend." actions={<button className="secondary-button" type="button" onClick={reload} disabled={isLoading}><Icon name="refresh" size={14} /> Refresh status</button>} />
      <div className="settings-grid">
        <Panel><SectionHeading eyebrow="SYSTEM" title="Runtime" /><div className="settings-list"><div><span>Environment</span><StatusBadge value={data.health.environment} label={data.health.environment} /></div><div><span>API status</span><StatusBadge value={data.health.status} label={data.health.status} dot /></div><div><span>API service</span><strong>{data.health.service}</strong></div><div><span>Last health check</span><strong>{new Date(data.health.timestamp).toLocaleString()}</strong></div></div></Panel>
        <Panel>
          <SectionHeading eyebrow="AI" title="Provider boundary" action={<StatusBadge value={aiClass} label={aiLabel} dot />} />
          <div className="settings-callout"><Icon name="shield" size={18} /><div><strong>Nebius Token Factory / NVIDIA Nemotron</strong><p>{data.aiHealth.message} The server retains credentials; this UI receives only safe status.</p></div></div>
          <div className="settings-list"><div><span>AI provider</span><StatusBadge value="nebius" label="Nebius" /></div><div><span>Model</span><strong>{data.aiHealth.model}</strong></div><div><span>Verification</span><strong>{data.aiHealth.verified ? "Real provider response validated" : "No successful provider verification"}</strong></div></div>
          <button className="secondary-button" type="button" onClick={verifyProvider} disabled={testLoading}><Icon name="activity" size={14} /> {testLoading ? "Verifying…" : "Verify provider connection"}</button>
          {testResult ? <div className="inline-alert"><Icon name={testResult.success ? "check" : "incidents"} size={15} /> {testResult.message}</div> : null}
          {testError ? <div className="inline-alert"><Icon name="incidents" size={15} /> {testError}</div> : null}
        </Panel>
        <Panel><SectionHeading eyebrow="SIMULATOR" title="ShopFlow" /><div className="settings-callout"><Icon name="layers" size={18} /><div><strong>Structured simulator ready</strong><p>{data.scenarios.length} scenario definitions are available through the read-only simulator API.</p></div></div><div className="settings-list"><div><span>Fixture source</span><StatusBadge value="ready" label="Ready" dot /></div><div><span>Mutates live incidents</span><strong>No</strong></div></div></Panel>
        <Panel><SectionHeading eyebrow="SECURITY" title="Runtime posture" /><div className="security-list"><div><Icon name="check" size={15} /><span>Frontend contains no provider secrets</span></div><div><Icon name="check" size={15} /><span>Environment-based configuration</span></div><div><Icon name="check" size={15} /><span>Actions remain approval-gated by architecture</span></div><div><Icon name="check" size={15} /><span>Server-side reference authentication and RBAC enabled</span></div></div></Panel>
      </div>
    </section>
  );
}
