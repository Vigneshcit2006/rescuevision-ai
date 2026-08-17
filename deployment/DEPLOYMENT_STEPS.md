# RescueVision AI — Deployment Steps

> **STATUS: NOT VERIFIED.** Everything in this document is deployment
> *documentation*, written and reviewed by hand. None of these steps have
> been executed against a real AWS account in this environment (no AWS
> credentials are available in this sandbox). Treat this as a runbook for
> whoever deploys the app with real AWS access — not as evidence of a live
> deployment. Before trusting it in front of judges, actually run through
> it once against a scratch AWS account.

## 1. AWS account requirements

- An AWS account with permission to create IAM roles/policies, S3 buckets,
  a DynamoDB table, an SNS topic, and either an EC2 instance or an ECS
  Fargate service + ECR repository.
- The AWS CLI (`aws --version`) configured locally with an admin or
  power-user identity for the *initial* setup only. Day-to-day, the running
  application uses a scoped-down role (below), not your personal credentials.
- Decide on a region up front (examples below use `us-east-1`); every ARN
  in this doc is written with a `<AWS_REGION>` and `<ACCOUNT_ID>` placeholder
  — substitute your real values.

## 2. IAM policy (least privilege)

The app only ever needs to: read/write objects in one S3 bucket, read/write
items in one DynamoDB table, and publish to one SNS topic. The full JSON is
checked in at [`deployment/iam-policy.json`](./iam-policy.json):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RescueVisionS3EvidenceBucket",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::rescuevision-evidence-<ACCOUNT_ID>",
        "arn:aws:s3:::rescuevision-evidence-<ACCOUNT_ID>/*"
      ]
    },
    {
      "Sid": "RescueVisionDynamoDBIncidentsTable",
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:Scan"],
      "Resource": [
        "arn:aws:dynamodb:<AWS_REGION>:<ACCOUNT_ID>:table/rescuevision-incidents",
        "arn:aws:dynamodb:<AWS_REGION>:<ACCOUNT_ID>:table/rescuevision-incidents/index/*"
      ]
    },
    {
      "Sid": "RescueVisionSNSAlertsTopic",
      "Effect": "Allow",
      "Action": ["sns:Publish"],
      "Resource": "arn:aws:sns:<AWS_REGION>:<ACCOUNT_ID>:rescuevision-alerts"
    },
    {
      "Sid": "RescueVisionCloudWatchLogs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:<AWS_REGION>:<ACCOUNT_ID>:log-group:/rescuevision/*"
    }
  ]
}
```

Create it and an IAM role that trusts either `ec2.amazonaws.com` (EC2 path)
or `ecs-tasks.amazonaws.com` (ECS path):

```bash
aws iam create-policy \
  --policy-name RescueVisionAppPolicy \
  --policy-document file://deployment/iam-policy.json

aws iam create-role \
  --role-name rescuevision-task-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

aws iam attach-role-policy \
  --role-name rescuevision-task-role \
  --policy-arn arn:aws:iam::<ACCOUNT_ID>:policy/RescueVisionAppPolicy
```

Never put a real access key/secret into the running app when it's on
AWS compute — the instance profile / task role above supplies credentials
automatically via boto3's default credential chain. Static keys in
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` are for local-machine testing
against a real account only, and must never be committed.

## 3. S3 bucket setup

```bash
aws s3api create-bucket \
  --bucket rescuevision-evidence-<ACCOUNT_ID> \
  --region <AWS_REGION>

# Block all public access - evidence images/video are never served
# directly from S3 in this app; the API mounts /evidence itself.
aws s3api put-public-access-block \
  --bucket rescuevision-evidence-<ACCOUNT_ID> \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Optional but recommended: keep prior evidence versions.
aws s3api put-bucket-versioning \
  --bucket rescuevision-evidence-<ACCOUNT_ID> \
  --versioning-configuration Status=Enabled
```

## 4. DynamoDB table setup

Partition key `incident_id` (string), on-demand billing so there's no
capacity planning for a hackathon-scale workload:

```bash
aws dynamodb create-table \
  --table-name rescuevision-incidents \
  --attribute-definitions AttributeName=incident_id,AttributeType=S \
  --key-schema AttributeName=incident_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region <AWS_REGION>
```

## 5. SNS topic + subscription

```bash
aws sns create-topic --name rescuevision-alerts --region <AWS_REGION>
# -> returns TopicArn, e.g. arn:aws:sns:<AWS_REGION>:<ACCOUNT_ID>:rescuevision-alerts

aws sns subscribe \
  --topic-arn arn:aws:sns:<AWS_REGION>:<ACCOUNT_ID>:rescuevision-alerts \
  --protocol email \
  --notification-endpoint you@example.com
# The subscriber must confirm via the email AWS sends before notifications flow.
```

## 6. Compute: ECS Fargate (primary path)

This is the primary, concrete deploy path documented here. (An EC2
alternative is sketched in section 6b for a lower-ceremony demo.)

1. **Create an ECR repository and push the backend image:**

   ```bash
   aws ecr create-repository --repository-name rescuevision-backend --region <AWS_REGION>

   aws ecr get-login-password --region <AWS_REGION> \
     | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com

   docker build -t rescuevision-backend ./backend
   docker tag rescuevision-backend:latest <ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/rescuevision-backend:latest
   docker push <ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/rescuevision-backend:latest
   ```

