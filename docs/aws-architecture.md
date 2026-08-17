# AWS Architecture

## Status of this document

This describes the AWS integration **as implemented in code**
(`backend/app/aws/`), which is real, tested (via mocked boto3 clients — no
AWS credentials required for `pytest`), and switches on purely via
environment variables. It does **not** claim that a live AWS deployment has
been performed or verified in this environment — see
`deployment/DEPLOYMENT_STEPS.md` for what a real deployment would require
and what has/has not been executed against a real AWS account.

## Services used, and why

| Service | Used for | Why this one |
|---|---|---|
| **Amazon S3** | Evidence image storage (`app/aws/storage.py::S3Storage`) | Durable, cheap object storage for the JPEG evidence frames the agent attaches to each incident; a natural fit for write-once, infrequently-read images. |
| **Amazon DynamoDB** | Incident state (`app/incidents/repository.py::DynamoDBIncidentRepository`) | Incidents are simple, independent key-value records (partition key `incident_id`) with occasional updates (status/approval changes) — DynamoDB's on-demand model avoids provisioning for a workload with a highly variable, bursty incident rate. |
| **Amazon SNS** | Operator notifications (`app/aws/notifications.py::SNSNotificationService`) | Pub/sub fan-out to however many responders/channels (email, SMS, Lambda) need to be notified, decoupled from the app itself. |
| **EC2 or ECS (Fargate)** | Application hosting for the FastAPI backend (see `deployment/DEPLOYMENT_STEPS.md`) | Either a single EC2 instance running the provided `backend/Dockerfile`, or an ECS Fargate service, both documented; no Lambda is used for the always-on monitoring loop since it is a long-lived background thread per camera, not a short request/response function. |
| **CloudWatch Logs** | Centralized log aggregation for the structured JSON logs already emitted by `backend/app/logging/structured_logger.py` | The app already logs structured JSON to stdout; CloudWatch Logs is the natural sink when running on ECS/EC2, requiring no application code changes. |

**Lambda is intentionally not used.** The monitoring loop is a persistent,
stateful per-camera process (it holds an OpenCV background-subtractor model
and an open incident map across frames) — this does not fit Lambda's
short-lived, stateless execution model well, and adding it purely for
"cloud-native" appearance would violate the project's stated principle of
only using services that are actually useful.

## Data flow

```
Camera / video file
        |
        v
OpenCV 5 Vision Pipeline  (backend/app/vision/)
        |
        v
Visual Evidence (IncidentCandidate)
        |
        v
Vision Agent (OBSERVE..VERIFY)  (backend/app/agent/)
        |
    Decision (AgentPolicy)
        |
   +----+-----------------+
   |                       |
   v                       v
create_incident()     store_evidence()
   |                       |
   v                       v
DynamoDB / SQLite      S3 / local filesystem
   |
   v
send_notification() -- (only if not gated on human approval)
   |
   v
SNS / in-memory mock
```

## Local-mode / AWS-mode symmetry

Every AWS integration point has a matching local implementation, selected
purely by `Settings.storage_backend` / `incident_backend` /
`notification_backend` (`backend/app/configuration/config.py`), built by
`backend/app/aws/factory.py`:

| Interface | Local implementation | AWS implementation |
|---|---|---|
| `StorageService` | `LocalStorage` (filesystem under `LOCAL_STORAGE_DIR`) | `S3Storage` |
| `IncidentRepository` | `LocalIncidentRepository` (SQLite, WAL mode) | `DynamoDBIncidentRepository` |
| `NotificationService` | `MockNotificationService` (in-memory list) | `SNSNotificationService` |

This is not a fallback bolted on for testing — it is the actual factory
(`build_storage`, `build_incident_repository`, `build_notification_service`)
used by the running application in both modes; there is no separate "demo"
code path. Setting `STORAGE_BACKEND=aws` together with a real `S3_BUCKET`
and valid AWS credentials in the environment (or an attached IAM role) is
the entire switch required to start writing evidence to S3 instead of disk
— see `backend/app/aws/factory.py::build_storage`, which falls back to
`LocalStorage` if `S3_BUCKET` is empty even when `STORAGE_BACKEND=aws`, so a
misconfiguration cannot silently attempt to write to a bucket named `""`.

## Security

- No AWS credentials are ever hard-coded. `boto3` clients are constructed
  with only a region name (`app/aws/storage.py`, `app/aws/notifications.py`,
  `app/incidents/repository.py`); credential resolution is left to boto3's
  standard chain (environment variables, an attached IAM instance
  role/task role, or a shared credentials file) — this is what makes
  "use IAM roles in production" possible without any code change.
- `.env` (real, populated) is git-ignored; only `.env.example` (documented
  placeholders, no secrets) is committed.
- No AWS credential or secret is ever sent to, or referenced by, the
  frontend (`frontend/`) — the browser only talks to this backend's own
  API, never to AWS directly.
- IAM policy scoping (least-privilege, limited to the one S3 bucket, one
  DynamoDB table, and one SNS topic this app uses) is documented with a
  concrete example policy in `deployment/DEPLOYMENT_STEPS.md`.
