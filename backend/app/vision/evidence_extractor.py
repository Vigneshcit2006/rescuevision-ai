"""
EvidenceExtractor: packages the OpenCV-derived measurements and an annotated
evidence frame into the structured IncidentCandidate the agent consumes.
This is the hand-off point between "vision" and "agent" in the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.vision.detectors import DetectionResult
from app.vision.opencv_processor import OpenCV5Processor, ProcessedFrame
from app.vision.temporal_analyzer import TemporalStatus


@dataclass
class IncidentCandidate:
    scenario: str
    state: str  # none | possible | confirmed
    confidence: float
    duration_seconds: float
    region: str
    motion_score: float
    positive_frame_ratio: float
    signals: dict[str, float]
    evidence_frame_jpeg: bytes | None
    frame_index: int
    timestamp_seconds: float

    def to_agent_evidence(self) -> dict:
        """The exact structured-evidence contract handed to the agent."""
        return {
            "event_type": f"possible_{self.scenario}" if self.state == "possible" else self.scenario,
            "state": self.state,
            "confidence": round(self.confidence, 4),
            "duration_seconds": round(self.duration_seconds, 2),
            "region": self.region,
            "motion_score": round(self.motion_score, 4),
            "positive_frame_ratio": round(self.positive_frame_ratio, 4),
            "evidence_available": self.evidence_frame_jpeg is not None,
            "signals": self.signals,
        }


def extract(
    scenario: str,
    frame: ProcessedFrame,
    detection: DetectionResult,
    temporal: TemporalStatus,
    region_name: str = "default_zone",
) -> IncidentCandidate:
    evidence_jpeg: bytes | None = None
    if temporal.state.value != "none":
        annotated = OpenCV5Processor.annotate_evidence_frame(
            frame, label=f"{scenario.upper()} {temporal.state.value} {detection.confidence:.2f}"
        )
        ok, buf = cv2.imencode(".jpg", annotated)
        evidence_jpeg = buf.tobytes() if ok else None

    return IncidentCandidate(
        scenario=scenario,
        state=temporal.state.value,
        confidence=temporal.rolling_confidence,
        duration_seconds=temporal.duration_seconds,
        region=region_name,
        motion_score=frame.motion_score,
        positive_frame_ratio=temporal.positive_frame_ratio,
        signals=detection.signals,
        evidence_frame_jpeg=evidence_jpeg,
        frame_index=frame.index,
        timestamp_seconds=frame.timestamp_seconds,
    )
