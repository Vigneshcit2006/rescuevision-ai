# RescueVision AI — Technical Report

**OpenCV AI Competition 2026, powered by AWS**

---

## 1. Executive Summary

RescueVision AI is a disaster-response monitoring prototype that uses
OpenCV 5 for substantive per-frame computer vision, a temporal-persistence
layer to separate noise from real events, and an explicit agentic
decision loop (OBSERVE → ANALYZE → ASSESS → PLAN → ACT → VERIFY) that
selects and executes controlled tools — including routing higher-risk
decisions to a human operator for approval before any notification is
sent. It covers three scenarios (fire/smoke, person-down, emergency-route
obstruction), runs entirely without AWS credentials in local mode, and has
a real, working AWS integration (S3, DynamoDB, SNS) built with matching
local implementations behind common interfaces. Every number in this
report is either a real measurement (cited to `evaluation/reports/`) or
explicitly labeled `NOT MEASURED`.

## 2. Problem

Disaster-response monitoring (fire watch, fall detection in care settings,
emergency-route obstruction monitoring) is traditionally either fully
manual (a person watching camera feeds) or fully automated black-box
systems that flag an event with no visible reasoning and no human
checkpoint before escalation — a problematic tradeoff when false positives
are costly (needless dispatch) and false negatives are dangerous.

## 3. Target Users

Facility/site safety operators (warehouses, care facilities, industrial
sites) and emergency-operations-center staff who need continuous
camera monitoring with an auditable, human-approved escalation path — not
individual consumers, and not a replacement for trained first responders.

## 4. Real-world Impact

A monitoring system that (a) never fatigues, (b) explains *why* it thinks
something is happening in terms of concrete visual measurements rather than
an opaque score, and (c) keeps a human in the loop for the decisions that
matter, could reduce response latency for real incidents while avoiding the
trust erosion that comes from unexplainable false alarms. This is the
project's stated aspiration, not a measured outcome — no real-world
deployment or user study has been conducted.

## 5. Existing Problem

Most commercial "AI camera" fire/fall/intrusion products are closed-source
black boxes: an operator gets a score and a snapshot with no visibility
into what drove it, and often no distinction between "detected once" and
"detected and sustained." RescueVision AI's differentiator is architectural
transparency (every signal traces to a named OpenCV operation, every
decision traces to a testable policy branch) and a structural, not
optional, human-approval requirement for the riskiest decisions.

## 6. Proposed Solution

See §8-11 below and `docs/architecture.md` for the concrete implementation:
an OpenCV 5 vision pipeline producing structured evidence, a temporal
analyzer for persistence, and a policy-driven agent that creates incidents,
stores evidence, and either autonomously alerts (only at high confidence,
never for `person_down`) or routes to a human operator.

## 7. Innovation

The core innovation claimed here is narrow and specific: an agent whose
decision *branch* — not just its output text — is driven by live OpenCV
measurements, verified by an automated decision-table test
(`evaluation/reports/evaluation_report.md` §3a: 108/108 rows matched the
documented policy), combined with a structural (not prompt-level, not
optional) human-approval gate for the `person_down` scenario regardless of
confidence. This is a deliberately narrow, verifiable claim rather than a
broad one about "AI agents for disaster response" in general.

## 8. System Architecture

See `docs/architecture.md` for five Mermaid diagrams (overall system,
OpenCV pipeline, agentic workflow + decision table, AWS architecture,
human-in-the-loop sequence) reflecting the actual code structure in
`backend/app/`.

## 9. OpenCV 5 Implementation

See `docs/opencv5_implementation.md` for the full call-by-call breakdown.
Summary: `opencv-python==5.0.0.93` is pinned and version-checked by an
automated test (`test_opencv_version_is_5`). Nine distinct OpenCV 5
operations are used per frame across preprocessing (resize, blur),
color-space conversion (HSV, grayscale), two independent change-detection
strategies (adaptive `BackgroundSubtractorMOG2` for live motion, and a
fixed-reference `absdiff` for persistent change — chosen because MOG2 would
erase a person who has fallen and stopped moving), morphological cleanup,
contour/area measurement, color-region analysis (`inRange`), and evidence-
frame annotation/encoding. There is no ML object-detection model anywhere
in the vision layer.

## 10. Vision Pipeline

`VideoSource`/`SyntheticFrameSource` → `OpenCV5Processor` → per-scenario
`Detector` → `TemporalAnalyzer` (none → possible → confirmed, driven by
configurable persistence thresholds) → `EvidenceExtractor` →
`IncidentCandidate`. All thresholds live in
`backend/app/configuration/config.py`; none are hard-coded inline. See
`docs/opencv5_implementation.md` and `backend/tests/test_vision_pipeline.py`
/ `test_temporal_analyzer.py`.

## 11. Agentic Vision

See `docs/agent-workflow.md` for the full OBSERVE→VERIFY breakdown, the
controlled-tool list (`create_incident`, `store_evidence`,
`send_notification`, `request_human_approval`, `update_incident`,
`increase_monitoring_frequency`, `close_incident` — the agent's entire
attack surface), and the human-approval gating rules. The decision table is
independently verified in `evaluation/reports/evaluation_report.md` §3a
(108/108 rows matched).

## 12. AWS Architecture

See `docs/aws-architecture.md`. Services used: S3 (evidence), DynamoDB
(incidents), SNS (notifications), with EC2/ECS documented for compute and
CloudWatch Logs for aggregation (`deployment/DEPLOYMENT_STEPS.md`). Lambda
is deliberately not used (the monitoring loop is a persistent, stateful
per-camera process, not a good fit for short-lived stateless functions).
Every AWS integration has a matching local implementation selected purely
by environment variable, built by `backend/app/aws/factory.py` — this is
the actual code path in both modes, not a separate demo shim.

