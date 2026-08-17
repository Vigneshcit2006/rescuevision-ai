import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useHealth } from "../hooks/useHealth";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: "▣" },
  { to: "/incidents", label: "Incidents", icon: "⚑" },
  { to: "/analytics", label: "Analytics", icon: "▤" },
  { to: "/system", label: "System", icon: "⚙" },
  { to: "/demo", label: "Demo Control", icon: "▶" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { connected, checking, error } = useHealth();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">RESCUEVISION AI</div>
        <div className="brand-sub">Ops Console</div>
        <nav>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              <span>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className={`conn-status ${checking ? "" : connected ? "ok" : "bad"}`}>
          {checking ? "Checking backend..." : connected ? "Backend connected" : `Backend unreachable${error ? ` (${error})` : ""}`}
        </div>
      </aside>
      <main className="main">
        {!checking && !connected && (
          <div className="banner">
            Cannot reach the RescueVision AI backend at the configured API URL. Start the backend
            (uvicorn app.main:app) and this page will reconnect automatically.
          </div>
        )}
        {children}
      </main>
    </div>
  );
}
