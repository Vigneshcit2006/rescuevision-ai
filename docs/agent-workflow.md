# Agentic Vision Workflow

This document describes how RescueVision AI satisfies the Agentic Vision
requirement: OpenCV 5's visual output does not just get displayed or
explained by a chatbot — it drives an explicit state machine that selects
and executes controlled tools, some of which require human approval before
they take effect.

## The state machine

`backend/app/agent/state_machine.py` defines:

```
OBSERVE -> ANALYZE -> ASSESS -> PLAN -> ACT -> VERIFY
```

Every call to `VisionAgent.step(candidate)`
(`backend/app/agent/agent.py`) runs through all six states exactly once,
for one `IncidentCandidate` produced by the vision pipeline, and returns an
`AgentCycleResult` containing the full trace (state, human-readable detail,
timestamp for each step) plus the incident (if any) and the concrete action
result. That trace is what `GET /api/demo/status/{session_id}` exposes as
`last_trace`, and it is what an incident's full audit trail is built from.

| State | What actually happens |
|---|---|
| **OBSERVE** | The agent receives one `IncidentCandidate.to_agent_evidence()` dict — the OpenCV-derived confidence, state (`none`/`possible`/`confirmed`), duration, region, motion score, and raw detector signals. This is real visual evidence, not a static/fixed example. |
| **ANALYZE** | The evidence is logged/inspected (state, confidence, duration) before any decision is made. |
| **ASSESS** | `AgentPolicy.evaluate(evidence)` (`backend/app/agent/policy.py`) — a pure, deterministic function — computes a `severity` (`NONE`/`LOW`/`MEDIUM`/`HIGH`) purely from the evidence and the configured thresholds in `backend/app/configuration/config.py` (`DetectionThresholds`, `AgentPolicyConfig`). No severity value is hard-coded per scenario; it falls out of confidence/duration/state. |
| **PLAN** | The same `AgentPolicy.evaluate()` call also returns a `decision` (`CONTINUE_OBSERVATION` / `INCREASE_MONITORING` / `CREATE_INCIDENT`), an `action` (`NONE` / `STORE_EVIDENCE_ONLY` / `SEND_ALERT` / `REQUEST_HUMAN_APPROVAL`), whether human approval is required, and the next adaptive observation interval. |
| **ACT** | The agent calls one or more of its controlled tools (`backend/app/agent/tools.py::AgentTools`) to actually execute the plan — see below. This is the step where OpenCV's output causes a real side effect (an incident row is written, an S3/local evidence file is stored, an SNS/mock notification fires, or a human-approval request is created), not just a description of one. |
| **VERIFY** | The tool call's actual return value (e.g. "was the notification sent?", "was the incident created?") is recorded as `action_result` and appended to the trace, closing the loop before the next OBSERVE. |

## Controlled tools (the entire agent attack surface)

`AgentTools` in `backend/app/agent/tools.py` is the **only** interface the
agent has to the outside world — it cannot call AWS SDKs, write files, or
send notifications directly. Each tool is narrow and logged:

- `store_evidence(incident_id, jpeg_bytes)` → delegates to the configured
  `StorageService` (local filesystem or S3).
- `create_incident(incident)` / `update_incident(incident_id, **fields)` →
  delegates to the configured `IncidentRepository` (SQLite or DynamoDB).
- `send_notification(incident)` → delegates to the configured
  `NotificationService` (in-memory mock or SNS) — **only called when the
  policy decision is `SEND_ALERT` and `requires_human_approval` is
  `False`.**
- `request_human_approval(incident_id)` → sets
  `human_approval_status = "PENDING"`; no alert is sent until a human
  operator calls `POST /api/incidents/{id}/approve`.
- `increase_monitoring_frequency(region, interval_seconds)` → logged; the
  returned `next_observation_seconds` is what the monitoring loop reports
  as the current adaptive interval.
- `close_incident(incident_id, reason)` → called automatically once a
  previously-open incident's signal genuinely clears (state returns to
  `none`).

## Why the visual result actually changes the outcome (not a fixed script)

`backend/tests/test_agent_policy.py` exercises every branch directly:
`state=none` → `CONTINUE_OBSERVATION`/`NONE`; `state=possible` →
`INCREASE_MONITORING`/`STORE_EVIDENCE_ONLY`; `state=confirmed` with
confidence below `human_approval_confidence_ceiling` (default `0.85`) →
`CREATE_INCIDENT`/`REQUEST_HUMAN_APPROVAL`; `state=confirmed` with
confidence at/above that ceiling → `CREATE_INCIDENT`/`SEND_ALERT` sent
autonomously — **except** `person_down`, which
`AgentPolicyConfig.person_down_always_requires_approval` (default `True`)
routes through human approval unconditionally, regardless of confidence,
because this project explicitly does not perform medical diagnosis or
autonomous emergency dispatch for a person's physical safety. Changing the
OpenCV-derived confidence or duration value changes which branch executes —
this is verified by unit tests, not asserted only in prose.

## Human-in-the-loop

When `requires_human_approval` is `True`, the incident is created with
`human_approval_status = "PENDING"` and **no notification is sent**. A human
operator reviews the evidence image and rationale via the dashboard
(`POST /api/incidents/{id}/approve` or `/reject`), and only `approve`
triggers `NotificationService.notify()` (see
`backend/app/api/routes.py::approve_incident`). The human decision
(approver identity, notes, resulting status) is persisted on the incident
record itself, forming the audit trail entry for that decision.

## Adaptive monitoring loop

`backend/app/services/monitoring_service.py::MonitoringSession` runs one
scenario's pipeline+agent on a background thread. Each cycle's
`PolicyOutcome.next_observation_seconds` (from `MonitoringConfig`: `5.0s`
normal / `2.0s` possible / `0.5s` confirmed, all configurable) is recorded in
`SessionStatus.current_interval_seconds` and is visible via
`GET /api/demo/status/{session_id}` and `GET /api/system-status` — this is
what makes the "analyze more often as suspicion increases" behavior
observable, not just implemented. (Demo/upload playback itself advances at
the source frame rate so a judge can watch a full escalation in seconds;
`current_interval_seconds` reports what a live deployment would use to pace
its own camera polling, since it is not throttling pre-recorded/synthetic
frames — see the comment in `MonitoringSession.__init__`.)
