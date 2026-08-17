"""
OpenCV5Processor: the substantive OpenCV 5 processing stage of the pipeline.

This module is the canonical place documented in
docs/opencv5_implementation.md as "where OpenCV 5 does the work". It is
deliberately independent of any ML detector: everything here is classical
computer vision (color-space conversion, background subtraction, dense
optical flow, morphology, contour/ROI measurement) and is used both
*before* a detector runs (preprocessing, ROI extraction) and *after*
(motion scoring, evidence-frame annotation).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.configuration.config import RegionOfInterest


@dataclass
class ProcessedFrame:
    """Everything the OpenCV 5 stage derived from a single raw frame."""

    index: int
    timestamp_seconds: float
    resized_bgr: np.ndarray
    roi_bgr: np.ndarray
    roi_box_px: tuple[int, int, int, int]  # x, y, w, h in resized-frame pixels
    hsv: np.ndarray
    gray: np.ndarray
    motion_score: float  # 0-1, fraction of ROI pixels flagged as moving *right now* (MOG2)
    motion_mask: np.ndarray
    mean_brightness: float
    fire_color_ratio: float
    smoke_color_ratio: float
    largest_contour_area_ratio: float  # largest MOG2 foreground contour area / ROI area
    persistent_change_ratio: float  # fraction of ROI changed vs. the fixed reference background
    largest_persistent_contour_area_ratio: float  # largest such contour area / ROI area
    persistent_change_mask_roi: np.ndarray  # binary mask, ROI-sized


class OpenCV5Processor:
    """
    Stateful per-scenario processor: holds the background subtractor and the
    previous frame needed for motion/optical-flow analysis, so it must be
    instantiated once per video stream, not once per frame.

    OpenCV 5 APIs exercised here:
      - cv2.resize                         (frame preprocessing)
      - cv2.cvtColor (BGR2HSV, BGR2GRAY)   (color-space conversion)
      - cv2.createBackgroundSubtractorMOG2 (temporal motion analysis)
      - cv2.morphologyEx / getStructuringElement (noise removal on masks)
      - cv2.findContours / contourArea     (evidence-region measurement)
      - cv2.inRange                        (fire/smoke color-region analysis)
      - cv2.GaussianBlur                   (preprocessing / denoise)
      - cv2.absdiff                        (persistent-change detection vs. fixed reference)

    Note on why two change signals exist: cv2.createBackgroundSubtractorMOG2
    is *adaptive* -- it absorbs anything that stops moving back into the
    modeled background within roughly its `history` window. That is correct
    for a "motion score" but wrong for detecting a person who has fallen and
    stopped moving, or a vehicle that has parked in an emergency route: those
    events are exactly the ones MOG2 would erase. `persistent_change_ratio`
    instead diffs each frame against a background captured once, early in the
    stream, so a static change stays visible for as long as it is present.
    """

    TARGET_SIZE = (640, 480)
    REFERENCE_FRAME_INDEX = 8  # frame used to snapshot the "clean" background

    def __init__(self, roi: RegionOfInterest):
        self.roi = roi
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=25, detectShadows=True
        )
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self._reference_gray: np.ndarray | None = None
        self._frames_seen = 0

    def _roi_box(self, width: int, height: int) -> tuple[int, int, int, int]:
        x = int(self.roi.x * width)
        y = int(self.roi.y * height)
        w = int(self.roi.w * width)
        h = int(self.roi.h * height)
        return x, y, max(1, w), max(1, h)

    def process(self, image_bgr: np.ndarray, index: int, timestamp_seconds: float) -> ProcessedFrame:
        resized = cv2.resize(image_bgr, self.TARGET_SIZE, interpolation=cv2.INTER_AREA)
        blurred = cv2.GaussianBlur(resized, (5, 5), 0)

        x, y, w, h = self._roi_box(*self.TARGET_SIZE)
        roi = blurred[y : y + h, x : x + w]

        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
        roi_hsv = hsv[y : y + h, x : x + w]

        if self._frames_seen == self.REFERENCE_FRAME_INDEX or self._reference_gray is None:
            self._reference_gray = gray.copy()
        self._frames_seen += 1

        static_diff = cv2.absdiff(gray, self._reference_gray)
        static_diff = cv2.threshold(static_diff, 25, 255, cv2.THRESH_BINARY)[1]
        static_diff = cv2.morphologyEx(static_diff, cv2.MORPH_OPEN, self._kernel)
        roi_static_diff = static_diff[y : y + h, x : x + w]
        persistent_change_ratio = float(np.count_nonzero(roi_static_diff)) / float(roi_static_diff.size)
        persistent_contours, _ = cv2.findContours(roi_static_diff, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest_persistent_area = max((cv2.contourArea(c) for c in persistent_contours), default=0.0)
        largest_persistent_ratio = float(largest_persistent_area) / float(roi.shape[0] * roi.shape[1])

        fg_mask = self._bg_subtractor.apply(blurred)
        fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)[1]  # drop MOG2 shadow value (127)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self._kernel)
        roi_mask = fg_mask[y : y + h, x : x + w]

        motion_score = float(np.count_nonzero(roi_mask)) / float(roi_mask.size)

        contours, _ = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest_area = max((cv2.contourArea(c) for c in contours), default=0.0)
        largest_ratio = float(largest_area) / float(roi.shape[0] * roi.shape[1])

        fire_lower, fire_upper = np.array([0, 120, 150]), np.array([30, 255, 255])
        fire_mask = cv2.inRange(roi_hsv, fire_lower, fire_upper)
        fire_ratio = float(np.count_nonzero(fire_mask)) / float(fire_mask.size)

        smoke_lower, smoke_upper = np.array([0, 0, 90]), np.array([180, 40, 200])
        smoke_mask = cv2.inRange(roi_hsv, smoke_lower, smoke_upper)
        smoke_ratio = float(np.count_nonzero(smoke_mask)) / float(smoke_mask.size)

        return ProcessedFrame(
            index=index,
            timestamp_seconds=timestamp_seconds,
            resized_bgr=resized,
            roi_bgr=roi,
            roi_box_px=(x, y, w, h),
            hsv=hsv,
            gray=gray,
            motion_score=motion_score,
            motion_mask=fg_mask,
            mean_brightness=float(np.mean(gray)),
            fire_color_ratio=fire_ratio,
            smoke_color_ratio=smoke_ratio,
            largest_contour_area_ratio=largest_ratio,
            persistent_change_ratio=persistent_change_ratio,
            largest_persistent_contour_area_ratio=largest_persistent_ratio,
            persistent_change_mask_roi=roi_static_diff,
        )

    @staticmethod
    def annotate_evidence_frame(frame: ProcessedFrame, label: str, color: tuple[int, int, int] = (0, 0, 255)) -> np.ndarray:
        """Draw the ROI box and a label onto a copy of the frame for evidence export."""
        annotated = frame.resized_bgr.copy()
        x, y, w, h = frame.roi_box_px
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
        cv2.putText(annotated, label, (x, max(0, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        return annotated
