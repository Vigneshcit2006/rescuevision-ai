import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, resolveEvidenceUrl } from "../api";
import type { Incident } from "../types";
import { ApprovalBadge, SeverityBadge, formatIncidentType, formatTimestamp } from "../components/badges";

const APPROVER = "operator";

export default function IncidentDetail() {
  const { id } = useParams<{ id: string }>();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [actionPending, setActionPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const res = await api.getIncident(id);
      setIncident(res);
      setError(null);
      setNotFound(false);
    } catch (e) {
      if (e instanceof Error && e.message.includes("not found")) {
        setNotFound(true);
      } else {
        setError(e instanceof Error ? e.message : "Failed to load incident");
      }
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleApprove() {
    if (!id) return;
    setActionPending(true);
    setActionError(null);
    try {
      const updated = await api.approveIncident(id, APPROVER);
      setIncident(updated);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Approval failed");
    } finally {
      setActionPending(false);
    }
  }

  async function handleReject() {
    if (!id) return;
    setActionPending(true);
    setActionError(null);
    try {
      const updated = await api.rejectIncident(id, APPROVER);
      setIncident(updated);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Rejection failed");
    } finally {
      setActionPending(false);
    }
  }

  if (notFound) {
    return (
      <div>
        <h1 className="page-title">Incident not found</h1>
        <p className="page-sub">
          <Link to="/incidents">&larr; Back to incidents</Link>
        </p>
      </div>
    );
  }

  if (!incident) {
    return (
      <div>
        <h1 className="page-title">Incident Detail</h1>
        {error ? <div className="banner">{error}</div> : <div className="loading">Loading incident...</div>}
      </div>
    );
  }

  const evidenceUrl = resolveEvidenceUrl(incident.evidence_url);

  return (
    <div>
      <p className="page-sub" style={{ marginBottom: 6 }}>
        <Link to="/incidents">&larr; Back to incidents</Link>
      </p>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
        <h1 className="page-title" style={{ marginBottom: 0 }}>
          {formatIncidentType(incident.incident_type)}
        </h1>
        <SeverityBadge severity={incident.severity} />
      </div>
      <p className="page-sub">
        {incident.incident_id} &middot; {formatTimestamp(incident.timestamp)} &middot; {incident.location}
      </p>

      <div className="grid grid-2">
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>
            Evidence
          </div>
          {evidenceUrl ? (
            <img src={evidenceUrl} alt="Incident evidence" className="evidence-img" />
          ) : (
            <div className="empty-state">No evidence image available for this incident.</div>
          )}
        </div>

        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>
            Agent Assessment
          </div>
          <div className="kv-row">
            <span className="kv-key">Confidence</span>
            <span className="kv-val">{(incident.confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="kv-row">
            <span className="kv-key">Decision</span>
            <span className="kv-val">{incident.agent_decision}</span>
          </div>
          <div className="kv-row">
            <span className="kv-key">Action Status</span>
            <span className="kv-val">{incident.action_status}</span>
          </div>
          <div className="kv-row">
            <span className="kv-key">Approval Status</span>
            <span className="kv-val">
              <ApprovalBadge status={incident.human_approval_status} />
            </span>
          </div>
          <div style={{ marginTop: 14 }}>
            <div className="stat-label">Rationale</div>
            <div style={{ color: "var(--text-0)", marginTop: 4 }}>{incident.agent_rationale}</div>
          </div>
          <div style={{ marginTop: 14 }}>
            <div className="stat-label">Recommended Action</div>
            <div style={{ color: "var(--text-0)", marginTop: 4 }}>{incident.recommended_action}</div>
          </div>
        </div>
      </div>

      {incident.human_approval_status === "PENDING" && (
        <div className="approval-box">
          <div className="approval-title">Potential emergency detected</div>
          <div className="kv-row">
            <span className="kv-key">Severity</span>
            <span className="kv-val">
              <SeverityBadge severity={incident.severity} />
            </span>
          </div>
          <div className="kv-row">
            <span className="kv-key">Confidence</span>
            <span className="kv-val">{(incident.confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="kv-row">
            <span className="kv-key">Recommended action</span>
            <span className="kv-val">{incident.recommended_action}</span>
          </div>
          {actionError && <div className="banner" style={{ marginTop: 12 }}>{actionError}</div>}
          <div className="approval-actions">
            <button className="btn btn-primary" onClick={handleApprove} disabled={actionPending}>
              {actionPending ? "Working..." : "APPROVE"}
            </button>
            <button className="btn btn-danger" onClick={handleReject} disabled={actionPending}>
              {actionPending ? "Working..." : "REJECT"}
            </button>
          </div>
        </div>
      )}

      {incident.human_approval_status === "APPROVED" && (
        <div className="approval-box" style={{ borderColor: "rgba(52,211,153,0.35)", background: "rgba(52,211,153,0.06)" }}>
          <div className="approval-title" style={{ color: "var(--ok)" }}>
            Approved — notification dispatched to responders.
          </div>
        </div>
      )}

      {incident.human_approval_status === "REJECTED" && (
        <div className="approval-box" style={{ borderColor: "rgba(239,86,88,0.35)", background: "rgba(239,86,88,0.06)" }}>
          <div className="approval-title" style={{ color: "var(--danger)" }}>
            Rejected by operator — no notification sent.
          </div>
        </div>
      )}
    </div>
  );
}
