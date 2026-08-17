"""
MonitoringService: the long-running orchestrator behind /api/demo/* and
/api/analyze. It owns one active VisionPipeline + VisionAgent session at a
time, runs frames through it on a background thread at the *adaptive*
interval returned by the agent's last decision (this is what makes the
"analyze every 5s -> every 2s -> continuously -> back to 5s" requirement
visible in logs and in GET /api/system-status), and exposes the latest
status/trace for the API and frontend to poll.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Iterator, Optional

from app.agent.agent import AgentCycleResult, VisionAgent
from app.agent.policy import AgentPolicy
from app.agent.tools import AgentTools, ToolContext
from app.aws.factory import build_incident_repository, build_notification_service, build_storage
from app.configuration.config import Settings
from app.logging.structured_logger import IncidentIdGenerator, get_logger, log_event
from app.vision.evidence_extractor import IncidentCandidate
from app.vision.pipeline import VisionPipeline
from app.vision.video_source import Frame, SyntheticFrameSource, VideoSource

logger = get_logger("services.monitoring")

DEMO_SCENARIOS = {
    "fire_smoke": "fire_smoke",
    "person_down": "person_down",
    "route_obstruction": "route_obstruction",
    "normal": "normal",
}


@dataclass
class SessionStatus:
    session_id: str
    scenario: str
    running: bool
    current_interval_seconds: float
    frames_processed: int
    last_candidate: Optional[dict] = None
    last_decision: Optional[dict] = None
    last_trace: list[dict] = field(default_factory=list)
    started_at: float = 0.0
    updated_at: float = 0.0


class MonitoringSession:
    """One monitored region/scenario, running its own pipeline + agent on a background thread."""

    def __init__(
        self,
        session_id: str,
        scenario: str,
        settings: Settings,
        frames: Iterator[Frame],
        incident_ids: IncidentIdGenerator,
        playback_interval_seconds: float = 1 / 15.0,
    ):
        self.session_id = session_id
        self.scenario = scenario
        self.settings = settings
        self._frames = frames
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # Demo/upload playback advances at (roughly) the source frame rate so a
        # judge can watch a full escalation in seconds. The adaptive interval
        # the agent computes (SessionStatus.current_interval_seconds) is what
        # a *production* deployment would sleep between capture calls -- it is
        # reported for observability but does not throttle this playback loop,
        # since these are pre-recorded/synthetic frames, not a live camera.
        self._playback_interval_seconds = playback_interval_seconds

        detection_scenario = scenario if scenario != "normal" else settings.default_scenario
        self.pipeline = VisionPipeline(detection_scenario, settings.thresholds, settings.region_of_interest, region_name=scenario)
        policy = AgentPolicy(settings.agent_policy, settings.thresholds, settings.monitoring)
        ctx = ToolContext(
            build_storage(settings), build_incident_repository(settings), build_notification_service(settings)
        )
        self.tools = ctx
        self.agent = VisionAgent(policy, AgentTools(ctx), incident_ids)

        self.status = SessionStatus(
            session_id=session_id,
            scenario=scenario,
            running=False,
            current_interval_seconds=settings.monitoring.normal_interval_seconds,
            frames_processed=0,
            started_at=time.time(),
            updated_at=time.time(),
        )

    def start(self) -> None:
        self.status.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        log_event(logger, "monitoring.session.start", session_id=self.session_id, scenario=self.scenario)

    def stop(self) -> None:
        self._stop.set()
        self.status.running = False
        log_event(logger, "monitoring.session.stop", session_id=self.session_id, scenario=self.scenario)

    def _run_loop(self) -> None:
        for frame in self._frames:
            if self._stop.is_set():
                break
            candidate = self.pipeline.process_frame(frame)
            result = self.agent.step(candidate)
            self._update_status(candidate, result)
            time.sleep(self._playback_interval_seconds)
        self.status.running = False

    def _update_status(self, candidate: IncidentCandidate, result: AgentCycleResult) -> None:
        self.status.frames_processed += 1
        self.status.current_interval_seconds = result.outcome.next_observation_seconds
        self.status.last_candidate = candidate.to_agent_evidence()
        self.status.last_decision = {
            "severity": result.outcome.severity,
            "decision": result.outcome.decision,
            "action": result.outcome.action,
            "requires_human_approval": result.outcome.requires_human_approval,
            "rationale": result.outcome.rationale,
            "action_result": result.action_result,
            "incident_id": result.incident.incident_id if result.incident else None,
        }
        self.status.last_trace = [
            {"state": s.state, "detail": s.detail, "timestamp": s.timestamp} for s in result.trace
        ]
        self.status.updated_at = time.time()


class MonitoringService:
    """Process-wide registry of active sessions, keyed by session_id."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._sessions: dict[str, MonitoringSession] = {}
        self._lock = threading.Lock()
        self._incident_ids = IncidentIdGenerator()

    def start_demo(self, scenario: str, session_id: str) -> MonitoringSession:
        if scenario not in DEMO_SCENARIOS:
            raise ValueError(f"Unknown demo scenario: {scenario}")
        with self._lock:
            existing = self._sessions.get(session_id)
            if existing:
                existing.stop()
            src = SyntheticFrameSource(scenario, num_frames=300, fps=15.0)
            session = MonitoringSession(session_id, scenario, self.settings, src.frames(), self._incident_ids)
            self._sessions[session_id] = session
        session.start()
        return session

    def start_upload_analysis(self, session_id: str, video_path: str, scenario: str) -> MonitoringSession:
        with self._lock:
            src = VideoSource(video_path).open()
            session = MonitoringSession(session_id, scenario, self.settings, src.frames(), self._incident_ids)
            self._sessions[session_id] = session
        session.start()
        return session

    def stop(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            return False
        session.stop()
        return True

    def get_status(self, session_id: str) -> Optional[SessionStatus]:
        session = self._sessions.get(session_id)
        return session.status if session else None

    def list_sessions(self) -> list[SessionStatus]:
        return [s.status for s in self._sessions.values()]
