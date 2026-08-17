# RescueVision AI

**"See the emergency. Reason about it. Act responsibly."**

RescueVision AI is a disaster-response monitoring prototype built for the
**OpenCV AI Competition 2026, powered by AWS**. It uses **OpenCV 5** for
substantive per-frame vision analysis (color/motion/persistent-change
detection, not a wrapped ML model), a **temporal analyzer** to distinguish
noise from a real, sustained event, and an **agentic decision loop**
(OBSERVE → ANALYZE → ASSESS → PLAN → ACT → VERIFY) that decides what to do
next — including, for higher-risk decisions, **routing to a human operator
for approval before any alert is sent.**

```
VIDEO / CAMERA
      |
      v
OPENCV 5 VISUAL PROCESSING
      |
      v
VISUAL EVIDENCE
      |
      v
AGENTIC DECISION ENGINE
      |
      v
SEVERITY + CONFIDENCE + CONTEXT
      |
      v
RESPONSE PLAN
      |
      v
CONTROLLED TOOL / AWS ACTION
      |
      v
VERIFY RESULT  ->  UPDATE INCIDENT  ->  CONTINUE MONITORING
```

## What it actually does

Three scenarios, each backed by real (if classical, not ML) computer vision
and a distinct, tested agent policy:

1. **Fire / smoke** — HSV color-region ratios + background-subtraction
   motion, escalated through none → possible → confirmed by sustained
   persistence.
2. **Person down / fall** — posture (bounding-box aspect ratio) held from
   the last active-motion frame, combined with a persistent-change presence
   check. **Always routes through human approval**, regardless of
   confidence — this project makes no medical determination.
3. **Emergency route obstruction** — persistent-change area ratio within a
   configured region, distinguishing a parked/blocking object from one that
   merely passed through.

Every decision the agent makes is driven by real OpenCV-derived confidence
and duration values, through a policy layer that is unit-tested for every
branch (`backend/tests/test_agent_policy.py`) — not hard-coded per scenario.

## Repository layout

```
backend/     FastAPI + OpenCV 5 + agent + AWS abstractions (Python 3.11)
frontend/    React + TypeScript + Vite operational dashboard
evaluation/  Reproducible measurement framework (real numbers, no fabrication)
sample_data/ Documents the synthetic (non-copyrighted) demo scenarios
deployment/  AWS deployment runbook, IAM policy, ECS task definition
docs/        Architecture diagrams, OpenCV/agent/AWS deep-dives, responsible use
scripts/     One-line dev helpers (run backend, run frontend, run tests;
             .bat versions on Windows are double-click launchers)
```

## Quickstart

See [`QUICKSTART.md`](QUICKSTART.md) for the full walkthrough. Short version:

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Then open the frontend (Vite prints the local URL, typically
`http://localhost:5173`) and visit **/demo** to run any of the four
deterministic scenarios, or hit the API directly:

```bash
curl -X POST http://localhost:8000/api/demo/start \
  -H "Content-Type: application/json" \
  -d '{"scenario": "fire_smoke"}'
```

Or with Docker: `docker compose up --build` (see `docker-compose.yml`).

## Verified, not claimed

- **OpenCV 5 is genuinely installed**: `opencv-python==5.0.0.93`, enforced
  by `backend/tests/test_vision_pipeline.py::test_opencv_version_is_5`.
  See [`docs/opencv5_implementation.md`](docs/opencv5_implementation.md) for
  every call site.
- **31/31 backend tests pass** locally with zero AWS credentials
  (`cd backend && python -m pytest tests/`).
- **The evaluation numbers in [`evaluation/reports/evaluation_report.md`](evaluation/reports/evaluation_report.md)
  are real measurements from an actual run**, not estimates — including an
  explicit, honest limitations section (n=4 synthetic scenarios, single
  development machine, no live AWS).
- **AWS integration (S3, DynamoDB, SNS) is implemented and unit-tested** via
  mocked boto3 calls, with a matching local-mode implementation for every
  AWS service so the whole system runs with zero AWS credentials. See
  [`docs/aws-architecture.md`](docs/aws-architecture.md). No live AWS
  deployment has been performed in this environment — see
  [`deployment/DEPLOYMENT_STEPS.md`](deployment/DEPLOYMENT_STEPS.md), which
  is explicitly labeled as an unverified runbook, not a deployment record.

## Documentation index

| Doc | What it covers |
|---|---|
| [`QUICKSTART.md`](QUICKSTART.md) | Local setup, both backend and frontend |
| [`DEMO.md`](DEMO.md) | Judge-facing 5-minute demo script |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | Pointer to the full AWS deployment runbook |
| [`BENCHMARK.md`](BENCHMARK.md) | Pointer to real, measured performance numbers |
| [`docs/architecture.md`](docs/architecture.md) | 5 Mermaid diagrams of the actual system |
| [`docs/opencv5_implementation.md`](docs/opencv5_implementation.md) | Every OpenCV 5 call site, with rationale |
| [`docs/agent-workflow.md`](docs/agent-workflow.md) | The OBSERVE→VERIFY state machine and policy table |
| [`docs/aws-architecture.md`](docs/aws-architecture.md) | AWS services used, local/AWS symmetry, security |
| [`docs/evaluation.md`](docs/evaluation.md) | Evaluation methodology |
| [`docs/failure-cases.md`](docs/failure-cases.md) | Tested failure modes and known, disclosed gaps |
| [`docs/responsible-use.md`](docs/responsible-use.md) | Scope limits, human oversight, privacy |
| [`docs/judge-scorecard.md`](docs/judge-scorecard.md) | Judging-criteria → evidence mapping |
| [`docs/technical-report.md`](docs/technical-report.md) | Full competition technical report |

## What this is not

RescueVision AI is a hackathon prototype. It performs no facial recognition,
no identity inference, and no medical diagnosis; it does not autonomously
contact emergency dispatch; and it has not been validated against real-world
footage or deployed to a live AWS account. See
[`docs/responsible-use.md`](docs/responsible-use.md) and
[`docs/failure-cases.md`](docs/failure-cases.md) for the full, honest scope.
