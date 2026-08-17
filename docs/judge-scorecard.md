# Judge Scorecard: Evidence Mapping

This maps every official judging criterion to the concrete, checkable
evidence in this repository. Every row links to a real file or test — none
of this is aspirational.

## Technical execution (30%)

| Claim | Evidence |
|---|---|
| OpenCV 5 actually installed and used substantively | `backend/requirements.txt` pins `opencv-python==5.0.0.93`; `backend/tests/test_vision_pipeline.py::test_opencv_version_is_5` enforces it in CI. Nine distinct OpenCV 5 operations used per frame — see `docs/opencv5_implementation.md`. |
| Modular vision pipeline (not a monolith) | `backend/app/vision/`: `video_source.py` → `opencv_processor.py` → `detectors.py` → `temporal_analyzer.py` → `evidence_extractor.py` → `pipeline.py`, matching the required `VideoSource -> FrameProcessor -> OpenCV5Processor -> Detector -> TemporalAnalyzer -> EvidenceExtractor -> IncidentCandidate` architecture exactly. |
| Temporal persistence, not single-frame triggers | `backend/app/vision/temporal_analyzer.py::TemporalAnalyzer`; `backend/tests/test_temporal_analyzer.py`. |
| Explicit, testable agent policy | `backend/app/agent/policy.py::AgentPolicy`; fully covered by `backend/tests/test_agent_policy.py` (6 tests over every decision branch). |
| Configuration-driven, not hard-coded | `backend/app/configuration/config.py` — every threshold, interval, and ROI referenced elsewhere is read from here. |
| Automated test suite passing | 31 tests across vision, temporal, policy, incident lifecycle, API, and failure cases — `cd backend && python -m pytest tests/`. |

## Innovation (20%)

| Claim | Evidence |
|---|---|
| Agentic perception→decision→action loop, not a chatbot over a fixed detection | `docs/agent-workflow.md` — the OBSERVE→ANALYZE→ASSESS→PLAN→ACT→VERIFY cycle in `backend/app/agent/agent.py`, where the OpenCV-derived confidence/state literally changes which tool the agent calls (verified by `test_agent_policy.py`, not just described in prose). |
| Two distinct OpenCV change-detection strategies used deliberately | `docs/opencv5_implementation.md`'s "why two change signals exist" — adaptive MOG2 motion vs. fixed-reference persistent-change diff, chosen per scenario based on whether the subject is expected to still be moving. |
| Adaptive, observable monitoring cadence | `MonitoringSession`/`SessionStatus.current_interval_seconds` (`backend/app/services/monitoring_service.py`) — visible live via `GET /api/system-status` and `/api/demo/status/{id}`. |

## Real-world impact (20%)

| Claim | Evidence |
|---|---|
| Three genuinely distinct disaster-response scenarios | Fire/smoke, person-down, route-obstruction — distinct detectors (`backend/app/vision/detectors.py`), distinct policy branches (`person_down` always requires human approval regardless of confidence). |
| Human-in-the-loop for high-risk decisions, not full autonomy | `docs/responsible-use.md`, `AgentPolicyConfig.person_down_always_requires_approval`; `POST /api/incidents/{id}/approve|reject`. |
| Honest about scope and limitations | `docs/failure-cases.md`, `docs/responsible-use.md` — explicit "no facial recognition, no medical diagnosis, no autonomous dispatch," explicit untested-limitation list. |

## User experience (10%)

| Claim | Evidence |
|---|---|
| Operational dashboard showing the full pipeline | `frontend/` — `/dashboard` shows VISION STATUS → INCIDENT → AGENT DECISION → ACTION → AWS STATUS live from the API. |
| Clear human-approval UI | `/incidents/:id` approve/reject flow. |
| Judge-facing deterministic demo control | `/demo` page driving `POST /api/demo/start` for all four scenarios with visibly different outcomes. |

## Documentation and presentation (10%)

| Claim | Evidence |
|---|---|
| Architecture diagrams reflecting actual implementation | `docs/architecture.md` (5 Mermaid diagrams: overall system, OpenCV pipeline, agentic workflow + decision table, AWS architecture, human-in-the-loop sequence). |
| Technical report, quickstart, demo script | `docs/technical-report.md`, `QUICKSTART.md`, `DEMO.md`. |
| Reproducible evaluation, not fabricated numbers | `evaluation/` — see `evaluation/reports/` for real, measured results with an explicit limitations section; anything not measured is labeled `NOT MEASURED`. |

## Cloud delivery, reproducibility, and responsible operation (10%)

| Claim | Evidence |
|---|---|
| Meaningful AWS integration (not decorative) | `docs/aws-architecture.md` — S3 (evidence), DynamoDB (incidents), SNS (alerts), each with a real local/AWS interface pair (`backend/app/aws/factory.py`). |
| Works fully without AWS credentials | Every test in `backend/tests/` runs local-only; `test_default_settings_select_local_backends_without_aws_credentials`. |
| Reproducible builds | Pinned dependency versions (`backend/requirements.txt`, `frontend/package.json`), `docker-compose.yml`, GitHub Actions CI (`.github/workflows/ci.yml`). |
| Responsible operation documented | `docs/responsible-use.md` — confidence thresholds, retention, access-control gaps disclosed rather than glossed over. |
