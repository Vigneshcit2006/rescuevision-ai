# RescueVision AI - Evaluation Report

**Source of truth for every number below:**
`evaluation/results/evaluation_20260817T161656Z.json`
(also mirrored at `evaluation/results/latest.json`, which is overwritten on
every run).

- Run timestamp (UTC): 2026-08-17T16:16:56Z
- Total run duration: 137.01s
- Produced by: `python evaluation/run_evaluation.py`
- Environment: Python 3.11.9, Windows-10-10.0.26200-SP0, OpenCV 5.0.0
  (measured on this single development machine -- see Limitations)

No number in this report was estimated, rounded up, or invented. Every figure
is read directly out of the JSON file cited above, which is itself the direct
output of instrumented calls into `backend/app/vision/*` and
`backend/app/agent/policy.py`. Where a number cannot be measured in this
environment (live AWS), it is labeled `NOT MEASURED` with a reason, per
project policy -- never a placeholder value.

---

## 1. Vision detection quality (n=4 synthetic scenarios)

**Methodology.** Each of the 4 scenarios from `SyntheticFrameSource` (`fire_smoke`,
`person_down`, `route_obstruction`, `normal`) was run for 260 frames at 15 fps
through its matching `VisionPipeline`. 260 frames (~17.3s of simulated time)
was taken from `backend/tests/test_vision_pipeline.py`, and empirically
confirmed here to be sufficient for every incident scenario to reach
`confirmed` (see "frame index of first confirmed" below, all well under 260).
Ground truth: `fire_smoke` / `person_down` / `route_obstruction` must reach
`confirmed`; `normal` must never reach `possible` or `confirmed`.

| Scenario | Reached possible | Reached confirmed | Time to possible (s) | Time to confirmed (s) | Frame # of first confirmed | Peak confidence |
|---|---|---|---|---|---|---|
| fire_smoke | Yes | Yes | 9.53 | 14.27 | 214 | 0.389 |
| person_down | Yes | Yes | 5.93 | 10.87 | 163 | 0.423 |
| route_obstruction | Yes | Yes | 6.13 | 11.07 | 166 | 0.606 |
| normal | No | No | - | - | - | 0.000 |

### Confusion matrix (n=4, positive class = "reaches confirmed")

| | Predicted incident | Predicted normal |
|---|---|---|
| **Actual incident** (3 scenarios) | TP = 3 | FN = 0 |
| **Actual normal** (1 scenario) | FP = 0 | TN = 1 |

`normal` also never reached `possible` (an even stricter pass than the ground
truth requires).

### Metrics (n=4, illustrative only -- see Limitations)

| Metric | Value |
|---|---|
| Precision | 1.0 |
| Recall | 1.0 |
| F1 | 1.0 |
| False positive rate | 0.0 |
| False negative rate | 0.0 |

**These are perfect scores on 4 deterministic synthetic clips, not a claim of
real-world accuracy.** With n=4 and zero natural variation between runs (the
generator is deterministic), a single logic bug would flip a whole scenario's
result to 0% rather than showing up as a partial-accuracy dip -- there is no
statistical noise to average out. Treat this section as "the escalation logic
behaves as specified on the only test scenes that exist," not as a benchmark
result.

---

## 2. Performance

All timings measured on this development machine only (Windows, Intel64
Family 6 Model 142, single run). No claim is made about performance on the
judge's or any other hardware.

### 2a. Raw per-frame vision cost (`OpenCV5Processor.process()` + detector `.detect()` + `TemporalAnalyzer.update()`, per frame, synthetic-frame rendering excluded from the timed region)

200 frames per scenario:

| Scenario | Mean (ms) | Median (ms) | p95 (ms) | Derived FPS (from mean) |
|---|---|---|---|---|
| fire_smoke | 18.64 | 16.48 | 30.37 | 53.66 |
| person_down | 13.23 | 12.51 | 17.32 | 75.58 |
| route_obstruction | 14.44 | 13.65 | 18.43 | 69.23 |
| normal | 17.32 | 15.40 | 27.83 | 57.73 |
| **Combined (800 frames pooled)** | **15.68** | **14.75** | **20.74** | **63.76** |

### 2b. Agent decision latency (`AgentPolicy.evaluate()` alone, pure function)

3000 calls (15 representative evidence dicts x 200 repeats):

| Mean (ms) | Median (ms) | p95 (ms) | Max (ms) |
|---|---|---|---|
| 0.0052 | 0.0042 | 0.0089 | 0.163 |

Confirms the policy layer is sub-millisecond, as expected for a pure/
deterministic function with no I/O -- measured, not assumed.

### 2c. End-to-end latency (`VisionPipeline.process_frame()` including evidence extraction/JPEG encoding, then `AgentPolicy.evaluate()`, per frame)

200 frames per scenario:

| Scenario | Mean (ms) | Median (ms) | p95 (ms) | Derived FPS (from mean) |
|---|---|---|---|---|
| fire_smoke | 16.83 | 16.10 | 22.59 | 59.43 |
| person_down | 16.36 | 15.48 | 21.40 | 61.13 |
| route_obstruction | 14.76 | 14.40 | 19.37 | 67.75 |
| normal | 12.07 | 11.37 | 14.71 | 82.88 |