## 13. User Experience

A React/TypeScript/Vite dashboard (`frontend/`) with six pages: `/dashboard`
(live pipeline visualization: VISION STATUS → INCIDENT → AGENT DECISION →
ACTION → AWS STATUS), `/incidents` and `/incidents/:id` (including the
approve/reject human-approval UI), `/analytics` (metrics), `/system`
(health/backend-mode), and `/demo` (judge-facing deterministic scenario
control panel). See `docs/judge-scorecard.md` for the UX-criterion mapping.

## 14. Evaluation Methodology

See `docs/evaluation.md`. In short: the same 4 synthetic scenario clips used
by the automated test suite are run through the real `VisionPipeline` and
`AgentPolicy` to measure detection-escalation behavior, per-frame/decision
latency, and decision-table correctness; AWS-side metrics are explicitly
`NOT MEASURED` since no live AWS deployment exists.

## 15. Actual Results

From `evaluation/reports/evaluation_report.md` (run 2026-08-17T16:16:56Z):
all three incident scenarios (fire_smoke, person_down, route_obstruction)
reached `confirmed` state within 260 synthetic frames (14.27s / 10.87s /
11.07s respectively); `normal` never left `none`. The 108-row agent
decision-table test matched the documented policy 108/108 times. 70.37% of
confirmed-state decision-table rows required human approval under default
thresholds. **These are results on 4 deterministic synthetic clips, not a
real-world accuracy claim** — see that report's own limitations section.

## 16. Performance

From the same report: raw OpenCV vision-stage processing averaged ~63.8 FPS
(15.68ms/frame mean) across 800 pooled frames; agent policy decisions
averaged 0.0052ms (sub-millisecond, as expected for a pure function);
end-to-end (vision+agent) per-frame latency ranged 12.07-16.83ms depending
on scenario. All measured once, on one Windows development machine — not a
hardware-independent benchmark, and not repeated across multiple runs. See
`BENCHMARK.md`.

## 17. Failure Cases

See `docs/failure-cases.md` for the full, tested-vs-untested breakdown:
tested-and-passing (low confidence never notifies, invalid video path
raises cleanly, unknown scenario raises cleanly, AWS-mode with missing
bucket falls back to local rather than failing silently, concurrent
sessions no longer collide on incident IDs) versus known, disclosed,
untested gaps (poor lighting, camera movement, crowded scenes, false
smoke-like objects, AWS network-interruption resilience, small evaluation
sample size).

## 18. Responsible AI

See `docs/responsible-use.md`: no facial recognition, no identity
inference, no medical diagnosis, no autonomous emergency dispatch;
structural (not optional) human approval for `person_down` regardless of
confidence and for lower-confidence confirmed events in the other two
scenarios; disclosed gaps around authentication/access control and video
retention policy (left to the deploying operator, not prescribed here).

## 19. Security

No AWS credentials are hard-coded anywhere; `boto3` clients rely on the
standard credential chain (env vars or an attached IAM role).
`.env` is git-ignored; only `.env.example` (placeholders) is committed. No
AWS credential or secret is ever referenced by the frontend — the browser
only talks to this backend's own API. A least-privilege example IAM policy
(scoped to one S3 bucket, one DynamoDB table, one SNS topic) is provided in
`deployment/iam-policy.json`. **Known gap, disclosed**: this prototype's API
has no authentication/authorization layer — see `docs/responsible-use.md`
for what a real deployment would need to add before exposing it beyond a
trusted network.

## 20. Limitations

Summarized from `docs/failure-cases.md` and the evaluation report: synthetic-
only test data (no real-world footage validation), single-machine
performance numbers, no live AWS deployment or measurement, no automated
concurrency stress test beyond manual verification, no authentication
layer, and classical (not ML-trained) detection logic tuned against
synthetic scenes rather than real cameras.

## 21. Reproducibility

Pinned dependencies throughout: `backend/requirements.txt`
(`opencv-python==5.0.0.93`, `fastapi==0.115.6`, `pydantic==2.10.4`,
`pydantic-settings==2.7.0`, `uvicorn[standard]==0.34.0`, `boto3==1.35.90`,
`numpy==2.2.6`, `python-multipart==0.0.20`, `python-dotenv==1.0.1`),
`frontend/package.json` (React 18.3.1, react-router-dom 6.28.0, Vite
5.4.11, TypeScript 5.6.3), `docker-compose.yml` for a one-command local
stack, and `.github/workflows/ci.yml` running the full backend test suite
and frontend build on every push. `evaluation/run_evaluation.py` is
independently re-runnable and regenerates a fresh, timestamped results file
using only in-repository synthetic data — no external dataset or network
access required.

## 22. Future Work

Real-world video validation against an actual labeled dataset; an
ML-based detector (e.g. a lightweight fire/smoke or fall classifier) used
*alongside* — not instead of — the existing OpenCV signal pipeline, so the
current classical signals remain an auditable baseline; camera-motion
compensation for the persistent-change detector; an authentication/
authorization layer; multi-subject/crowded-scene handling; and an actual
verified AWS deployment with measured cloud latency/throughput/cost,
replacing the current `NOT MEASURED` placeholders with real numbers.

## 23. Conclusion

RescueVision AI demonstrates a complete, working perception → reasoning →
decision → action → observation → adaptation loop, built on genuinely
substantive OpenCV 5 processing, a real (if currently un-deployed) AWS
integration with full local-mode parity, and a structural human-approval
requirement for its highest-risk decision. Every number and every claim in
this report is either backed by a passing automated test, a real
measurement in `evaluation/reports/`, or explicitly disclosed as untested/
`NOT MEASURED` — the project's intent throughout has been to under-claim
rather than over-claim.
