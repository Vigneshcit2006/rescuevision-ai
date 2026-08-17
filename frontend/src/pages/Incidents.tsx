import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Incident } from "../types";
import { ApprovalBadge, SeverityBadge, formatIncidentType, formatTimestamp } from "../components/badges";

export default function Incidents() {
  const [incidents, setIncidents] = useState<Incident[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await api.listIncidents(100);
        if (!cancelled) {
          setIncidents(res.incidents);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load incidents");
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
      <h1 className="page-title">Incidents</h1>
      <p className="page-sub">All incidents raised by the agentic vision pipeline.</p>

      {error && <div className="banner">{error}</div>}

      <div className="card" style={{ padding: 0, overflowX: "auto" }}>
        {incidents === null ? (
          <div className="loading" style={{ padding: 20 }}>
            Loading incidents...
          </div>
        ) : incidents.length === 0 ? (
          <div className="empty-state">No incidents recorded yet. Run a demo scenario to generate one.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Location</th>
                <th>Severity</th>
                <th>Confidence</th>
                <th>Action Status</th>
                <th>Approval</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc) => (
                <tr
                  key={inc.incident_id}
                  className="clickable"
                  onClick={() => navigate(`/incidents/${inc.incident_id}`)}
                >
                  <td>{formatTimestamp(inc.timestamp)}</td>
                  <td>{formatIncidentType(inc.incident_type)}</td>
                  <td>{inc.location}</td>
                  <td>
                    <SeverityBadge severity={inc.severity} />
                  </td>
                  <td>{(inc.confidence * 100).toFixed(0)}%</td>
                  <td>{inc.action_status}</td>
                  <td>
                    <ApprovalBadge status={inc.human_approval_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
