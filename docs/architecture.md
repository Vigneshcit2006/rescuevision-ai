# System Architecture

Diagrams below reflect the actual implementation in this repository
(`backend/app/`), not an aspirational design. File paths are given next to
each component.

## 1. Overall system

```mermaid
flowchart TD
    CAM["Camera / video file / synthetic demo source"] --> VS["VideoSource / SyntheticFrameSource<br/>backend/app/vision/video_source.py"]
    VS --> PIPE["VisionPipeline<br/>backend/app/vision/pipeline.py"]
    PIPE --> CAND["IncidentCandidate<br/>(structured visual evidence)"]
    CAND --> AGENT["VisionAgent state machine<br/>backend/app/agent/agent.py"]
    AGENT -->|CREATE_INCIDENT| STORE["store_evidence()"]
    AGENT -->|CREATE_INCIDENT| REPO["create_incident() / update_incident()"]
    AGENT -->|SEND_ALERT| NOTIFY["send_notification()"]
    AGENT -->|needs review| APPROVAL["request_human_approval()"]
    STORE --> S3["S3Storage / LocalStorage"]
    REPO --> DB["DynamoDBIncidentRepository / LocalIncidentRepository"]
    NOTIFY --> SNS["SNSNotificationService / MockNotificationService"]
    APPROVAL --> API["FastAPI /api/incidents/{id}/approve|reject<br/>backend/app/api/routes.py"]
    API --> HUMAN["Human operator (dashboard)"]
    HUMAN --> API
    DB --> DASH["React dashboard<br/>frontend/"]
    S3 --> DASH
```

## 2. OpenCV 5 vision pipeline

```mermaid
flowchart LR
    F["Raw frame (BGR)"] --> RESIZE["cv2.resize<br/>+ cv2.GaussianBlur"]
    RESIZE --> ROI["ROI crop<br/>(configured region)"]
    ROI --> HSV["cv2.cvtColor<br/>BGR2HSV / BGR2GRAY"]
    HSV --> COLOR["cv2.inRange<br/>fire / smoke color ratio"]
    HSV --> DIFF["cv2.absdiff vs. fixed reference<br/>persistent-change mask"]
    HSV --> MOG2["cv2.createBackgroundSubtractorMOG2<br/>adaptive motion mask"]
    DIFF --> MORPH1["cv2.morphologyEx (OPEN)"]
    MOG2 --> MORPH2["cv2.morphologyEx (OPEN)"]
    MORPH1 --> CONT1["cv2.findContours / contourArea<br/>persistent-region measurement"]
    MORPH2 --> CONT2["cv2.findContours / contourArea<br/>motion-region measurement"]
    COLOR --> DETECT["Scenario detector<br/>(fire_smoke | person_down | route_obstruction)"]
    CONT1 --> DETECT
    CONT2 --> DETECT
    DETECT --> TEMPORAL["TemporalAnalyzer<br/>none -> possible -> confirmed"]
    TEMPORAL --> EVID["EvidenceExtractor<br/>+ cv2.rectangle/putText/imencode"]
    EVID --> CAND2["IncidentCandidate"]
```

See `docs/opencv5_implementation.md` for the exact call sites and rationale.

## 3. Agentic workflow

```mermaid
stateDiagram-v2
    [*] --> OBSERVE
    OBSERVE --> ANALYZE: IncidentCandidate evidence
    ANALYZE --> ASSESS: parsed state/confidence/duration
    ASSESS --> PLAN: severity (AgentPolicy)
    PLAN --> ACT: decision + action
    ACT --> VERIFY: tool call executed
    VERIFY --> OBSERVE: action_result recorded
```

Decision table (`backend/app/agent/policy.py::AgentPolicy.evaluate`):

```mermaid
flowchart TD
    E["Evidence: state, confidence, duration, scenario"] --> Q1{state == none OR<br/>confidence < min_frame_confidence?}
    Q1 -->|yes| R1["CONTINUE_OBSERVATION / NONE"]
    Q1 -->|no| Q2{state == possible?}
    Q2 -->|yes| R2["INCREASE_MONITORING / STORE_EVIDENCE_ONLY"]
    Q2 -->|no, confirmed| Q3{scenario == person_down<br/>OR confidence < approval_ceiling?}
    Q3 -->|yes| R3["CREATE_INCIDENT / REQUEST_HUMAN_APPROVAL"]
    Q3 -->|no| R4["CREATE_INCIDENT / SEND_ALERT (autonomous)"]
```

## 4. AWS architecture

See `docs/aws-architecture.md` for the full diagram and service rationale.

## 5. Human-in-the-loop workflow

```mermaid
sequenceDiagram
    participant V as Vision Pipeline
    participant A as Vision Agent
    participant DB as Incident Repository
    participant H as Human Operator (dashboard)
    participant N as Notification Service

    V->>A: IncidentCandidate (confirmed, e.g. person_down)
    A->>DB: create_incident(human_approval_status=PENDING)
    Note over A,N: send_notification() is NOT called yet
    H->>DB: GET /api/incidents/{id}
    H->>A: POST /api/incidents/{id}/approve {approver, notes}
    DB->>DB: human_approval_status=APPROVED, action_status=ACTION_TAKEN
    A->>N: notify(incident)
    Note over H,DB: POST .../reject instead sets REJECTED / CLOSED,<br/>no notification is ever sent
```
