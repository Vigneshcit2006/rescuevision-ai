"""
VisionPipeline: wires VideoSource -> OpenCV5Processor -> Detector ->
TemporalAnalyzer -> EvidenceExtractor -> IncidentCandidate, exactly as
specified in the architecture. One VisionPipeline instance == one
monitored camera/region/scenario.
"""
from __future__ import annotations

from typing import Iterator

from app.configuration.config import DetectionThresholds, RegionOfInterest, ScenarioType
from app.vision.detectors import DETECTORS
from app.vision.evidence_extractor import IncidentCandidate, extract
from app.vision.opencv_processor import OpenCV5Processor
from app.vision.temporal_analyzer import TemporalAnalyzer
from app.vision.video_source import Frame


class VisionPipeline:
    def __init__(
        self,
        scenario: ScenarioType,
        thresholds: DetectionThresholds,
        roi: RegionOfInterest,
        region_name: str = "default_zone",
    ):
        self.scenario = scenario
        self.region_name = region_name
        self.processor = OpenCV5Processor(roi)
        self.detector = DETECTORS[scenario](thresholds)
        self.temporal = TemporalAnalyzer(thresholds)

    def process_frame(self, frame: Frame) -> IncidentCandidate:
        processed = self.processor.process(frame.image_bgr, frame.index, frame.timestamp_seconds)
        detection = self.detector.detect(processed)
        temporal_status = self.temporal.update(detection, frame.timestamp_seconds)
        return extract(self.scenario, processed, detection, temporal_status, self.region_name)

    def run(self, frames: Iterator[Frame]) -> Iterator[IncidentCandidate]:
        for frame in frames:
            yield self.process_frame(frame)
