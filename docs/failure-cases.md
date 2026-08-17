# Failure Cases and Limitations

This document is intentionally candid. RescueVision AI is a hackathon-scope
prototype built on classical OpenCV 5 computer vision (color analysis,
background subtraction, contour geometry) plus a rule-based policy agent —
it is not a production-grade, ML-trained, real-world-validated detection
system. Treat every claim below as scoped to what has actually been tested
in this repository (`backend/tests/`), not as a general accuracy guarantee.

## Tested failure modes and how the system responds

| Scenario | What happens | Where it's enforced |
|---|---|---|
| **Low confidence signal** | The policy never sends a notification below the confidence/persistence thresholds; it stays in `CONTINUE_OBSERVATION` or `INCREASE_MONITORING`/`STORE_EVIDENCE_ONLY` instead. | `AgentPolicy.evaluate` gate on `min_frame_confidence`; `backend/tests/test_failure_cases.py::test_low_confidence_never_triggers_notification`. |
| **Invalid / corrupt video input** | `VideoSource.open()` raises `IOError` immediately rather than silently returning empty frames or crashing the monitoring thread. | `backend/app/vision/video_source.py::VideoSource.open`; `test_invalid_video_path_raises_ioerror`. |
| **Unknown scenario name** | `VisionPipeline(scenario=...)` raises `KeyError` at construction, before any frame is processed. | `backend/app/vision/pipeline.py`; `test_unknown_scenario_key_raises_value_error`. |
| **AWS not configured / unavailable** | The app never attempts to reach AWS unless `STORAGE_BACKEND`/`INCIDENT_BACKEND`/`NOTIFICATION_BACKEND` are explicitly set to `aws`, and even then, an AWS storage backend with an empty `S3_BUCKET` falls back to `LocalStorage` rather than trying (and failing) to write to a bucket named `""`. | `backend/app/aws/factory.py`; `test_default_settings_select_local_backends_without_aws_credentials`, `test_aws_storage_backend_without_bucket_falls_back_to_local`. |
| **Concurrent incidents across sessions** | Multiple monitoring sessions (e.g. two cameras/scenarios running at once) share one process-wide, thread-safe incident ID generator so concurrent `CREATE_INCIDENT` calls cannot collide and overwrite each other's rows. | `backend/app/logging/structured_logger.py::IncidentIdGenerator`; exercised manually via concurrent `/api/demo/start` calls during development (see project history) — not yet covered by an automated concurrency stress test (**gap, noted below**). |
| **Normal / no-incident scene** | Never escalates past `none`, never creates an incident, across a full synthetic clip. | `backend/tests/test_vision_pipeline.py::test_normal_scene_never_escalates`. |

## Known limitations (not yet tested, or tested and found lacking)

- **No real-world video validation.** All automated tests run against
  `SyntheticFrameSource`-rendered synthetic scenes (see
  `sample_data/README.md`), not real camera footage of an actual fire, fall,
  or obstruction. Real lighting, camera noise, occlusion, and crowding
  behave differently from the synthetic renders, and detector thresholds
  (`backend/app/configuration/config.py::DetectionThresholds`) were tuned
  against the synthetic scenes, not real footage. See
  `evaluation/reports/` for what was actually measured and its scope.
- **Poor lighting.** The fire/smoke color-ratio thresholds
  (`fire_color_ratio_threshold`, `smoke_color_ratio_threshold`) are HSV-band
  based; very low light reduces saturation/value readings and would likely
  suppress true detections (a false negative risk), while very bright,
  warm-toned lighting (e.g. sunset through a window) could plausibly
  register as a partial fire-color match (a false positive risk mitigated
  only by the temporal persistence requirement, not by the color model
  itself). **Not measured against real low-light footage.**
- **Camera movement.** The persistent-change detector
  (`OpenCV5Processor`'s fixed-reference `cv2.absdiff`) assumes a
  mostly-static camera. A moving/panning camera would make the entire frame
  register as "changed" relative to the reference, likely causing false
  positives for `person_down` and `route_obstruction` (both of which rely
  on that signal) until/unless the reference frame is re-captured. There is
  no camera-motion compensation (e.g. feature-based frame registration) in
  this implementation. **Not measured; a documented gap.**
- **Crowded scenes / multiple subjects.** The current contour-based
  approach reports only the *largest* connected foreground/change region
  per frame. A crowded scene with multiple overlapping subjects has not
  been tested and would likely under- or over-count as a single blob rather
  than distinguishing individuals.
- **False smoke-like objects.** Steam, fog, dust, grey clothing/furniture,
  or overcast window light can plausibly fall inside the smoke HSV band
  (`smoke_lower`/`smoke_upper` in `opencv_processor.py`) — the temporal
  persistence requirement (`confirmed_incident_seconds`) reduces but does
  not eliminate this risk for a persistent grey object. **Not measured
  against a labeled false-smoke test set** (none exists in this project).
- **Network interruption / agent unavailable.** There is no explicit retry/
  circuit-breaker logic around AWS SDK calls
  (`S3Storage`/`SNSNotificationService`/`DynamoDBIncidentRepository`) — an
  exception during `create_incident`/`store_evidence`/`notify` in AWS mode
  will currently propagate up and terminate that monitoring session's
  background thread rather than retrying or degrading gracefully. **This is
  a known gap**, not a tested-and-passing failure mode: local mode has no
  such dependency and is unaffected, but AWS-mode resilience under network
  interruption has not been implemented or tested here.
- **Small evaluation sample size.** `evaluation/reports/` evaluates 4
  synthetic scenario clips (one per scenario type) — precision/recall/F1
  figures computed from n=4 are illustrative of the pipeline's decision
  logic and latency, not a statistically meaningful accuracy claim. See
  that report's own limitations section.
- **Single-machine performance numbers.** FPS/latency figures in
  `evaluation/reports/` were measured on one development machine and are
  not a hardware-independent benchmark.

## What "fails safely" means here, concretely

The one property this project does defend with automated tests is: **a weak
or ambiguous signal never autonomously triggers a human notification.** Every
path to `SEND_ALERT` requires either (a) a `confirmed` state sustained for
`confirmed_incident_seconds` **and** confidence at/above
`human_approval_confidence_ceiling`, or (b) explicit human approval via the
dashboard. `person_down` additionally always requires human approval
regardless of confidence (`AgentPolicyConfig.person_down_always_requires_approval`).
Everything else in this document is a candidly-scoped gap or an untested
edge case, not a claim of resilience.
