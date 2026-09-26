import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { getAIHealth } from "../api/ai";
import { getHealth } from "../api/health";
import { listIncidents } from "../api/incidents";
import type { AIHealthResponse, HealthResponse } from "../types";
import { Icon, type IconName } from "./Icon";
import { StatusBadge } from "./StatusBadge";

interface NavItem {
  label: string;
  path: string;
  icon: IconName;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    label: "MONITOR",
    items: [
      { label: "Incidents", path: "/incidents", icon: "incidents" },
      { label: "Business Health", path: "/business-health", icon: "business" },
      { label: "Operations", path: "/operations", icon: "operations" }
    ]
  },
  {
    label: "INTELLIGENCE",
    items: [
      { label: "Investigation", path: "/investigation", icon: "investigation" },
      { label: "Evidence", path: "/evidence", icon: "evidence" },
      { label: "Agents", path: "/agents", icon: "agents" }
    ]
  },
  {
    label: "ACTION",
    items: [
      { label: "Remediation", path: "/remediation", icon: "remediation" },
      { label: "Verification", path: "/verification", icon: "verification" }
    ]
  },
  {
    label: "REPORTING",
    items: [
      { label: "Reports", path: "/reports", icon: "reports" },
      { label: "History", path: "/history", icon: "history" }
    ]
  },
  {
    label: "SYSTEM",
    items: [{ label: "Settings", path: "/settings", icon: "settings" }]
  }
];

const pageTitles: Record<string, string> = {
  "/command-center": "Command Center",
  "/incidents": "Incidents",
  "/business-health": "Business Health",
  "/operations": "Operations",
  "/investigation": "Investigation",
  "/evidence": "Evidence Explorer",
  "/agents": "Agent Fabric",
  "/remediation": "Remediation",
  "/verification": "Verification",
  "/reports": "Reports",
  "/history": "History",
  "/settings": "Settings"
};

function currentPageTitle(pathname: string): string {
  if (pathname.startsWith("/incidents/")) return "Incident Detail";
  if (pathname.startsWith("/investigation/")) return "Investigation Detail";
  if (pathname.startsWith("/reports/")) return "Report Detail";
  return pageTitles[pathname] ?? "Command Center";
}

export function AppShell() {
  const location = useLocation();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [aiHealth, setAIHealth] = useState<AIHealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [openCount, setOpenCount] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    let active = true;
    setHealthLoading(true);
    Promise.allSettled([getHealth(), getAIHealth()]).then(([healthResult, aiResult]) => {
      if (!active) return;
      setHealth(healthResult.status === "fulfilled" ? healthResult.value : null);
      setAIHealth(aiResult.status === "fulfilled" ? aiResult.value : null);
      setHealthLoading(false);
    });

    listIncidents()
      .then((incidents) => {
        if (!active) return;
        setOpenCount(incidents.filter((incident) => !["resolved", "closed", "cancelled"].includes(incident.status)).length);
      })
      .catch(() => {
        if (active) setOpenCount(null);
      });

    return () => {
      active = false;
    };
  }, [location.pathname]);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const aiStatusLabel = aiHealth?.verified
    ? "AI CONNECTED"
    : healthLoading
      ? "CHECKING AI"
      : aiHealth?.status === "not_configured"
        ? "AI NOT CONFIGURED"
        : aiHealth?.status === "provider_unavailable"
          ? "AI PROVIDER UNAVAILABLE"
          : aiHealth?.status === "authentication_failed"
            ? "AI AUTHENTICATION FAILED"
            : aiHealth?.status === "model_unavailable"
              ? "AI MODEL UNAVAILABLE"
              : "AI NOT VERIFIED";

  const sidebarClass = useMemo(
    () => `sidebar${collapsed ? " sidebar-collapsed" : ""}${mobileOpen ? " sidebar-mobile-open" : ""}`,
    [collapsed, mobileOpen]
  );

  return (
    <div className="app-shell">
      <aside className={sidebarClass} aria-label="NEXORA workspace navigation">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">N</div>
          <div className="brand-copy">
            <div className="brand-name">NEXORA <span>ONE</span></div>
            <div className="brand-caption">OPERATIONS INTELLIGENCE</div>
          </div>
          <button className="sidebar-close mobile-only" type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)}>
            <Icon name="close" size={17} />
          </button>
        </div>

        <div className="sidebar-rule" />
        <nav className="primary-nav" aria-label="Primary navigation">
          <NavLink
            to="/command-center"
            className={({ isActive }) => `nav-item nav-command-item${isActive ? " nav-item-active" : ""}`}
            title="Command Center"
          >
            <span className="nav-icon"><Icon name="command" size={16} /></span>
            <span className="nav-item-label">Command Center</span>
          </NavLink>
          {navGroups.map((group) => (
            <div className="nav-group" key={group.label}>
              <div className="nav-label">{group.label}</div>
              {group.items.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) => `nav-item${isActive ? " nav-item-active" : ""}`}
                  title={item.label}
                >
                  <span className="nav-icon"><Icon name={item.icon} size={16} /></span>
                  <span className="nav-item-label">{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="foundation-card">
            <span className="eyebrow">PHASE 2 COMMAND CENTER</span>
            <p>Live intake is connected. Investigation and action remain explicitly bounded.</p>
          </div>
          <div className="operator-row">
            <span className="operator-avatar">OP</span>
            <div className="operator-copy">
              <strong>Local operator</strong>
              <span className="muted">Authentication not enabled</span>
            </div>
          </div>
        </div>
      </aside>

      {mobileOpen ? <button className="mobile-scrim" type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)} /> : null}

      <main className="main-content">
        <header className="topbar">
          <div className="topbar-left">
            <button className="mobile-menu-button" type="button" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}>
              <Icon name="menu" size={19} />
            </button>
            <div className="topbar-page-title">{currentPageTitle(location.pathname)}</div>
            <span className="topbar-divider">/</span>
            <span className="muted topbar-context">ShopFlow environment</span>
          </div>
          <div className="topbar-right">
            <div className={`system-status${health ? " is-operational" : healthLoading ? " is-loading" : " is-down"}`}>
              <span className="system-status-dot" aria-hidden="true" />
              <span>{health ? "NEXORA SYSTEMS OPERATIONAL" : healthLoading ? "CHECKING NEXORA SYSTEMS" : "NEXORA API UNAVAILABLE"}</span>
            </div>
            <div className={`system-status${aiHealth?.verified ? " is-operational" : healthLoading ? " is-loading" : aiHealth ? " is-loading" : " is-down"}`} title={aiHealth?.message ?? "AI provider health unavailable"}>
              <span className="system-status-dot" aria-hidden="true" />
              <span>{aiStatusLabel}</span>
            </div>
            <div className="topbar-divider topbar-divider-right" />
            <div className="alert-count" title="Derived from the live incident API">
              <Icon name="bell" size={15} />
              <span>{openCount === null ? "—" : openCount}</span>
              <span className="topbar-muted">open</span>
            </div>
            <StatusBadge value={health?.environment ?? "pending"} label={health?.environment ?? "pending"} />
            <div className="profile-chip" title="Authentication is not enabled in Phase 2">
              <span className="profile-avatar">OP</span>
              <span className="profile-name">Local operator</span>
            </div>
            <button className="sidebar-toggle desktop-only" type="button" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={() => setCollapsed((value) => !value)}>
              <Icon name={collapsed ? "arrow" : "menu"} size={16} />
            </button>
          </div>
        </header>
        <div className="content-wrap">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
