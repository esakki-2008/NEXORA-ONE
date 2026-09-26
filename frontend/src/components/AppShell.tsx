import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { getHealth } from "../api/health";
import { StatusBadge } from "./StatusBadge";
import type { HealthResponse } from "../types";

interface NavItem {
  label: string;
  path: string;
  code: string;
}

const navItems: NavItem[] = [
  { label: "Command Center", path: "/command-center", code: "CC" },
  { label: "Incidents", path: "/incidents", code: "IN" },
  { label: "Investigation", path: "/investigation", code: "IV" },
  { label: "Evidence", path: "/evidence", code: "EV" },
  { label: "Agents", path: "/agents", code: "AG" },
  { label: "Operations", path: "/operations", code: "OP" },
  { label: "Verification", path: "/verification", code: "VR" },
  { label: "Reports", path: "/reports", code: "RP" },
  { label: "Settings", path: "/settings", code: "ST" }
];

function HealthIndicator({ health, loading }: { health: HealthResponse | null; loading: boolean }) {
  if (loading) {
    return <StatusBadge value="loading" />;
  }

  return <StatusBadge value={health ? "online" : "offline"} />;
}

export function AppShell() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getHealth()
      .then((payload) => {
        if (active) setHealth(payload);
      })
      .catch(() => {
        if (active) setHealth(null);
      })
      .finally(() => {
        if (active) setHealthLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">N</div>
          <div>
            <div className="brand-name">NEXORA <span>ONE</span></div>
            <div className="brand-caption">OPERATIONS INTELLIGENCE</div>
          </div>
        </div>

        <div className="sidebar-rule" />
        <div className="nav-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Primary navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-item${isActive ? " nav-item-active" : ""}`}
            >
              <span className="nav-code">{item.code}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="foundation-card">
            <span className="eyebrow">PHASE 1 FOUNDATION</span>
            <p>Bounded surfaces are live. Investigation and execution remain disabled until their phases.</p>
          </div>
          <div className="operator-row">
            <span className="operator-avatar">OP</span>
            <div>
              <strong>Local operator</strong>
              <span className="muted">Development workspace</span>
            </div>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <span className="topbar-kicker">NEXORA CONTROL PLANE</span>
            <span className="topbar-divider">/</span>
            <span className="muted">ShopFlow environment</span>
          </div>
          <div className="topbar-status" title={health?.timestamp ? `Last checked ${health.timestamp}` : undefined}>
            <span className="muted">API</span>
            <HealthIndicator health={health} loading={healthLoading} />
          </div>
        </header>
        <div className="content-wrap">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
