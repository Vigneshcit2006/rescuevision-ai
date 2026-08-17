import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Incident, SystemStatusResponse } from "../types";
import { ApprovalBadge, SeverityBadge, formatIncidentType, formatTimestamp } from "../components/badges";

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [latestIncident, setLatestIncident] = useState<Incident | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [statusRes, incidentsRes] = await Promise.all([
          api.systemStatus(),
          api.listIncidents(1),
        ]);
        if (cancelled) return;
        setStatus(statusRes);
        setLatestIncident(incidentsRes.incidents[0] ?? null);
        setError(null);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load dashboard data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    const timer = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const activeCount = status?.active_sessions.filter((s) => s.running).length ?? 0;

  return (
    <div>
      <h1 className="page-title">Operations Dashboard</h1>
      <p className="page-sub">Live view of the vision-to-action pipeline for disaster-response monitoring.</p>

      {error && <div className="banner">{error}</div>}
      {loading && !status ? (
        <div className="loading">Loading system status...</div>
      ) : (
        <>
          <div className="grid grid-4" style={{ marginBottom: 24 }}>
            <div className="stat-tile">
              <div className="stat-label">Active Sessions</div>
              <div className="stat-value">{activeCount}</div>
            </div>
            <div className="stat-tile">
              <div className="stat-label">Storage Backend</div>
              <div className="stat-value small">{status?.storage_backend ?? "-"}</div>
            </div>
            <div className="stat-tile">
              <div className="stat-label">Incident Backend</div>
              <div className="stat-value small">{status?.incident_backend ?? "-"}</div>
            </div>
            <div className="stat-tile">
              <div className="stat-label">Notification Backend</div>
              <div className="stat-value small">{status?.notification_backend ?? "-"}</div>
            </div>
          </div>

          <div className="section-title">Pipeline</div>
          <div className="pipeline">
            <PipelineStage label="Vision Status">
              {status ? (
                <>
                  <div className="kv-row">
                    <span className="kv-key">Environment</span>
                    <span className="kv-val">{status.environment}</span>
                  </div>
                  <div className="kv-row">
                    <span className="kv-key">Sessions running</span>
                    <span className="kv-val">{activeCount}</span>
                  </div>
                </>
              ) : (
                <span className="loading">No data</span>
              )}
            </PipelineStage>
            <Arrow />
            <PipelineStage label="Incident">
              {latestIncident ? (
                <>
                  <div style={{ marginBottom: 8 }}>
                    <SeverityBadge severity={latestIncident.severity} />
                  </div>
                  <div className="kv-row">
                    <span className="kv-key">Type</span>
                    <span className="kv-val">{formatIncidentType(latestIncident.incident_type)}</span>
                  </div>
                  <div className="kv-row">
                    <span className="kv-key">Confidence</span>
                    <span className="kv-val">{(latestIncident.confidence * 100).toFixed(0)}%</span>
                  </div>
                </>
              ) : (
                <span className="loading">No incidents yet</span>
              )}
            </PipelineStage>
            <Arrow />
            <PipelineStage label="Agent Decision">
              {latestIncident ? (
                <>
                  <div className="kv-row">
                    <span className="kv-key">Decision</span>
                    <span className="kv-val">{latestIncident.agent_decision}</span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-1)", marginTop: 8 }}>
                    {latestIncident.agent_rationale}
                  </div>
                </>
              ) : (
                <span className="loading">Awaiting signal</span>
              )}
            </PipelineStage>
            <Arrow />
            <PipelineStage label="Action">
              {latestIncident ? (
                <>
                  <div className="kv-row">
                    <span className="kv-key">Status</span>
                    <span className="kv-val">{latestIncident.action_status}</span>
                  </div>
                  <div className="kv-row">
                    <span className="kv-key">Approval</span>
                    <span className="kv-val">
                      <ApprovalBadge status={latestIncident.human_approval_status} />
                    </span>
                  </div>
                </>
              ) : (
                <span className="loading">No action</span>
              )}
            </PipelineStage>
            <Arrow />
            <PipelineStage label="AWS Status">
              {status ? (
                <>
                  <div className="kv-row">
                    <span className="kv-key">Storage</span>
                    <span className="kv-val">{status.storage_backend}</span>
                  </div>
                  <div className="kv-row">
                    <span className="kv-key">Incidents</span>
                    <span className="kv-val">{status.incident_backend}</span>
                  </div>
                  <div className="kv-row">
                    <span className="kv-key">Notify</span>
                    <span className="kv-val">{status.notification_backend}</span>
                  </div>
                </>
              ) : (
                <span className="loading">No data</span>
              )}
            </PipelineStage>
          </div>

          <div className="section-title">Most Recent Incident</div>
          {latestIncident ? (
            <div className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <div>
                  <strong>{formatIncidentType(latestIncident.incident_type)}</strong>{" "}
                  <span style={{ color: "var(--text-2)" }}>at {latestIncident.location}</span>
                </div>
                <SeverityBadge severity={latestIncident.severity} />
              </div>
              <div style={{ color: "var(--text-1)", marginBottom: 12 }}>{latestIncident.agent_rationale}</div>
              <div style={{ fontSize: 12, color: "var(--text-2)" }}>
                {formatTimestamp(latestIncident.timestamp)} &middot;{" "}
                <Link to={`/incidents/${latestIncident.incident_id}`}>View details &rarr;</Link>
              </div>
            </div>
          ) : (
            <div className="card empty-state">No incidents recorded yet. Run a demo scenario to generate one.</div>
          )}
        </>
      )}
    </div>
  );
}

function PipelineStage({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="pipeline-stage">
      <div className="pipeline-stage-label">{label}</div>
      <div className="pipeline-stage-body">{children}</div>
    </div>
  );
}

function Arrow() {
  return <div className="pipeline-arrow">&rarr;</div>;
}