(End-to-end figures are close to, and in some cases lower than, the "raw
vision cost only" figures in 2a -- both are noisy single-run wall-clock
measurements on a shared machine, not a controlled benchmark; the differences
between 2a and 2c are within measurement noise, not a meaningful signal that
evidence extraction is free.)

---

## 3. Agent evaluation

### 3a. Decision-table test

**Methodology.** Every combination of scenario (`fire_smoke`, `person_down`,
`route_obstruction`) x state (`none`, `possible`, `confirmed`) x 12 confidence
values (0.0 through 1.0, including values just below/above the
`min_frame_confidence` and `human_approval_confidence_ceiling` boundaries) was
run through the real `AgentPolicy.evaluate()`. Each result was compared
against an independent re-derivation of the documented rules in
`backend/app/agent/policy.py` (severity/decision/action/approval logic),
computed separately in the evaluation script rather than re-using the
implementation's own branches.

- Total rows: **108**
- Rows matching the documented policy: **108 / 108 (100%)**
- Mismatches: **0**

Full row-by-row output (scenario, state, confidence, actual vs. expected
outcome, match flag) is in the `agent_evaluation.rows` array of the results
JSON.

### 3b. Human-escalation rate

Among the 108 decision-table rows, those with `state == "confirmed"` and
confidence at/above `min_frame_confidence` (54 rows: 3 scenarios x 12
confidence steps, 6 steps at/above 0.35) were checked for
`requires_human_approval`:

- **Human escalation rate among confirmed rows: 70.37%** (38 / 54)

This reflects the actual configured thresholds
(`human_approval_confidence_ceiling = 0.85`,
`person_down_always_requires_approval = true`): every `person_down` confirmed
row requires approval regardless of confidence, and every non-person_down
confirmed row below confidence 0.85 also requires approval; only
non-person_down confirmed rows at confidence >= 0.85 route to an autonomous
`SEND_ALERT`.

---

## 4. Cloud (AWS)

| Metric | Value |
|---|---|
| AWS processing latency | `NOT MEASURED` |
| AWS throughput (events/sec) | `NOT MEASURED` |
| AWS cost per 1000 events | `NOT MEASURED` |
| AWS resource utilization | `NOT MEASURED` |

**Reason:** No live AWS deployment exists in this environment; the backend
runs in local mode only (`storage_backend=local`, `incident_backend=local`,
`notification_backend=local`, no AWS credentials configured). Per project
policy, these figures are not estimated or synthesized -- they are labeled
`NOT MEASURED` rather than filled with a guess.

---

## Limitations of this evaluation

- **n=4 scenario clips, not a dataset.** The entire "vision detection
  quality" section is derived from exactly 4 deterministic synthetic
  scenarios. There is no natural variation (lighting, camera angle, clutter,
  multiple simultaneous incidents, partial occlusion, etc.) and no repeated
  independent trials, because the generator is fully deterministic per
  scenario name. A 100% precision/recall/F1 here means "the logic passes on
  the only 4 scenes that exist," not "this system is 100% accurate."
- **Synthetic, not real-world footage.** `SyntheticFrameSource` draws simple
  geometric shapes with `cv2` primitives; it does not contain real cameras,
  real fires, real people, or real vehicles. See `evaluation/datasets/README.md`
  for exactly what is rendered and why. Performance on real camera footage is
  unknown and was out of scope for this pass (no such footage exists in this
  project).
- **Single-machine timing.** All latency/FPS numbers were measured once, on
  one development machine, on one occasion (see the timestamp above). They
  are not averaged across hardware, not repeated across multiple runs, and
  will vary (likely significantly on different CPUs, under load, or in a
  containerized/cloud environment). Treat FPS/latency numbers as "was capable
  of roughly this throughput on this box that day," not a guaranteed SLA.
- **No live AWS measurement.** The project has no AWS credentials or
  deployment configured; all AWS-related metrics are `NOT MEASURED` rather
  than estimated. Any real AWS latency/cost/throughput figures would require
  an actual deployed stack and real traffic, which do not exist here.
- **Agent decision-table coverage, not exhaustive fuzz testing.** The 108-row
  decision table exercises the documented severity/decision/action/approval
  branches at representative and boundary confidence values, but is not an
  exhaustive search over all possible evidence dict shapes (e.g. it does not
  vary `duration_seconds` independently of `state`, or test malformed/missing
  fields).
- **Confusion-matrix framing is a simplification.** "Reaches confirmed" is
  treated as a single binary outcome per scenario; it does not capture
  per-frame false-positive/false-negative rates within a scenario's own
  timeline (e.g. transient possible-state flicker before onset), though the
  underlying JSON's `states_seen` and time-to-possible/confirmed fields
  preserve that detail for anyone who wants to look closer.

## How to reproduce

```
python evaluation/run_evaluation.py
```

from the repository root (`C:\Users\Vignesh T\Downloads\RescueVision-AI`).
This regenerates a fresh timestamped JSON in `evaluation/results/` plus an
overwritten `evaluation/results/latest.json`, using only the backend's actual
`VisionPipeline`, `AgentPolicy`, and `SyntheticFrameSource` -- no mocking, no
recorded/replayed numbers.
