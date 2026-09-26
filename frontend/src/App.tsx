import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { CommandCenterPage } from "./pages/CommandCenterPage";
import { IncidentDetailPage } from "./pages/IncidentDetailPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/command-center" replace />} />
        <Route path="/command-center" element={<CommandCenterPage />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/incidents/:incidentId" element={<IncidentDetailPage />} />
        <Route path="/investigation" element={<PlaceholderPage eyebrow="INVESTIGATION" title="Investigation workspace" description="Evidence correlation and hypothesis validation will be added after the foundation." phase="PHASE 5" />} />
        <Route path="/evidence" element={<PlaceholderPage eyebrow="EVIDENCE" title="Evidence ledger" description="A traceable evidence surface will connect bounded tools to incidents in a future phase." phase="PHASE 5" />} />
        <Route path="/agents" element={<PlaceholderPage eyebrow="AGENT FABRIC" title="Agent directory" description="Specialist agent registration contracts exist in the backend; live specialists are not enabled yet." phase="PHASE 4" />} />
        <Route path="/operations" element={<PlaceholderPage eyebrow="OPERATIONS" title="Controlled operations" description="Approval-gated actions will appear here only after their tool permissions are implemented." phase="PHASE 6–7" />} />
        <Route path="/verification" element={<PlaceholderPage eyebrow="VERIFICATION" title="Verification center" description="Verification contracts are defined; resolution checks will be wired in a later phase." phase="PHASE 8" />} />
        <Route path="/reports" element={<PlaceholderPage eyebrow="REPORTING" title="Incident reports" description="Report records are modeled, but no report is generated until the investigation workflow exists." phase="PHASE 5" />} />
        <Route path="/settings" element={<PlaceholderPage eyebrow="SYSTEM" title="Settings" description="Environment-based configuration is managed by the backend runtime and local environment files." phase="PHASE 1" />} />
        <Route path="*" element={<PlaceholderPage eyebrow="NOT FOUND" title="Workspace surface not found" description="Use the navigation to return to a registered NEXORA surface." phase="FOUNDATION" />} />
      </Route>
    </Routes>
  );
}
