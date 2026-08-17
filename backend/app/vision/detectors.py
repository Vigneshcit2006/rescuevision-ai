"""
Scenario detectors: turn a single ProcessedFrame's OpenCV-derived measurements
into a per-frame confidence score for one scenario. These are intentionally
classical/rule-based (color ratio + motion + contour geometry) rather than a
black-box model, so that every confidence value is traceable to a concrete
OpenCV measurement. This satisfies the "OpenCV must perform substantive
processing, not just wrap a detector" requirement head-on: there is no
separate object-detection model in this project at all.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.configuration.config import DetectionThresholds
from app.vision.opencv_processor import ProcessedFrame


@dataclass
class DetectionResult:
    scenario: str
    confidence: float
    signals: dict[str, float]


class FireSmokeDetector:
    def __init__(self, thresholds: DetectionThresholds):
        self.t = thresholds

    def detect(self, frame: ProcessedFrame) -> DetectionResult:
        fire_signal = min(1.0, frame.fire_color_ratio / max(self.t.fire_color_ratio_threshold, 1e-6))
        smoke_signal = min(1.0, frame.smoke_color_ratio / max(self.t.smoke_color_ratio_threshold, 1e-6))
        motion_signal = min(1.0, frame.motion_score / max(self.t.motion_score_threshold, 1e-6))

        # Fire is weighted highest, smoke moderately; motion alone never triggers a positive.
        confidence = min(1.0, 0.55 * fire_signal + 0.30 * smoke_signal + 0.15 * motion_signal)
        if fire_signal == 0 and smoke_signal == 0:
            confidence = 0.0
        return DetectionResult(
            scenario="fire_smoke",
            confidence=confidence,
            signals={
                "fire_color_ratio": frame.fire_color_ratio,
                "smoke_color_ratio": frame.smoke_color_ratio,
                "motion_score": frame.motion_score,
            },
        )


class PersonDownDetector:
    """
    Stateful across frames: posture (aspect ratio) is only measurable while
    the subject is actively moving (from the MOG2 motion mask), so the last
    observed posture is *held* once motion stops. Combined with
    `persistent_change_ratio` (still differs from the fixed reference
    background, i.e. the subject has not left the scene) and the caller's
    TemporalAnalyzer duration tracking, this reproduces "person remains
    horizontal, no recovery movement" without needing a full pose model.
    """

    MIN_MOTION_CONTOUR_AREA_PX = 50

    def __init__(self, thresholds: DetectionThresholds):
        self.t = thresholds
        self._last_aspect_ratio: float | None = None

    def detect(self, frame: ProcessedFrame) -> DetectionResult:
        import cv2

        has_subject = frame.persistent_change_ratio > 0.02

        current_aspect_ratio = self._motion_aspect_ratio(frame)
        if current_aspect_ratio is not None:
            self._last_aspect_ratio = current_aspect_ratio

        aspect_ratio = self._last_aspect_ratio
        horizontal_signal = 0.0
        if aspect_ratio is not None:
            horizontal_signal = min(
                1.0, max(0.0, (aspect_ratio - 1.0) / max(self.t.horizontal_aspect_ratio_threshold - 1.0, 1e-6))
            )

        confidence = 0.0
        if has_subject and aspect_ratio is not None:
            confidence = min(1.0, 0.55 * horizontal_signal + 0.4)
        return DetectionResult(
            scenario="person_down",
            confidence=confidence,
            signals={
                "aspect_ratio": aspect_ratio or 0.0,
                "has_subject": float(has_subject),
                "motion_score": frame.motion_score,
                "persistent_change_ratio": frame.persistent_change_ratio,
            },
        )

    @staticmethod
    def _motion_aspect_ratio(frame: ProcessedFrame) -> float | None:
        import cv2

        contours, _ = cv2.findContours(frame.motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < PersonDownDetector.MIN_MOTION_CONTOUR_AREA_PX:
            return None
        _, _, w, h = cv2.boundingRect(largest)
        if h == 0:
            return None
        return w / h


class RouteObstructionDetector:
    def __init__(self, thresholds: DetectionThresholds):
        self.t = thresholds

    def detect(self, frame: ProcessedFrame) -> DetectionResult:
        # Persistent change (vs. fixed reference) is what distinguishes a
        # vehicle/object parked across the route from one merely passing
        # through, which MOG2's adaptive motion mask would erase once it stops.
        area_signal = min(
            1.0, frame.largest_persistent_contour_area_ratio / max(self.t.obstruction_area_ratio_threshold, 1e-6)
        )
        confidence = area_signal
        return DetectionResult(
            scenario="route_obstruction",
            confidence=confidence,
            signals={
                "occluded_area_ratio": frame.largest_persistent_contour_area_ratio,
                "motion_score": frame.motion_score,
            },
        )


DETECTORS = {
    "fire_smoke": FireSmokeDetector,
    "person_down": PersonDownDetector,
    "route_obstruction": RouteObstructionDetector,
}
