"""
AgentPolicy unit tests -- the policy is pure/deterministic, so every
severity/decision/action combination the agent can produce is tested here
directly against evidence dicts, without needing a running pipeline.
"""
from app.agent.policy import AgentPolicy


def _policy(settings):
    return AgentPolicy(settings.agent_policy, settings.thresholds, settings.monitoring)


def test_no_signal_continues_observation(settings):
    policy = _policy(settings)
    outcome = policy.evaluate({"state": "none", "confidence": 0.0, "duration_seconds": 0.0, "scenario": "fire_smoke"})
    assert outcome.decision == "CONTINUE_OBSERVATION"
    assert outcome.action == "NONE"
    assert outcome.requires_human_approval is False
    assert outcome.next_observation_seconds == settings.monitoring.normal_interval_seconds


def test_possible_state_increases_monitoring_and_stores_evidence_only(settings):
    policy = _policy(settings)
    outcome = policy.evaluate(
        {"state": "possible", "confidence": 0.5, "duration_seconds": 4.0, "scenario": "fire_smoke"}
    )
    assert outcome.decision == "INCREASE_MONITORING"
    assert outcome.action == "STORE_EVIDENCE_ONLY"
    assert outcome.requires_human_approval is False
    assert outcome.next_observation_seconds == settings.monitoring.possible_incident_interval_seconds


def test_confirmed_low_confidence_requires_human_approval(settings):
    policy = _policy(settings)
    outcome = policy.evaluate(
        {"state": "confirmed", "confidence": 0.6, "duration_seconds": 10.0, "scenario": "fire_smoke"}
    )
    assert outcome.decision == "CREATE_INCIDENT"
    assert outcome.action == "REQUEST_HUMAN_APPROVAL"
    assert outcome.requires_human_approval is True


def test_confirmed_high_confidence_fire_sends_alert_autonomously(settings):
    policy = _policy(settings)
    outcome = policy.evaluate(
        {"state": "confirmed", "confidence": 0.95, "duration_seconds": 10.0, "scenario": "fire_smoke"}
    )
    assert outcome.decision == "CREATE_INCIDENT"
    assert outcome.action == "SEND_ALERT"
    assert outcome.requires_human_approval is False
    assert outcome.severity == "HIGH"


def test_person_down_always_requires_human_approval_even_at_high_confidence(settings):
    policy = _policy(settings)
    outcome = policy.evaluate(
        {"state": "confirmed", "confidence": 0.95, "duration_seconds": 10.0, "scenario": "person_down"}
    )
    assert outcome.decision == "CREATE_INCIDENT"
    assert outcome.requires_human_approval is True
    assert outcome.action == "REQUEST_HUMAN_APPROVAL"


def test_confidence_just_below_frame_threshold_does_not_act(settings):
    policy = _policy(settings)
    below = settings.thresholds.min_frame_confidence - 0.01
    outcome = policy.evaluate({"state": "possible", "confidence": below, "duration_seconds": 1.0, "scenario": "fire_smoke"})
    assert outcome.decision == "CONTINUE_OBSERVATION"
    assert outcome.action == "NONE"
