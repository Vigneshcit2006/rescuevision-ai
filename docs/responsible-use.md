# Responsible AI and Use

RescueVision AI is a **decision-support tool**. It does not replace, and is
not designed to replace, trained emergency personnel, dispatchers, or first
responders. It is built for the OpenCV AI Competition 2026 as a prototype
demonstrating an agentic perception-decision-action loop with human
oversight, not as a certified life-safety system.

## What this system explicitly does NOT do

- **No facial recognition.** No component in this codebase identifies,
  matches, or tracks individual people's identity. All vision processing
  (`backend/app/vision/`) operates on aggregate color/motion/shape signals
  (fire color ratio, motion score, contour aspect ratio) — there is no face
  detection, face embedding, or re-identification model anywhere in this
  repository.
- **No identity inference of any kind.** The system does not attempt to
  determine who a detected person is, their age, gender, ethnicity, or any
  other personal characteristic. A "person_down" detection is a posture/
  motion signal about a *region of the frame*, not a person.
- **No medical diagnosis.** `person_down` detection is an aspect-ratio/
  motion heuristic (see `docs/opencv5_implementation.md`), not a clinical
  assessment of consciousness, injury, or medical condition. The
  recommended action text
  (`backend/app/agent/agent.py::RECOMMENDED_ACTION_TEXT`) is deliberately
  phrased as "escalate to a human operator for verification," never as a
  medical determination.
- **No autonomous dispatch of emergency services.** This system never
  contacts 911/112 or any emergency dispatch system directly. Its
  notification tool (`AgentTools.send_notification`) reaches an internal
  operator channel (SNS topic / mock), which a human is expected to act on.

## Human oversight is structural, not optional

- `person_down` incidents **always** require human approval before any
  notification is sent, regardless of detection confidence
  (`AgentPolicyConfig.person_down_always_requires_approval = True`,
  enforced in `AgentPolicy.evaluate` and covered by
  `backend/tests/test_agent_policy.py::test_person_down_always_requires_human_approval_even_at_high_confidence`).
- For `fire_smoke` and `route_obstruction`, human approval is required
  whenever confidence is below `human_approval_confidence_ceiling` (default
  `0.85`) — only a sustained, high-confidence signal triggers an autonomous
  alert, and even then the underlying evidence and rationale are always
  recorded and reviewable after the fact.
- Every human approval/rejection is persisted on the incident record itself
  (`Incident.human_approval_status`, set via
  `POST /api/incidents/{id}/approve|reject`), forming a durable audit trail
  of who decided what and when — see `docs/agent-workflow.md`.

## Confidence thresholds, false positives, and false negatives

All thresholds are configurable, not hard-coded per scenario
(`backend/app/configuration/config.py::DetectionThresholds`,
`AgentPolicyConfig`). Operators deploying this system are expected to tune
these for their specific camera placement, lighting, and monitored region —
default values were chosen against the synthetic demo scenes in this
repository (see `sample_data/README.md`), not validated against a
real-world dataset. See `docs/failure-cases.md` for concrete, tested and
untested failure modes (false smoke-like objects, poor lighting, camera
movement, etc.) and `evaluation/reports/` for what precision/recall figures
actually were measured, and their (small, synthetic-only) scope.

## Privacy and video retention

- Evidence frames are single annotated JPEG snapshots (not continuous video
  recordings) captured only once a scenario reaches `possible` or
  `confirmed` state (`EvidenceExtractor.extract`) — routine "nothing is
  happening" frames are never persisted to storage.
- In local mode, evidence is written to a filesystem directory
  (`LOCAL_STORAGE_DIR`) under the operator's own control; in AWS mode, to a
  single, explicitly-configured S3 bucket. This project does not implement
  an automatic retention/deletion policy — operators deploying this system
  in a real environment are responsible for configuring S3 lifecycle rules
  (or equivalent local cleanup) appropriate to their jurisdiction's video
  retention requirements, which this project does not attempt to prescribe.
- No evidence, incident data, or AWS credential is ever exposed to or
  reachable from the frontend except through this backend's own,
  access-controlled API (`docs/aws-architecture.md`).

## Access control and audit logs

- The API as implemented in this prototype does not include operator
  authentication/authorization (no login system) — this is a **known gap**
  for any real deployment; `deployment/DEPLOYMENT_STEPS.md` should be
  extended with an authentication layer (e.g. an API gateway with IAM/Cognito
  auth, or a reverse proxy with SSO) before exposing this system beyond a
  trusted local/demo network. This is explicitly out of scope for the
  current hackathon submission and is called out here rather than left
  implicit.
- Every agent decision, tool call, and human approval/rejection is written
  as a structured JSON log line
  (`backend/app/logging/structured_logger.py`) correlated by
  `incident_id` and `request_id`, forming the audit trail described in
  `docs/agent-workflow.md`. These logs are not currently shipped anywhere
  durable by default in local mode (they go to stdout); AWS-mode deployment
  should route them to CloudWatch Logs (`docs/aws-architecture.md`) for
  retention.

## Limitations, restated plainly

This is a hackathon prototype evaluated on synthetic, programmatically
generated video (see `sample_data/README.md`), with no real-world accuracy
validation, no authentication layer, and rule-based (not ML-trained)
detection logic. It should not be deployed to make unsupervised real-world
safety decisions. Its intended and demonstrated value is the
perception → reasoning → decision → action → observation → adaptation loop
with human approval as a first-class, structurally-enforced step — not a
finished, certified life-safety product.
