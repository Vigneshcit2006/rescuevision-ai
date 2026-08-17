# Quickstart

Everything below runs in **local mode** (SQLite + filesystem evidence + an
in-memory mock notification service) with **zero AWS credentials required**.
AWS mode is opt-in via environment variables — see
[`docs/aws-architecture.md`](docs/aws-architecture.md).

## Prerequisites

- Python 3.11+ (developed/tested on 3.11.9)
- Node.js 18+ (developed/tested on Node 24.18, npm 11.16)
- (Optional) Docker, if you'd rather use `docker compose up --build`

## Windows: double-click launchers

If you're on Windows and don't want to use a terminal, `scripts/` has
double-clickable `.bat` files that install dependencies and start each
process in its own cmd window (logs/errors stay visible in that window):

- **`scripts/start_all.bat`** — starts both backend and frontend at once,
  each in its own window.
- `scripts/run_backend.bat` — backend only (`http://localhost:8000`).
- `scripts/run_frontend.bat` — frontend only (`http://localhost:5173`).
- `scripts/run_tests.bat` — runs the backend pytest suite.

Close a window (or Ctrl+C inside it) to stop that process. These just wrap
the `.ps1` scripts below via PowerShell, so the terminal steps in this file
are equivalent — use whichever you prefer.

## 1. Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify it's up:

```bash
curl http://localhost:8000/api/health
# {"status":"ok","opencv_version":"5.0.0","environment":"local"}
```

If `opencv_version` doesn't start with `5.`, something installed the wrong
OpenCV wheel — `pip show opencv-python` should report `5.0.0.93` (pinned in
`backend/requirements.txt`).

Interactive API docs are auto-served at `http://localhost:8000/docs`.

## 2. Frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite will print a local URL (typically `http://localhost:5173`). Open it —
you should see the RescueVision AI dashboard with a green "connected"
indicator if the backend from step 1 is reachable at
`http://localhost:8000` (configurable via `frontend/.env` /
`VITE_API_BASE_URL`, copy from `frontend/.env.example`).

## 3. Run the tests

```bash
cd backend
python -m pytest tests/ -v
```

This runs 31 tests (vision pipeline, temporal analyzer, agent policy,
incident lifecycle, API integration, and failure-mode tests) — all local,
no AWS credentials, no network access. Expect it to take 60-90 seconds:
several tests genuinely run demo scenarios through their full 15-20 second
escalation window rather than mocking time.

## 4. Try the demo

Either through the dashboard's **/demo** page (four buttons: Fire, Person
Down, Obstruction, Normal Scene), or directly via curl:

```bash
curl -X POST http://localhost:8000/api/demo/start \
  -H "Content-Type: application/json" \
  -d '{"scenario": "fire_smoke", "session_id": "quickstart-1"}'

# Poll status (scenario takes ~15-20s to fully escalate at synthetic playback speed)
curl http://localhost:8000/api/demo/status/quickstart-1

# Once an incident_id appears in last_decision, fetch it:
curl http://localhost:8000/api/incidents/RV-00001

# Approve it (this is what actually sends the notification):
curl -X POST http://localhost:8000/api/incidents/RV-00001/approve \
  -H "Content-Type: application/json" \
  -d '{"approver": "quickstart_operator"}'
```

Valid `scenario` values: `fire_smoke`, `person_down`, `route_obstruction`,
`normal`. See [`sample_data/README.md`](sample_data/README.md) for what each
one renders and why.

## 5. Run the evaluation

```bash
python evaluation/run_evaluation.py
```

Produces a fresh timestamped JSON in `evaluation/results/` and prints a
summary. Takes ~2 minutes (it genuinely runs multiple 260-frame scenario
passes and timing loops, not a mocked/instant pass). See
[`evaluation/reports/evaluation_report.md`](evaluation/reports/evaluation_report.md)
for the last committed run's results and their limitations.

## 6. Docker (alternative to steps 1-2)

```bash
docker compose up --build
```

Backend on `http://localhost:8000`, frontend on `http://localhost:5173`.
See `docker-compose.yml` for the environment variables it wires through.

## Configuring AWS mode (optional)

Copy `backend/.env.example` to `backend/.env` and set
`STORAGE_BACKEND=aws`, `INCIDENT_BACKEND=aws`, `NOTIFICATION_BACKEND=aws`,
plus `AWS_REGION`, `S3_BUCKET`, `DYNAMODB_TABLE`, `SNS_TOPIC_ARN`, and valid
AWS credentials (environment variables or an attached IAM role — never
hard-code them). See [`deployment/DEPLOYMENT_STEPS.md`](deployment/DEPLOYMENT_STEPS.md)
for the full AWS-side setup this requires (S3 bucket, DynamoDB table, SNS
topic, IAM policy). This has not been deployed/verified against a real AWS
account in this project's development environment — treat it as a runbook,
not a deployment record.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'cv2'`** — `pip install -r backend/requirements.txt` didn't complete; re-run it and check for errors (opencv-python==5.0.0.93 requires a 64-bit Python 3.9-3.13 environment).
- **Frontend shows "disconnected"** — the backend isn't running or is on a different port than `VITE_API_BASE_URL` points to; check `frontend/.env`.
- **A demo scenario never reaches "confirmed"** — this can happen if you stop and restart a session with the same `session_id` mid-escalation (each session's temporal analyzer/reference frame resets). Start a fresh `session_id`, or just omit it and let the API generate one.
