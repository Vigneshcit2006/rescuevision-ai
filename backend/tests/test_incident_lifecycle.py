"""Incident repository + notification/storage mock tests (no AWS credentials required)."""
import time

from app.aws.notifications import MockNotificationService
from app.aws.storage import LocalStorage
from app.incidents.models import Incident
from app.incidents.repository import LocalIncidentRepository


def _incident(incident_id="RV-00001") -> Incident:
    now = time.time()
    return Incident(
        incident_id=incident_id,
        timestamp=now,
        incident_type="fire_smoke",
        severity="HIGH",
        confidence=0.9,
        location="zone_a",
        agent_decision="CREATE_INCIDENT",
        recommended_action="Notify responders.",
        created_at=now,
        updated_at=now,
    )


def test_create_and_get_incident(settings):
    repo = LocalIncidentRepository(settings.local_db_path)
    created = repo.create(_incident())
    fetched = repo.get(created.incident_id)
    assert fetched is not None
    assert fetched.incident_type == "fire_smoke"


def test_update_incident_lifecycle(settings):
    repo = LocalIncidentRepository(settings.local_db_path)
    repo.create(_incident())
    updated = repo.update("RV-00001", human_approval_status="APPROVED", action_status="ACTION_TAKEN")
    assert updated is not None
    assert updated.human_approval_status == "APPROVED"
    assert updated.action_status == "ACTION_TAKEN"


def test_update_missing_incident_returns_none(settings):
    repo = LocalIncidentRepository(settings.local_db_path)
    assert repo.update("RV-99999", severity="LOW") is None


def test_list_incidents_ordered(settings):
    repo = LocalIncidentRepository(settings.local_db_path)
    repo.create(_incident("RV-00001"))
    repo.create(_incident("RV-00002"))
    incidents = repo.list()
    assert [i.incident_id for i in incidents] == ["RV-00002", "RV-00001"]


def test_mock_notification_records_sent_incidents():
    service = MockNotificationService()
    incident = _incident()
    assert service.notify(incident) is True
    assert service.sent == [incident]


def test_local_storage_writes_and_returns_url(tmp_path):
    storage = LocalStorage(str(tmp_path))
    url = storage.store_evidence("RV-00001", b"\xff\xd8\xff\xe0fakejpeg")
    assert url == "/evidence/RV-00001.jpg"
    assert (tmp_path / "RV-00001.jpg").read_bytes() == b"\xff\xd8\xff\xe0fakejpeg"