2. **Register the task definition** — see
   [`deployment/ecs-task-definition.json`](./ecs-task-definition.json) for
   the concrete example (fill in `<ACCOUNT_ID>` / `<AWS_REGION>`, env vars
   listed in section 7):

   ```bash
   aws ecs register-task-definition --cli-input-json file://deployment/ecs-task-definition.json
   ```

3. **Create/update the ECS cluster and service** (Fargate, behind an ALB if
   you want a stable public URL; a public IP on the ENI is enough for a
   demo):

   ```bash
   aws ecs create-cluster --cluster-name rescuevision

   aws ecs create-service \
     --cluster rescuevision \
     --service-name rescuevision-backend \
     --task-definition rescuevision-backend \
     --desired-count 1 \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[<SUBNET_ID>],securityGroups=[<SG_ID>],assignPublicIp=ENABLED}"
   ```

4. **Frontend**: build `frontend/Dockerfile`, push to its own ECR repo (or a
   static host like S3+CloudFront), and set its `VITE_API_BASE_URL` build
   arg to the backend's public URL/ALB DNS name.

### 6b. Compute: EC2 alternative (lower ceremony)

For a quick single-instance demo instead of ECS:

```bash
# On an EC2 instance with Docker installed and the rescuevision-task-role
# instance profile attached:
docker pull <ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/rescuevision-backend:latest

docker run -d --name rescuevision-backend \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e STORAGE_BACKEND=aws \
  -e INCIDENT_BACKEND=aws \
  -e NOTIFICATION_BACKEND=aws \
  -e AWS_REGION=<AWS_REGION> \
  -e S3_BUCKET=rescuevision-evidence-<ACCOUNT_ID> \
  -e DYNAMODB_TABLE=rescuevision-incidents \
  -e SNS_TOPIC_ARN=arn:aws:sns:<AWS_REGION>:<ACCOUNT_ID>:rescuevision-alerts \
  --restart unless-stopped \
  <ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/rescuevision-backend:latest
```

No static AWS keys needed here either — the instance's IAM instance profile
(attached to the EC2 instance, trusting `ec2.amazonaws.com`, with the same
`RescueVisionAppPolicy` attached) supplies credentials via the instance
metadata service.

## 7. Required environment variables (production)

| Variable                | Production value                                              |
|--------------------------|----------------------------------------------------------------|
| `ENVIRONMENT`            | `production`                                                   |
| `STORAGE_BACKEND`        | `aws`                                                           |
| `INCIDENT_BACKEND`       | `aws`                                                           |
| `NOTIFICATION_BACKEND`   | `aws`                                                           |
| `AWS_REGION`             | e.g. `us-east-1`                                                |
| `S3_BUCKET`              | `rescuevision-evidence-<ACCOUNT_ID>`                            |
| `DYNAMODB_TABLE`         | `rescuevision-incidents`                                        |
| `SNS_TOPIC_ARN`          | `arn:aws:sns:<AWS_REGION>:<ACCOUNT_ID>:rescuevision-alerts`      |
| `LOG_LEVEL`              | `INFO` (or `WARNING` to reduce noise)                           |

`LOCAL_STORAGE_DIR` / `LOCAL_DB_PATH` are ignored once the corresponding
`*_BACKEND` is `aws`, so they don't need to be set in production.

## 8. Health check

`GET /api/health` returns `{"status": "ok", "opencv_version": "...",
"environment": "..."}`. Point an ALB target group health check, an ECS
container health check (already set in the task definition above), or a
simple `curl`/uptime monitor at this path.

```bash
curl -f http://<HOST>:8000/api/health
```

## 9. Logs

- **ECS path**: logs go to CloudWatch Logs, group `/rescuevision/backend`
  (configured in the task definition's `logConfiguration`). View with:

  ```bash
  aws logs tail /rescuevision/backend --follow
  ```

- **EC2 path**: if run via `docker run` as above, use:

  ```bash
  docker logs -f rescuevision-backend
  ```

  If instead run as a systemd-managed `docker run`/`docker compose`
  service, use `journalctl -u rescuevision-backend -f`.

## 10. Rollback procedure

- **ECS**: task definitions are versioned. To roll back:

  ```bash
  aws ecs update-service \
    --cluster rescuevision \
    --service rescuevision-backend \
    --task-definition rescuevision-backend:<PREVIOUS_REVISION_NUMBER>
  ```

  Find `<PREVIOUS_REVISION_NUMBER>` with
  `aws ecs list-task-definitions --family-prefix rescuevision-backend`.

- **EC2 / docker run**: keep the previous image tag around and re-run:

  ```bash
  docker stop rescuevision-backend && docker rm rescuevision-backend
  docker run -d --name rescuevision-backend -p 8000:8000 \
    <same env vars as before> \
    <ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/rescuevision-backend:<PREVIOUS_TAG>
  ```

- In both cases, prefer tagging images with the git commit SHA
  (`docker tag ... :$(git rev-parse HEAD)`) at build time so "previous tag"
  always has an unambiguous, reproducible meaning.

## Reminder

Nothing above has been run against a real AWS account from this repo/session.
Treat every command as untested until someone with real AWS access walks
through it end to end and updates this note.
