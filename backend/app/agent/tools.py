"""
Controlled agent tools. The agent never touches storage/incident/notification
backends directly -- it can only call these named tools, and each tool
delegates to whichever backend (local or AWS) is configured. This is the
enforcement point for "the agent cannot execute unrestricted dangerous
actions": tools are the entire attack surface, and each one is narrow,
logged, and backed by an interface that is mocked in tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.aws.notifications import NotificationService
from app.aws.storage import StorageService
from app.incidents.models import Incident
from app.incidents.repository import IncidentRepository
from app.logging.structured_logger import get_logger, log_event

logger = get_logger("agent.tools")


@dataclass
class ToolContext:
    storage: StorageService
    incidents: IncidentRepository
    notifications: NotificationService


class AgentTools:
    """Every method here is a named, auditable tool the agent may invoke."""

    def __init__(self, ctx: ToolContext):
        self.ctx = ctx

    def store_evidence(self, incident_id: str, jpeg_bytes: Optional[bytes]) -> Optional[str]:
        if jpeg_bytes is None:
            return None
        url = self.ctx.storage.store_evidence(incident_id, jpeg_bytes)
        log_event(logger, "tool.store_evidence", incident_id=incident_id, evidence_url=url)
        return url

    def create_incident(self, incident: Incident) -> Incident:
        created = self.ctx.incidents.create(incident)
        log_event(logger, "tool.create_incident", incident_id=created.incident_id, severity=created.severity)
        return created

    def update_incident(self, incident_id: str, **fields) -> Optional[Incident]:
        updated = self.ctx.incidents.update(incident_id, **fields)
        log_event(logger, "tool.update_incident", incident_id=incident_id, fields=list(fields.keys()))
        return updated

    def send_notification(self, incident: Incident) -> bool:
        ok = self.ctx.notifications.notify(incident)
        log_event(logger, "tool.send_notification", incident_id=incident.incident_id, sent=ok)
        return ok

    def request_human_approval(self, incident_id: str) -> Optional[Incident]:
        updated = self.ctx.incidents.update(incident_id, human_approval_status="PENDING")
        log_event(logger, "tool.request_human_approval", incident_id=incident_id)
        return updated

    def increase_monitoring_frequency(self, region: str, interval_seconds: float) -> None:
        log_event(logger, "tool.increase_monitoring_frequency", region=region, interval_seconds=interval_seconds)

    def close_incident(self, incident_id: str, reason: str) -> Optional[Incident]:
        updated = self.ctx.incidents.update(incident_id, action_status="CLOSED")
        log_event(logger, "tool.close_incident", incident_id=incident_id, reason=reason)
        return updated
