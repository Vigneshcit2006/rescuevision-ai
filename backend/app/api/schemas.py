"""Pydantic request/response schemas for the public API."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.incidents.models import Incident


class HealthResponse(BaseModel):
    status: str
    opencv_version: str
    environment: str


class SystemStatusResponse(BaseModel):
    environment: str
    storage_backend: str
    incident_backend: str
    notification_backend: str
    active_sessions: list[dict[str, Any]]


class IncidentListResponse(BaseModel):
    incidents: list[Incident]
    count: int


class DemoStartRequest(BaseModel):
    scenario: str = Field(..., description="fire_smoke | person_down | route_obstruction | normal")
    session_id: Optional[str] = Field(default=None)


class DemoStartResponse(BaseModel):
    session_id: str
    scenario: str
    status: str


class DemoStopRequest(BaseModel):
    session_id: str


class ApprovalRequest(BaseModel):
    approver: str = Field(..., description="Identifier of the human operator making the decision")
    notes: Optional[str] = None


class AnalyzeResponse(BaseModel):
    session_id: str
    scenario: str
    status: str


class MetricsResponse(BaseModel):
    total_incidents: int
    incidents_by_severity: dict[str, int]
    incidents_by_type: dict[str, int]
    pending_human_approvals: int
    active_sessions: int
