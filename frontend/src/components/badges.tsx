import type { ApprovalStatus, Severity } from "../types";

export function SeverityBadge({ severity }: { severity: Severity }) {
  const cls =
    severity === "HIGH"
      ? "badge-high"
      : severity === "MEDIUM"
      ? "badge-medium"
      : severity === "LOW"
      ? "badge-low"
      : "badge-none";
  return (
    <span className={`badge ${cls}`}>
      <span className="badge-dot" />
      {severity}
    </span>
  );
}

export function ApprovalBadge({ status }: { status: ApprovalStatus }) {
  const cls =
    status === "PENDING"
      ? "pending"
      : status === "APPROVED"
      ? "approved"
      : status === "REJECTED"
      ? "rejected"
      : "";
  const label = status === "NOT_REQUIRED" ? "N/A" : status;
  return <span className={`badge badge-approval ${cls}`}>{label}</span>;
}

export function formatIncidentType(t: string): string {
  return t
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function formatTimestamp(ts: number): string {
  return new Date(ts * 1000).toLocaleString();
}
