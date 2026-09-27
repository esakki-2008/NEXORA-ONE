import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AgentsPage } from "./pages/AgentsPage";
import { BusinessHealthPage } from "./pages/BusinessHealthPage";
import { CommandCenterPage } from "./pages/CommandCenterPage";
import { EvidencePage } from "./pages/EvidencePage";
import { HistoryPage } from "./pages/HistoryPage";
import { IncidentDetailPage } from "./pages/IncidentDetailPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { InvestigationDetailPage } from "./pages/InvestigationDetailPage";
import { InvestigationPage } from "./pages/InvestigationPage";
import { OperationsDomainPage } from "./pages/OperationsDomainPage";
import { OperationsPage } from "./pages/OperationsPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { ReportDetailPage } from "./pages/ReportDetailPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { VerificationPage } from "./pages/VerificationPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/command-center" replace />} />
        <Route path="/command-center" element={<CommandCenterPage />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/incidents/:incidentId" element={<IncidentDetailPage />} />
        <Route path="/business-health" element={<BusinessHealthPage />} />
        <Route path="/operations" element={<OperationsPage />} />
        <Route path="/operations/:domain" element={<OperationsDomainPage />} />
        <Route path="/investigation" element={<InvestigationPage />} />
        <Route path="/investigation/:incidentId" element={<InvestigationDetailPage />} />
        <Route path="/evidence" element={<EvidencePage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/remediation" element={<PlaceholderPage eyebrow="ACTION / REMEDIATION" title="Remediation" description="Approval-gated remediation plans and controlled actions will appear here after their action phase." phase="PHASE 7" />} />
        <Route path="/verification" element={<VerificationPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/reports/:incidentId" element={<ReportDetailPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<PlaceholderPage eyebrow="NOT FOUND" title="Workspace surface not found" description="Use the navigation to return to a registered NEXORA surface." phase="FOUNDATION" path="/command-center" />} />
      </Route>
    </Routes>
  );
}
