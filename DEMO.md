# Demo Script (5 minutes)

This is the exact sequence to run for a live or recorded judge demonstration.
Everything here is deterministic (synthetic scenes, see
[`sample_data/README.md`](sample_data/README.md)) so it reproduces
identically every time.

## Before you start

```bash
cd backend && python -m uvicorn app.main:app --port 8000 &
cd frontend && npm run dev &
```

Open the frontend URL (Vite prints it, typically `http://localhost:5173`)
and confirm the top nav shows a green "connected" indicator (calls
`GET /api/health`). Navigate to **/demo**.

## 0:00 – 0:20 — Introduce

> "This is RescueVision AI. It turns visual evidence into responsible
> action — not just a detection, but a full perception, reasoning, decision,
> action, and verification loop, with a human in control of high-risk
> decisions."

Show the **/dashboard** page briefly — point out the five-stage pipeline
visualization: VISION STATUS → INCIDENT → AGENT DECISION → ACTION → AWS
STATUS.

## 0:20 – 0:50 — Show architecture

Open [`docs/architecture.md`](docs/architecture.md) (rendered, e.g. on
GitHub or any Mermaid-capable viewer) and walk through diagram 1 (overall
system) and diagram 3 (agentic workflow / decision table) — 30 seconds,
don't linger.

> "Camera or video goes through OpenCV 5 — nine distinct classical
> vision operations, no black-box ML detector — producing structured visual
> evidence. That evidence drives an explicit agent state machine: observe,
> analyze, assess, plan, act, verify. The agent's decision changes based on
> what the vision layer actually reports — not a script."

## 0:50 – 3:30 — Live/deterministic demonstration

On the **/demo** page:

1. **Normal scene** (~15s) — click "Normal Scene". Narrate while it runs:
   > "No incident signal is ever introduced here — watch it stay in `none`
   > state and never create an incident."
   Point out the status panel staying flat.

2. **Fire / smoke** (~20s) — click "Fire Demo". Narrate the escalation as it
   appears live: `none` → `possible` (~9-10s in) → `confirmed` (~14s in).
   > "The flame and smoke color signal has now persisted long enough to
   > confirm. Watch the agent create an incident — but at this confidence
   > level, it still routes to a human for approval rather than firing an
   > alert autonomously."
   Click through to the created incident's detail page — show the
   evidence image, severity, and rationale text.

3. **Person down** (~15s) — click "Person Down Demo".
   > "This one **always** requires human approval, regardless of
   > confidence — this system makes no medical determination, so a human
   > operator is structurally required in the loop for this scenario."
   Show the incident detail page's approval UI (`Severity`, `Confidence`,
   `[ APPROVE ] [ REJECT ]`).

4. **Route obstruction** (~15s) — click "Obstruction Demo". Let it run to
   `confirmed`, briefly note the different severity/rationale text compared
   to the fire scenario (different detector, different signals).

5. **AWS incident** — on any of the confirmed incidents, click **APPROVE**.
   > "Approving is what actually triggers the notification tool call — in
   > this local-mode run that's a mocked notification service; configured
   > with real AWS credentials, this same code path calls SNS." (Point to
   > **/system** page showing `storage_backend` / `notification_backend` =
   > `local`, and reference `docs/aws-architecture.md` for what flips when
   > those are set to `aws`.)

6. **Human approval, in full** — on the person-down incident, demonstrate
   **REJECT** instead, showing that a rejected incident never notifies.

## 3:30 – 4:20 — Show actual metrics

Open [`evaluation/reports/evaluation_report.md`](evaluation/reports/evaluation_report.md)
(or **/analytics** for the live incident counts from this session) and cite,
verbatim, 2-3 real numbers — do not round up or editorialize:

> "On this development machine, the raw OpenCV vision stage processed
> frames at roughly 64 FPS on average across all four scenarios. The agent
> policy decision itself is sub-millisecond — about 5 microseconds on
> average — since it's a pure function with no I/O. And across a 108-row
> decision-table sweep over every scenario/state/confidence combination,
> 100% matched the documented policy rules, with about 70% of confirmed
> incidents requiring human escalation under the default thresholds."

Explicitly say: *"This evaluation runs on four synthetic, deterministic
clips — it's a correctness and performance check of the pipeline logic, not
a real-world accuracy benchmark; that limitation is written down in the
report itself."*

## 4:20 – 5:00 — Close

> "To recap: OpenCV 5 does substantive vision work — nine operations per
> frame, no wrapped ML model. A real AWS integration — S3, DynamoDB, SNS —
> with a matching local-mode implementation so it's fully testable and
> demoable without any AWS credentials. An agentic OBSERVE-to-VERIFY loop
> where the visual evidence genuinely changes the decision. And a human
> approval step that is structurally required for the higher-risk
> decisions, never bypassed. This is decision support for disaster
> response — not a replacement for trained emergency personnel."

## Notes for whoever records this

- Each demo scenario takes 15-20 seconds of real wall-clock time to reach
  its final state (synthetic playback runs at 15 fps against a ~150-300
  frame clip) — plan narration pacing around that, don't rush the escalation
  or you'll be talking over an unfinished state.
- If a scenario's `session_id` collides with a previous run, stop it first
  (the "Stop" button on `/demo`) or just let the page generate a fresh one
  automatically per click.
- The `/system` page is useful to point at quickly to show OpenCV version
  and backend mode (local vs AWS) without needing a terminal on screen.
