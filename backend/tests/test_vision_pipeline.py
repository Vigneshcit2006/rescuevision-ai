"""
Vision pipeline tests. Verifies OpenCV 5 is actually installed, that each
scenario detector escalates none -> possible -> confirmed on its matching
synthetic scenario, and that a normal (no-incident) scene never escalates
even when run for the full clip.
"""
import cv2
import pytest

from app.vision.pipeline import VisionPipeline
from app.vision.video_source import SyntheticFrameSource


def test_opencv_version_is_5():
    major = int(cv2.__version__.split(".")[0])
    assert major == 5, f"Expected OpenCV 5.x, found {cv2.__version__} -- NOT VERIFIED as OpenCV 5"


@pytest.mark.parametrize("scenario", ["fire_smoke", "person_down", "route_obstruction"])
def test_scenario_escalates_to_confirmed(settings, scenario):
    src = SyntheticFrameSource(scenario, num_frames=260, fps=15.0)
    pipeline = VisionPipeline(scenario, settings.thresholds, settings.region_of_interest, region_name=scenario)

    states_seen = set()
    for candidate in pipeline.run(src.frames()):
        states_seen.add(candidate.state)

    assert "none" in states_seen, "Scenario should start with no detected incident"
    assert "possible" in states_seen, f"{scenario} never reached 'possible' state"
    assert "confirmed" in states_seen, f"{scenario} never reached 'confirmed' state"


def test_normal_scene_never_escalates(settings):
    src = SyntheticFrameSource("normal", num_frames=260, fps=15.0)
    pipeline = VisionPipeline(settings.default_scenario, settings.thresholds, settings.region_of_interest)

    states_seen = {c.state for c in pipeline.run(src.frames())}
    assert states_seen == {"none"}, f"Normal scene should never escalate, saw states: {states_seen}"


def test_evidence_frame_only_produced_once_signal_present(settings):
    src = SyntheticFrameSource("fire_smoke", num_frames=260, fps=15.0)
    pipeline = VisionPipeline("fire_smoke", settings.thresholds, settings.region_of_interest)

    for candidate in pipeline.run(src.frames()):
        if candidate.state == "none":
            assert candidate.evidence_frame_jpeg is None
        else:
            assert candidate.evidence_frame_jpeg is not None
