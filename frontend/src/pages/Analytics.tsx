import { useEffect, useState } from "react";
import { api } from "../api";
import type { MetricsResponse } from "../types";
import { formatIncidentType } from "../components/badges";

const SEVERITY_ORDER = ["HIGH", "MEDIUM", "LOW", "NONE"];

export default function Analytics() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await api.metrics();
        if (!cancelled) {
          setMetrics(res);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load metrics");
      }
    }
    load();
    const timer = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return (
    <div>
      <h1 className="page-title">Analytics</h1>
      <p className="page-sub">Aggregate incident metrics across the monitoring deployment.</p>

      {error && <div className="banner">{error}</div>}

      {!metrics ? (
        <div className="loading">Loading metrics...</div>
      ) : (
        <>
          <div className="grid grid-4" style={{ marginBottom: 28 }}>
            <div className="stat-tile">
              <div className="stat-label">Total Incidents</div>
              <div className="stat-value">{metrics.total_incidents}</div>
            </div>
            <div className="stat-tile">
              <div className="stat-label">Pending Approvals</div>
              <div className="stat-value">{metrics.pending_human_approvals}</div>
            </div>
            <div className="stat-tile">
              <div className="stat-label">Active Sessions</div>
              <div className="stat-value">{metrics.active_sessions}</div>
            </div>
            <div className="stat-tile">
              <div className="stat-label">Incident Types Seen</div>
              <div className="stat-value">{Object.keys(metrics.incidents_by_type).length}</div>
            </div>
          </div>

          <div className="grid grid-2">
            <div className="card">
              <div className="section-title" style={{ marginTop: 0 }}>
                Incidents by Severity
              </div>
              <BarChart
                data={SEVERITY_ORDER.filter((s) => metrics.incidents_by_severity[s]).map((s) => ({
                  label: s,
                  value: metrics.incidents_by_severity[s] ?? 0,
                }))}
                total={metrics.total_incidents}
                emptyMessage="No incidents recorded yet."
              />
            </div>
            <div className="card">
              <div className="section-title" style={{ marginTop: 0 }}>
                Incidents by Type
              </div>
              <BarChart
                data={Object.entries(metrics.incidents_by_type).map(([label, value]) => ({
                  label: formatIncidentType(label),
                  value,
                }))}
                total={metrics.total_incidents}
                emptyMessage="No incidents recorded yet."
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function BarChart({
  data,
  total,
  emptyMessage,
}: {
  data: { label: string; value: number }[];
  total: number;
  emptyMessage: string;
}) {
  if (data.length === 0) {
    return <div className="empty-state">{emptyMessage}</div>;
  }
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div>
      {data.map((d) => (
        <div className="bar-row" key={d.label}>
          <span>{d.label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(d.value / max) * 100}%` }} />
          </div>
          <span style={{ textAlign: "right" }}>
            {d.value}
            {total > 0 && (
              <span style={{ color: "var(--text-2)" }}> ({((d.value / total) * 100).toFixed(0)}%)</span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}
