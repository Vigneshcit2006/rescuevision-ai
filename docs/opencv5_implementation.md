# Where OpenCV 5 Is Used in RescueVision AI

This document exists to make one thing checkable in under five minutes: that
OpenCV 5 performs substantive computer-vision work in this project, not just
a thin wrapper around a single detector call.

## Verifying the installed version

```bash
cd backend
python -c "import cv2; print(cv2.__version__)"
# -> 5.0.0
```

`backend/requirements.txt` pins `opencv-python==5.0.0.93` (the OpenCV 5 wheel
on PyPI). `backend/tests/test_vision_pipeline.py::test_opencv_version_is_5`
asserts `int(cv2.__version__.split(".")[0]) == 5` as a CI-enforced guard
against silently regressing to OpenCV 4.x.

## There is no separate ML object-detection model

RescueVision AI's vision layer contains **no YOLO, no neural network, and no
pretrained detector**. Every signal that feeds the agent comes directly from
classical OpenCV 5 operations. This is a deliberate choice for this
submission: it makes 100% of the detection logic auditable and keeps OpenCV
5 as the load-bearing technology, rather than a preprocessing step in front
of someone else's model.

## The pipeline stage-by-stage, with exact OpenCV 5 calls

All of the following live in `backend/app/vision/opencv_processor.py`
(`OpenCV5Processor.process()`), called once per frame by
`backend/app/vision/pipeline.py::VisionPipeline.process_frame()`.

| Step | OpenCV 5 call | Purpose |
|---|---|---|
| 1. Resize | `cv2.resize(image, (640, 480), interpolation=cv2.INTER_AREA)` | Normalizes any input resolution (webcam, uploaded file, synthetic demo frame) to a fixed working size before any measurement, so thresholds are comparable across sources. |
| 2. Denoise | `cv2.GaussianBlur(resized, (5, 5), 0)` | Suppresses per-pixel sensor/synthetic noise before color and background analysis. |
| 3. ROI extraction | NumPy slicing on a box computed from the configured `RegionOfInterest` (`app/configuration/config.py`) | Restricts all downstream analysis to the monitored region (e.g. the marked emergency route), not the whole frame. |
| 4. Color-space conversion | `cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)` and `cv2.COLOR_BGR2GRAY` | HSV powers the fire/smoke color-region analysis (hue/saturation are far more robust to lighting than raw BGR); grayscale powers motion/persistent-change analysis. |
| 5. Persistent-change detection | `cv2.absdiff(gray, reference_gray)` → `cv2.threshold(..., 25, 255, cv2.THRESH_BINARY)` → `cv2.morphologyEx(..., cv2.MORPH_OPEN, kernel)` | Diffs the current frame against a background frame captured once, early in the stream (`REFERENCE_FRAME_INDEX = 8`), so an object that stops moving (a fallen person, a parked vehicle) stays visible — see "why two change signals" below. |
| 6. Adaptive motion analysis | `cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=25, detectShadows=True).apply(blurred)` → `cv2.threshold(..., 200, 255, ...)` (drops MOG2's shadow value 127) → `cv2.morphologyEx(..., cv2.MORPH_OPEN, kernel)` | Produces a genuine motion score: what fraction of the ROI is *actively* changing right now, used as a secondary signal and reported to the agent as `motion_score`. |
| 7. Evidence-region measurement | `cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)` + `cv2.contourArea(c)` + `cv2.boundingRect(c)` | Measures the largest connected foreground region (both the motion mask and the persistent-change mask), giving an area ratio and a width/height bounding box used for posture (aspect-ratio) and occlusion-area estimation. |
| 8. Fire/smoke color-region analysis | `cv2.inRange(hsv_roi, lower, upper)` with two HSV bands (a warm hue/high-saturation band for flame, a low-saturation/mid-value band for smoke/haze) | Produces `fire_color_ratio` and `smoke_color_ratio` — the fraction of ROI pixels matching each color model — which is the primary fire/smoke confidence signal. |
| 9. Evidence-frame annotation | `cv2.rectangle` (ROI box) + `cv2.putText` (state/confidence label) on the resized frame, then `cv2.imencode(".jpg", annotated)` | Produces the human-readable evidence image stored to S3/local storage and shown in the incident-approval UI. |

### Why two different "something changed" signals exist

`cv2.createBackgroundSubtractorMOG2` is **adaptive**: anything that stops
moving is absorbed back into its modeled background within roughly its
`history` window. That is exactly correct for a live "is something moving
right now" score, but exactly wrong for detecting a person who has fallen
and stopped moving, or a vehicle that has parked across an emergency route —
those are the events this project most needs to keep seeing. The
fixed-reference `cv2.absdiff` signal (`persistent_change_ratio`,
`largest_persistent_contour_area_ratio`) does not decay, so it is what
`PersonDownDetector` and `RouteObstructionDetector`
(`backend/app/vision/detectors.py`) actually key off, while
`FireSmokeDetector` uses the color-ratio signals plus MOG2 motion as a minor
secondary term (fire/smoke keeps moving, so the adaptive signal is
appropriate there).

## Per-scenario detector logic (also OpenCV-derived, no ML model)

`backend/app/vision/detectors.py`:

- **`FireSmokeDetector`** — weighted combination of `fire_color_ratio`
  (55%), `smoke_color_ratio` (30%), and MOG2 `motion_score` (15%), each
  normalized against a configured threshold.
- **`PersonDownDetector`** — stateful: holds the last MOG2-motion-derived
  bounding-box aspect ratio (width/height) from when the subject was last
  actively moving (a fall is a burst of motion), combined with whether the
  persistent-change mask still shows a subject present (i.e. they have not
  simply walked out of frame).
- **`RouteObstructionDetector`** — the persistent-change contour's area
  ratio directly, normalized against the configured obstruction-area
  threshold.

## Temporal analysis (also not the detector's job)

`backend/app/vision/temporal_analyzer.py::TemporalAnalyzer` maintains a
rolling window (`temporal_window_seconds`, default 15s) of per-frame
confidence values and classifies the scenario into `none` / `possible` /
`confirmed` based on configured persistence durations
(`possible_incident_seconds`, `confirmed_incident_seconds`) and positive-
frame ratio — this is what turns a single noisy frame into (or prevents it
from becoming) a real incident, and it operates purely on the OpenCV-derived
per-frame confidence, with no additional vision processing of its own.

## Evidence extraction

`backend/app/vision/evidence_extractor.py::extract()` packages the
OpenCV-derived measurements, the temporal state, and the annotated evidence
JPEG (only once state is `possible` or `confirmed` — see
`test_evidence_frame_only_produced_once_signal_present`) into the
`IncidentCandidate.to_agent_evidence()` dict that is hand-off point to the
agent (`docs/agent-workflow.md`).

## Summary

Every confidence value the agent ever sees is traceable to one or more of:
a color-ratio measurement, a background-subtraction motion ratio, a
persistent-change area ratio, or a contour aspect ratio — all computed by
OpenCV 5 APIs listed above, all with configurable thresholds
(`backend/app/configuration/config.py`), and all unit-tested in
`backend/tests/test_vision_pipeline.py` and
`backend/tests/test_temporal_analyzer.py`.
