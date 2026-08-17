"""
API integration tests using FastAPI's TestClient (no live server, no network,
no AWS credentials). Exercises the full HTTP surface: health, demo lifecycle,
incident listing, and human approval/rejection.
"""
import time

import pytest
from fastapi.testclient import TestClient

from app.api.routes import router
from app.aws.factory import build_incident_repository, build_notification_service
from app.services.monitoring_service import MonitoringService
from fastapi import FastAPI


@pytest.fixture
def client(settings):
    app = FastAPI()
    app.state.settings = settings
    app.state.monitoring_service = MonitoringService(settings)
    app.state.incident_repo = build_incident_repository(settings)
    app.state.notifications = build_notification_service(settings)
    app.include_router(router)
    return TestClient(app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["opencv_version"].startswith("5.")


def test_demo_start_invalid_scenario_returns_400(client):
    resp = client.post("/api/demo/start", json={"scenario": "not_a_real_scenario"})
    assert resp.status_code == 400


def test_demo_lifecycle_creates_incident_for_fire(client):
    resp = client.post("/api/demo/start", json={"scenario": "fire_smoke", "session_id": "api-test-fire"})
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    deadline = time.time() + 45
    incident_id = None
    while time.time() < deadline:
        status = client.get(f"/api/demo/status/{session_id}").json()
        decision = (status.get("last_decision") or {}).get("incident_id")
        if decision:
            incident_id = decision
            break
        time.sleep(0.5)

    assert incident_id is not None, "Fire demo did not create an incident within timeout"

    incident = client.get(f"/api/incidents/{incident_id}").json()
    assert incident["incident_type"] == "fire_smoke"
    assert incident["human_approval_status"] == "PENDING"

    approved = client.post(
        f"/api/incidents/{incident_id}/approve", json={"approver": "test_operator"}
    ).json()
    assert approved["human_approval_status"] == "APPROVED"
    assert approved["action_status"] == "ACTION_TAKEN"

    client.post("/api/demo/stop", json={"session_id": session_id})


def test_incident_not_found_returns_404(client):
    resp = client.get("/api/incidents/RV-DOES-NOT-EXIST")
    assert resp.status_code == 404


def test_metrics_endpoint_shape(client):
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert "total_incidents" in body
    assert "pending_human_approvals" in body
