"""
VisionAgent: runs one full OBSERVE -> ANALYZE -> ASSESS -> PLAN -> ACT ->
VERIFY cycle per IncidentCandidate, using AgentPolicy for the ASSESS/PLAN
decision and AgentTools for every ACT-stage side effect. Returns an
AgentCycleResult carrying the full per-state trace for observability.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from app.agent.policy import AgentPolicy, PolicyOutcome
from app.agent.state_machine import AgentState
from app.agent.tools import AgentTools
from app.incidents.models import Incident
from app.logging.structured_logger import IncidentIdGenerator, get_logger, log_event, set_incident_context
from app.vision.evidence_extractor import IncidentCandidate

logger = get_logger("agent.core")

RECOMMENDED_ACTION_TEXT = {
    "NONE": "No action required; continue routine monitoring.",
    "SEND_ALERT": "Notify emergency response channel and store evidence.",
    "REQUEST_HUMAN_APPROVAL": "Escalate to a human operator for verification before notifying responders.",
    "STORE_EVIDENCE_ONLY": "Retain evidence and continue observation at increased frequency.",
}


@dataclass
class AgentTraceStep:
    state: str
    detail: str
    timestamp: float


@dataclass
class AgentCycleResult:
    trace: list[AgentTraceStep]
    outcome: PolicyOutcome
    incident: Optional[Incident]
    action_result: Optional[str]


class VisionAgent:
    def __init__(self, policy: AgentPolicy, tools: AgentTools, incident_ids: IncidentIdGenerator):
        self.policy = policy
        self.tools = tools
        self._incident_ids = incident_ids
        self._open_incident_ids: dict[str, str] = {}  # region -> open incident_id

    def step(self, candidate: IncidentCandidate) -> AgentCycleResult:
        trace: list[AgentTraceStep] = []
        # The full per-state trace is always kept in-memory for the caller
        # (SessionStatus.last_trace / incident audit trail). Emitting it to
        # the structured logger too is throttled to non-idle cycles only --
        # logging every OBSERVE/ANALYZE/ASSESS for thousands of "nothing
        # happened" frames during normal monitoring adds no audit value and
        # measurably slows frame throughput.
        should_log = candidate.state != "none"

        def record(state: AgentState, detail: str) -> None:
            trace.append(AgentTraceStep(state=state.value, detail=detail, timestamp=time.time()))
            if should_log:
                log_event(logger, f"agent.{state.value.lower()}", detail=detail)

        record(AgentState.OBSERVE, f"Received evidence for {candidate.scenario} in {candidate.region}.")

        evidence = candidate.to_agent_evidence()
        evidence["scenario"] = candidate.scenario
        record(
            AgentState.ANALYZE,
            f"state={evidence['state']} confidence={evidence['confidence']} duration={evidence['duration_seconds']}s",
        )

        outcome = self.policy.evaluate(evidence)
        record(AgentState.ASSESS, f"severity={outcome.severity} rationale={outcome.rationale}")
        record(
            AgentState.PLAN,
            f"decision={outcome.decision} action={outcome.action} human_approval={outcome.requires_human_approval}",
        )

        incident: Optional[Incident] = None
        action_result: Optional[str] = None

        if outcome.decision == "CREATE_INCIDENT":
            existing_id = self._open_incident_ids.get(candidate.region)
            now = time.time()
            if existing_id:
                incident = self.tools.ctx.incidents.update(
                    existing_id,
                    severity=outcome.severity,
                    confidence=candidate.confidence,
                    agent_decision=outcome.decision,
                    agent_rationale=outcome.rationale,
                    recommended_action=RECOMMENDED_ACTION_TEXT[outcome.action],
                    updated_at=now,
                )
                record(AgentState.ACT, f"Updated existing incident {existing_id} (evidence reinforced).")
            else:
                incident_id = self._incident_ids.next()
                set_incident_context(incident_id)
                evidence_url = self.tools.store_evidence(incident_id, candidate.evidence_frame_jpeg)
                incident = self.tools.create_incident(
                    Incident(
                        incident_id=incident_id,
                        timestamp=now,
                        incident_type=candidate.scenario,
                        severity=outcome.severity,
                        confidence=candidate.confidence,
                        location=candidate.region,
                        evidence_url=evidence_url,
                        agent_decision=outcome.decision,
                        agent_rationale=outcome.rationale,
                        recommended_action=RECOMMENDED_ACTION_TEXT[outcome.action],
                        human_approval_required=outcome.requires_human_approval,
                        human_approval_status="PENDING" if outcome.requires_human_approval else "NOT_REQUIRED",
                        created_at=now,
                        updated_at=now,
                    )
                )
                self._open_incident_ids[candidate.region] = incident_id
                record(AgentState.ACT, f"Created incident {incident_id}.")

            if incident is not None:
                if outcome.action == "SEND_ALERT" and not outcome.requires_human_approval:
                    sent = self.tools.send_notification(incident)
                    action_result = "NOTIFICATION_SENT" if sent else "NOTIFICATION_FAILED"
                elif outcome.action == "REQUEST_HUMAN_APPROVAL":
                    self.tools.request_human_approval(incident.incident_id)
                    action_result = "AWAITING_HUMAN_APPROVAL"
                else:
                    action_result = "EVIDENCE_STORED"

        elif outcome.decision == "INCREASE_MONITORING":
            self.tools.increase_monitoring_frequency(candidate.region, outcome.next_observation_seconds)
            record(AgentState.ACT, f"Increased monitoring frequency to every {outcome.next_observation_seconds}s.")
            action_result = "MONITORING_INCREASED"
        else:
            record(AgentState.ACT, "No action taken; remaining at normal monitoring frequency.")
            action_result = "NO_ACTION"
            open_id = self._open_incident_ids.get(candidate.region)
            if open_id:
                self.tools.close_incident(open_id, reason="Signal cleared during continued observation.")
                del self._open_incident_ids[candidate.region]

        record(AgentState.VERIFY, f"action_result={action_result}")

        return AgentCycleResult(trace=trace, outcome=outcome, incident=incident, action_result=action_result)
