"""Temporal persistence logic, isolated from the vision detectors themselves."""
from app.configuration.config import DetectionThresholds
from app.vision.detectors import DetectionResult
from app.vision.temporal_analyzer import IncidentState, TemporalAnalyzer


def _thresholds() -> DetectionThresholds:
    return DetectionThresholds(
        min_frame_confidence=0.5,
        possible_incident_seconds=2.0,
        confirmed_incident_seconds=5.0,
        temporal_window_seconds=10.0,
    )


def test_single_frame_spike_does_not_escalate():
    analyzer = TemporalAnalyzer(_thresholds())
    status = analyzer.update(DetectionResult("fire_smoke", confidence=0.9, signals={}), timestamp_seconds=0.0)
    assert status.state == IncidentState.NONE


def test_sustained_signal_escalates_through_states():
    analyzer = TemporalAnalyzer(_thresholds())
    states = []
    for i in range(60):
        t = i * 0.2
        result = DetectionResult("fire_smoke", confidence=0.9, signals={})
        states.append(analyzer.update(result, t).state)
    assert IncidentState.NONE in states
    assert IncidentState.POSSIBLE in states
    assert IncidentState.CONFIRMED in states
    # Once confirmed, state should not regress while signal remains strong.
    assert states[-1] == IncidentState.CONFIRMED


def test_signal_dropout_resets_persistence():
    analyzer = TemporalAnalyzer(_thresholds())
    for i in range(15):
        analyzer.update(DetectionResult("fire_smoke", confidence=0.9, signals={}), i * 0.2)
    # Long run of negatives should bring state back down.
    last_state = None
    for i in range(15, 15 + 60):
        last_state = analyzer.update(DetectionResult("fire_smoke", confidence=0.0, signals={}), i * 0.2).state
    assert last_state == IncidentState.NONE
