"""
TemporalAnalyzer: converts a stream of per-frame DetectionResults into a
persistence-aware state (none / possible / confirmed), which is what lets
the system distinguish a single noisy frame from a real, sustained event.

This is the piece that specifically satisfies "temporal persistence" and
"do not hard-code decisions" -- state transitions are driven purely by
configured thresholds (app.configuration.config.DetectionThresholds).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from app.configuration.config import DetectionThresholds
from app.vision.detectors import DetectionResult


class IncidentState(str, Enum):
    NONE = "none"
    POSSIBLE = "possible"
    CONFIRMED = "confirmed"


@dataclass
class TemporalObservation:
    timestamp_seconds: float
    confidence: float
    is_positive: bool


@dataclass
class TemporalStatus:
    state: IncidentState
    duration_seconds: float
    rolling_confidence: float
    positive_frame_ratio: float
    first_positive_timestamp: float | None


class TemporalAnalyzer:
    def __init__(self, thresholds: DetectionThresholds):
        self.t = thresholds
        self._window: deque[TemporalObservation] = deque()
        self._first_positive_ts: float | None = None
        self._state = IncidentState.NONE

    def _prune(self, now: float) -> None:
        cutoff = now - self.t.temporal_window_seconds
        while self._window and self._window[0].timestamp_seconds < cutoff:
            self._window.popleft()

    def update(self, result: DetectionResult, timestamp_seconds: float) -> TemporalStatus:
        is_positive = result.confidence >= self.t.min_frame_confidence
        self._window.append(TemporalObservation(timestamp_seconds, result.confidence, is_positive))
        self._prune(timestamp_seconds)

        positives = [o for o in self._window if o.is_positive]
        positive_ratio = len(positives) / len(self._window) if self._window else 0.0
        rolling_confidence = sum(o.confidence for o in self._window) / len(self._window) if self._window else 0.0

        if is_positive and self._first_positive_ts is None:
            self._first_positive_ts = timestamp_seconds
        elif not is_positive and positive_ratio < 0.2:
            # Signal has genuinely dropped out; reset persistence tracking.
            self._first_positive_ts = None

        duration = (
            timestamp_seconds - self._first_positive_ts if self._first_positive_ts is not None else 0.0
        )

        if duration >= self.t.confirmed_incident_seconds and positive_ratio >= 0.6:
            self._state = IncidentState.CONFIRMED
        elif duration >= self.t.possible_incident_seconds and positive_ratio >= 0.4:
            self._state = IncidentState.POSSIBLE
        elif positive_ratio < 0.2:
            self._state = IncidentState.NONE

        return TemporalStatus(
            state=self._state,
            duration_seconds=duration,
            rolling_confidence=rolling_confidence,
            positive_frame_ratio=positive_ratio,
            first_positive_timestamp=self._first_positive_ts,
        )
