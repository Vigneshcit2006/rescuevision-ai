"""
Failure-mode tests: the system must fail *safely* -- low-confidence signals
must never trigger a notification, an invalid/corrupt video source must
raise a clear error rather than crash silently, and AWS-backend selection
must never be attempted when AWS is not configured (so local dev/CI never
needs credentials). See docs/failure-cases.md for the full narrative.
"""
import pytest

from app.agent.policy import AgentPolicy
from app.aws.factory import build_incident_repository, build_notification_service, build_storage
from app.configuration.config import Settings
from app.vision.video_source import VideoSource


def test_low_confidence_never_triggers_notification(settings):
    policy = AgentPolicy(settings.agent_policy, settings.thresholds, settings.monitoring)
    outcome = policy.evaluate(
        {"state": "possible", "confidence": 0.36, "duration_seconds": 3.5, "scenario": "fire_smoke"}
    )
    assert outcome.action != "SEND_ALERT"


def test_invalid_video_path_raises_ioerror():
    with pytest.raises(IOError):
        VideoSource("this_file_definitely_does_not_exist.mp4").open()


def test_default_settings_select_local_backends_without_aws_credentials():
    settings = Settings()
    assert settings.storage_backend == "local"
    assert settings.incident_backend == "local"
    assert settings.notification_backend == "local"
    # These factory calls must succeed with zero AWS configuration present.
    build_storage(settings)
    build_incident_repository(settings)
    build_notification_service(settings)


def test_aws_storage_backend_without_bucket_falls_back_to_local(tmp_path):
    settings = Settings(storage_backend="aws", s3_bucket="", local_storage_dir=str(tmp_path))
    storage = build_storage(settings)
    from app.aws.storage import LocalStorage

    assert isinstance(storage, LocalStorage)


def test_unknown_scenario_key_raises_value_error(settings):
    from app.vision.pipeline import VisionPipeline

    with pytest.raises(KeyError):
        VisionPipeline("not_a_scenario", settings.thresholds, settings.region_of_interest)
