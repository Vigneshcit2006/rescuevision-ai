"""API routes for RescueVision AI. See docs/agent-workflow.md for the
full request -> vision -> agent -> AWS action -> response life cycle."""
from __future__ import annotations

import shutil
import tempfile
import time
import uuid
from pathlib import Path

import cv2
from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.api.schemas import (
    AnalyzeResponse,
    ApprovalRequest,
    DemoStartRequest,
    DemoStartResponse,
    DemoStopRequest,
    HealthResponse,
    IncidentListResponse,
    MetricsResponse,
    SystemStatusResponse,
)
from app.incidents.models import Incident
from app.logging.structured_logger import get_logger, log_event

router = APIRouter(prefix="/api")
logger = get_logger("api.routes")


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(status="ok", opencv_version=cv2.__version__, environment=settings.environment)


@router.get("/system-status", response_model=SystemStatusResponse)
def system_status(request: Request) -> SystemStatusResponse:
    settings = request.app.state.settings
    monitoring = request.app.state.monitoring_service
    sessions = [s.__dict__ for s in monitoring.list_sessions()]
    return SystemStatusResponse(
        environment=settings.environment,
        storage_backend=settings.storage_backend,
        incident_backend=settings.incident_backend,
        notification_backend=settings.notification_backend,
        active_sessions=sessions,
    )


@router.get("/incidents", response_model=IncidentListResponse)
def list_incidents(request: Request, limit: int = 100) -> IncidentListResponse:
    repo = request.app.state.incident_repo
    incidents = repo.list(limit=limit)
    return IncidentListResponse(incidents=incidents, count=len(incidents))


@router.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(request: Request, incident_id: str) -> Incident:
    repo = request.app.state.incident_repo
    incident = repo.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return incident


@router.post("/incidents/{incident_id}/approve", response_model=Incident)
def approve_incident(request: Request, incident_id: str, body: ApprovalRequest) -> Incident:
    repo = request.app.state.incident_repo
    notifications = request.app.state.notifications
    incident = repo.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    updated = repo.update(
        incident_id,
        human_approval_status="APPROVED",
        action_status="ACTION_TAKEN",
        updated_at=time.time(),
    )
    notifications.notify(updated)
    log_event(logger, "api.incident.approved", incident_id=incident_id, approver=body.approver)
    return updated


@router.post("/incidents/{incident_id}/reject", response_model=Incident)
def reject_incident(request: Request, incident_id: str, body: ApprovalRequest) -> Incident:
    repo = request.app.state.incident_repo
    incident = repo.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    updated = repo.update(
        incident_id,
        human_approval_status="REJECTED",
        action_status="CLOSED",
        updated_at=time.time(),
    )
    log_event(logger, "api.incident.rejected", incident_id=incident_id, approver=body.approver, notes=body.notes)
    return updated


@router.post("/demo/start", response_model=DemoStartResponse)
def demo_start(request: Request, body: DemoStartRequest) -> DemoStartResponse:
    monitoring = request.app.state.monitoring_service
    session_id = body.session_id or f"demo-{uuid.uuid4().hex[:8]}"
    try:
        session = monitoring.start_demo(body.scenario, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_event(logger, "api.demo.start", session_id=session_id, scenario=body.scenario)
    return DemoStartResponse(session_id=session.session_id, scenario=session.scenario, status="running")


@router.post("/demo/stop")
def demo_stop(request: Request, body: DemoStopRequest) -> dict:
    monitoring = request.app.state.monitoring_service
    stopped = monitoring.stop(body.session_id)
    if not stopped:
        raise HTTPException(status_code=404, detail=f"Session {body.session_id} not found")
    log_event(logger, "api.demo.stop", session_id=body.session_id)
    return {"session_id": body.session_id, "status": "stopped"}


@router.get("/demo/status/{session_id}")
def demo_status(request: Request, session_id: str) -> dict:
    monitoring = request.app.state.monitoring_service
    status = monitoring.get_status(session_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return status.__dict__


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: Request, scenario: str, file: UploadFile = File(...)) -> AnalyzeResponse:
    monitoring = request.app.state.monitoring_service
    session_id = f"upload-{uuid.uuid4().hex[:8]}"
    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    tmp_dir = Path(tempfile.gettempdir()) / "rescuevision_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{session_id}{suffix}"
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        session = monitoring.start_upload_analysis(session_id, str(tmp_path), scenario)
    except (IOError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Unable to analyze uploaded video: {e}")
    log_event(logger, "api.analyze.start", session_id=session_id, scenario=scenario, filename=file.filename)
    return AnalyzeResponse(session_id=session.session_id, scenario=session.scenario, status="running")


@router.get("/metrics", response_model=MetricsResponse)
def metrics(request: Request) -> MetricsResponse:
    repo = request.app.state.incident_repo
    monitoring = request.app.state.monitoring_service
    incidents = repo.list(limit=1000)
    by_severity: dict[str, int] = {}
    by_type: dict[str, int] = {}
    pending = 0
    for inc in incidents:
        by_severity[inc.severity] = by_severity.get(inc.severity, 0) + 1
        by_type[inc.incident_type] = by_type.get(inc.incident_type, 0) + 1
        if inc.human_approval_status == "PENDING":
            pending += 1
    return MetricsResponse(
        total_incidents=len(incidents),
        incidents_by_severity=by_severity,
        incidents_by_type=by_type,
        pending_human_approvals=pending,
        active_sessions=len(monitoring.list_sessions()),
    )
