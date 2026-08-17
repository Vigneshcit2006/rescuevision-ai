# Deployment

The full AWS deployment runbook lives in
[`deployment/DEPLOYMENT_STEPS.md`](deployment/DEPLOYMENT_STEPS.md) — it
covers AWS account requirements, IAM policy (least-privilege JSON in
[`deployment/iam-policy.json`](deployment/iam-policy.json)), S3/DynamoDB/SNS
setup, compute (an example ECS Fargate task definition in
[`deployment/ecs-task-definition.json`](deployment/ecs-task-definition.json),
plus an EC2 alternative), required production environment variables, health
checks, log aggregation, and rollback.

**This runbook has not been executed against a real AWS account in this
project's development environment** — there are no AWS credentials
available here, and no live deployment exists to point to. Every step in
`deployment/DEPLOYMENT_STEPS.md` is written and internally consistent with
the actual code (`backend/app/aws/factory.py` and friends), but is labeled
`NOT VERIFIED` rather than claimed as a completed deployment. Anyone
following it against a real AWS account should validate each step as they
go.

For local development and demoing without any AWS account, see
[`QUICKSTART.md`](QUICKSTART.md) and `docker-compose.yml` — both run
entirely in local mode (SQLite, filesystem evidence, mock notifications).

## CI/CD

- [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — runs on every
  push/PR: backend syntax check + full pytest suite (no AWS credentials
  required), frontend typecheck + build.
- [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) — separate
  from CI; only runs on manual dispatch or a tag, and every AWS-touching
  step is gated on `secrets.AWS_ACCESS_KEY_ID` being present so it never
  silently attempts a real deployment from a fork or an unconfigured repo.
