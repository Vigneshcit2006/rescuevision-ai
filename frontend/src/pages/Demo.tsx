import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { DemoScenario, SessionStatus } from "../types";
import { SeverityBadge } from "../components/badges";

const SCENARIOS: { scenario: DemoScenario; title: string; subtitle: string }[] = [
  { scenario: "fire_smoke", title: "Fire Demo", subtitle: "Simulates smoke/fire color signature" },
  { scenario: "person_down", title: "Person Down Demo", subtitle: "Simulates a stationary collapsed figure" },
  { scenario: "route_obstruction", title: "Obstruction Demo", subtitle: "Simulates a persistent route blockage" },
  { scenario: "normal", title: "Normal Scene", subtitle: "Simulates routine, incident-free footage" },
];

function severityForDecision(decision: string | undefined): "NONE" | "LOW" | "MEDIUM" | "HIGH" {
  const s = (decision as "NONE" | "LOW" | "MEDIUM" | "HIGH") || "NONE";
  if (s === "HIGH" || s === "MEDIUM" || s === "LOW" || s === "NONE") return s;
  return "NONE";
}

export default function Demo() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [scenario, setScenario] = useState<DemoScenario | null>(null);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [starting, setStarting] = useState<DemoScenario | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function pollStatus(id: string) {
    try {
      const s = await api.demoStatus(id);
      setStatus(s);
      if (!s.running) {
        stopPolling();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to poll session status");
      stopPolling();
    }
  }

  async function startDemo(s: DemoScenario) {
    setError(null);
    setStarting(s);
    stopPolling();
    const newSessionId = `demo-${Date.now()}`;
    try {
      const res = await api.demoStart(s, newSessionId);
      setSessionId(res.session_id);
      setScenario(s);
      setStatus(null);
      await pollStatus(res.session_id);
      pollRef.current = setInterval(() => pollStatus(res.session_id), 750);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start demo");
    } finally {
      setStarting(null);
    }
  }

  async function stopDemo() {
    if (!sessionId) return;
    stopPolling();
    try {
      await api.demoStop(sessionId);
      await pollStatus(sessionId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to stop demo");
    }
  }

  const decisionSeverity = status?.last_decision ? severityForDecision(status.last_decision.severity) : null;
  const incidentId = status?.last_decision?.incident_id ?? null;

  return (
    <div>
      <h1 className="page-title">Demo Control</h1>
      <p className="page-sub">Run synthetic scenarios end-to-end through the vision, agent, and action pipeline.</p>

      {error && <div className="banner">{error}</div>}

      <div className="demo-grid">
        {SCENARIOS.map((sc) => (
          <button
            key={sc.scenario}
            className="demo-btn"
            onClick={() => startDemo(sc.scenario)}
            disabled={starting !== null || (status?.running ?? false)}
          >
            <div className="demo-btn-title">{sc.title}</div>
            <div className="demo-btn-sub">
              {starting === sc.scenario ? "Starting..." : sc.subtitle}
            </div>
          </button>
        ))}
      </div>

      {sessionId && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div>
              <strong>Session:</strong> <span className="mono">{sessionId}</span>{" "}
              <span style={{ color: "var(--text-2)" }}>({scenario})</span>
            </div>
            <button className="btn btn-stop" onClick={stopDemo} disabled={!status?.running}>
              Stop
            </button>
          </div>

          {!status ? (
            <div className="loading">Starting session...</div>
          ) : (
            <>
              <div className="grid grid-4" style={{ marginBottom: 20 }}>
                <div className="stat-tile">
                  <div className="stat-label">Status</div>
                  <div className="stat-value small">{status.running ? "Running" : "Stopped"}</div>
                </div>
                <div className="stat-tile">
                  <div className="stat-label">Detection State</div>
                  <div className="stat-value small">{status.last_candidate?.state ?? "none"}</div>
                </div>
                <div className="stat-tile">
                  <div className="stat-label">Confidence</div>
                  <div className="stat-value small">
                    {status.last_candidate ? `${(status.last_candidate.confidence * 100).toFixed(0)}%` : "-"}
                  </div>
                </div>
                <div className="stat-tile">
                  <div className="stat-label">Monitoring Interval</div>
                  <div className="stat-value small">{status.current_interval_seconds}s</div>
                </div>
              </div>

              {status.last_decision ? (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                    {decisionSeverity && <SeverityBadge severity={decisionSeverity} />}
                    <strong>{status.last_decision.decision}</strong>
                  </div>
                  {scenario === "normal" && decisionSeverity === "NONE" ? (
                    <div style={{ color: "var(--text-1)" }}>
                      No incident — continuing routine monitoring.
                    </div>
                  ) : (
                    <div style={{ color: "var(--text-1)" }}>{status.last_decision.rationale}</div>
                  )}
                  <div className="kv-row">
                    <span className="kv-key">Action</span>
                    <span className="kv-val">{status.last_decision.action}</span>
                  </div>
                  <div className="kv-row">
                    <span className="kv-key">Requires human approval</span>
                    <span className="kv-val">{status.last_decision.requires_human_approval ? "Yes" : "No"}</span>
                  </div>
                  {incidentId && (
                    <div className="kv-row">
                      <span className="kv-key">Incident</span>
                      <span className="kv-val">
                        <Link to={`/incidents/${incidentId}`}>{incidentId} &rarr;</Link>
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <div className="loading">Awaiting first agent decision...</div>
              )}

              <div className="stat-label" style={{ marginBottom: 8 }}>
                Trace
              </div>
              <div className="trace-log">
                {status.last_trace.length === 0 ? (
                  <div className="trace-line">No trace events yet.</div>
                ) : (
                  status.last_trace.map((t, i) => (
                    <div className="trace-line" key={i}>
                      <span className="t-time">{new Date(t.timestamp * 1000).toLocaleTimeString()}</span>
                      <span className="t-state">{t.state}</span>
                      {t.detail}
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
