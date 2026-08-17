"""
VideoSource: uniform frame iterator over webcam, video file, or a
deterministic synthetic generator used for demo mode.

Uses OpenCV 5 VideoCapture for file/webcam ingestion.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

import cv2
import numpy as np


@dataclass
class Frame:
    index: int
    timestamp_seconds: float
    image_bgr: np.ndarray


class VideoSource:
    """Wraps cv2.VideoCapture for a file path or webcam index."""

    def __init__(self, source: str | int):
        self.source = source
        self._cap: Optional[cv2.VideoCapture] = None

    def open(self) -> "VideoSource":
        self._cap = cv2.VideoCapture(self.source)
        if not self._cap.isOpened():
            raise IOError(f"Unable to open video source: {self.source}")
        return self

    @property
    def fps(self) -> float:
        if self._cap is None:
            return 0.0
        fps = self._cap.get(cv2.CAP_PROP_FPS)
        return fps if fps and fps > 0 else 30.0

    def frames(self) -> Iterator[Frame]:
        if self._cap is None:
            self.open()
        index = 0
        assert self._cap is not None
        fps = self.fps
        while True:
            ok, image = self._cap.read()
            if not ok:
                break
            yield Frame(index=index, timestamp_seconds=index / fps, image_bgr=image)
            index += 1

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "VideoSource":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()


class SyntheticFrameSource:
    """
    Deterministic, seed-free synthetic frame generator used by demo mode.

    Renders programmatically-composited scenes (no external/copyrighted
    media) so the demo is fully reproducible: the same scenario name always
    produces the same frame sequence. See docs/failure-cases.md and
    sample_data/README.md for what these scenes represent.
    """

    WIDTH = 640
    HEIGHT = 480

    def __init__(self, scenario: str, num_frames: int = 150, fps: float = 15.0):
        self.scenario = scenario
        self.num_frames = num_frames
        self._fps = fps

    @property
    def fps(self) -> float:
        return self._fps

    def frames(self) -> Iterator[Frame]:
        for i in range(self.num_frames):
            t = i / self._fps
            img = self._render(i, t)
            yield Frame(index=i, timestamp_seconds=t, image_bgr=img)

    def _base_scene(self) -> np.ndarray:
        img = np.full((self.HEIGHT, self.WIDTH, 3), (60, 50, 40), dtype=np.uint8)  # dim room, BGR
        cv2.rectangle(img, (0, self.HEIGHT - 80), (self.WIDTH, self.HEIGHT), (70, 70, 70), -1)  # floor
        return img

    def _render(self, i: int, t: float) -> np.ndarray:
        img = self._base_scene()
        if self.scenario == "normal":
            cv2.rectangle(img, (250, 150), (390, 300), (90, 60, 40), -1)  # static furniture
        elif self.scenario == "fire_smoke":
            self._render_fire(img, i, t)
        elif self.scenario == "person_down":
            self._render_person(img, i, t)
        elif self.scenario == "route_obstruction":
            self._render_obstruction(img, i, t)
        else:
            raise ValueError(f"Unknown synthetic scenario: {self.scenario}")
        noise = np.random.default_rng(seed=i).integers(-4, 4, img.shape, dtype=np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        return img

    def _render_fire(self, img: np.ndarray, i: int, t: float) -> None:
        # Fire grows from frame 30 onward; before that, an ambiguous flicker only.
        onset = 30
        cx, cy = 320, 340
        if i < onset:
            radius = 6
        else:
            growth = min(1.0, (i - onset) / 60.0)
            radius = int(6 + growth * 55)
        flicker = 1.0 + 0.08 * np.sin(i * 0.9)
        r = max(3, int(radius * flicker))
        # Fire core (orange/red in BGR)
        cv2.circle(img, (cx, cy), r, (20, 90, 220), -1)
        cv2.circle(img, (cx, cy - r // 2), max(2, r // 2), (10, 140, 255), -1)
        if i >= onset + 20:
            # Smoke plume rising above the flame, grey and drifting
            smoke_h = min(200, (i - onset - 20) * 2)
            for k in range(0, smoke_h, 12):
                sx = cx + int(10 * np.sin((i + k) * 0.15))
                sy = cy - r - k
                if sy < 0:
                    break
                cv2.circle(img, (sx, sy), 18 + k // 10, (140, 140, 140), -1)

    def _render_person(self, img: np.ndarray, i: int, t: float) -> None:
        stand_until = 40
        fall_end = 55
        if i < stand_until:
            x, y, w, h = 300, 120, 40, 220
        elif i < fall_end:
            progress = (i - stand_until) / (fall_end - stand_until)
            w = int(40 + progress * 160)
            h = int(220 - progress * 170)
            x, y = 280, 120 + int(progress * 220)
        else:
            x, y, w, h = 260, 330, 200, 50
        cv2.rectangle(img, (x, y), (x + w, y + h), (80, 130, 160), -1)

    def _render_obstruction(self, img: np.ndarray, i: int, t: float) -> None:
        # Restricted emergency-route region drawn as a translucent overlay guide
        route = (200, 200, 240, 380)  # x1,y1,x2,y2
        cv2.rectangle(img, (route[0], route[1]), (route[2], route[3]), (50, 90, 50), 2)
        onset = 25
        if i >= onset:
            growth = min(1.0, (i - onset) / 40.0)
            w = int(20 + growth * 220)
            # High-contrast (bright, distinct from the dim room) so the
            # persistent-change detector reliably separates it from background.
            cv2.rectangle(img, (210, 210), (210 + w, 370), (210, 205, 195), -1)  # vehicle-like block
