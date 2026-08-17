import { useEffect, useState } from "react";
import { api } from "../api";
import type { HealthResponse, SystemStatusResponse } from "../types";

export default function System() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [h, s] = await Promise.all([api.health(), api.systemStatus()]);
        if (!cancelled) {
          setHealth(h);
          setStatus(s);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load system status");
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
      <h1 className="page-title">System</h1>
      <p className="page-sub">Backend health and active session detail.</p>

      {error && <div className="banner">{error}</div>}

      <div className="grid grid-2" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>
            Health
          </div>
          {health ? (
            <>
              <div className="kv-row">
                <span className="kv-key">Status</span>
                <span className="kv-val">{health.status}</span>
              </div>
              <div className="kv-row">
                <span className="kv-key">OpenCV Version</span>
                <span className="kv-val">{health.opencv_version}</span>
              </div>
              <div className="kv-row">
                <span className="kv-key">Environment</span>
                <span className="kv-val">{health.environment}</span>
              </div>
            </>
          ) : (
            <div className="loading">Loading...</div>
          )}
        </div>

        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>
            Backends
          </div>
          {status ? (
            <>
              <div className="kv-row">
                <span className="kv-key">Environment</span>
                <span className="kv-val">{status.environment}</span>
              </div>
              <div className="kv-row">
                <span className="kv-key">Storage</span>
                <span className="kv-val">{status.storage_backend}</span>
              </div>
              <div className="kv-row">
                <span className="kv-key">Incidents</span>
                <span className="kv-val">{status.incident_backend}</span>
              </div>
              <div className="kv-row">
                <span className="kv-key">Notifications</span>
                <span className="kv-val">{status.notification_backend}</span>
              </div>
            </>
          ) : (
            <div className="loading">Loading...</div>
          )}
        </div>
      </div>

      <div className="section-title">Active Sessions</div>
      <div className="card" style={{ padding: 0, overflowX: "auto" }}>
        {status === null ? (
          <div className="loading" style={{ padding: 20 }}>
            Loading...
          </div>
        ) : status.active_sessions.length === 0 ? (
          <div className="empty-state">No sessions have run yet.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Session ID</th>
                <th>Scenario</th>
                <th>Running</th>
                <th>Interval (s)</th>
                <th>Frames Processed</th>
                <th>Last State</th>
              </tr>
            </thead>
            <tbody>
              {status.active_sessions.map((s) => (
                <tr key={s.session_id}>
                  <td>{s.session_id}</td>
                  <td>{s.scenario}</td>
                  <td>{s.running ? "Yes" : "No"}</td>
                  <td>{s.current_interval_seconds}</td>
                  <td>{s.frames_processed}</td>
                  <td>{s.last_candidate?.state ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
