"""Incident data model shared by local (SQLite) and AWS (DynamoDB) repositories."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

IncidentType = Literal["fire_smoke", "person_down", "route_obstruction"]
Severity = Literal["NONE", "LOW", "MEDIUM", "HIGH"]
ActionStatus = Literal["OPEN", "ACTION_TAKEN", "CLOSED"]
ApprovalStatus = Literal["NOT_REQUIRED", "PENDING", "APPROVED", "REJECTED"]


class Incident(BaseModel):
    incident_id: str
    timestamp: float
    incident_type: IncidentType
    severity: Severity
    confidence: float
    location: str
    evidence_url: Optional[str] = None
    agent_decision: str
    agent_rationale: str = ""
    recommended_action: str
    action_status: ActionStatus = "OPEN"
    human_approval_required: bool = False
    human_approval_status: ApprovalStatus = "NOT_REQUIRED"
    created_at: float
    updated_at: float
