"""
Policy layer: the ONLY place that decides severity/action from evidence.
This is what "the agent cannot execute unrestricted dangerous actions" and
"do not hard-code these decisions" mean in practice -- every threshold
comes from AgentPolicyConfig/DetectionThresholds (configuration.config),
and the policy is pure/deterministic so it is unit-testable in isolation
(see backend/tests/test_agent_policy.py).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.configuration.config import AgentPolicyConfig, DetectionThresholds

Severity = str  # "NONE" | "LOW" | "MEDIUM" | "HIGH"
Decision = str  # "NO_ACTION" | "CONTINUE_OBSERVATION" | "INCREASE_MONITORING" | "CREATE_INCIDENT" | "UPDATE_INCIDENT"
Action = str  # "NONE" | "SEND_ALERT" | "REQUEST_HUMAN_APPROVAL" | "STORE_EVIDENCE_ONLY"


@dataclass
class PolicyOutcome:
    severity: Severity
    decision: Decision
    action: Action
    requires_human_approval: bool
    next_observation_seconds: float
    rationale: str


class AgentPolicy:
    def __init__(self, agent_policy: AgentPolicyConfig, thresholds: DetectionThresholds, monitoring):
        self.p = agent_policy
        self.t = thresholds
        self.m = monitoring

    def evaluate(self, evidence: dict) -> PolicyOutcome:
        state = evidence.get("state", "none")
        scenario = evidence.get("scenario", evidence.get("event_type", "unknown"))
        confidence = float(evidence.get("confidence", 0.0))
        duration = float(evidence.get("duration_seconds", 0.0))

        if state == "none" or confidence < self.t.min_frame_confidence:
            return PolicyOutcome(
                severity="NONE",
                decision="CONTINUE_OBSERVATION",
                action="NONE",
                requires_human_approval=False,
                next_observation_seconds=self.m.normal_interval_seconds,
                rationale="No positive signal above minimum frame confidence; remain in normal monitoring.",
            )

        if state == "possible":
            severity = "LOW" if confidence < 0.6 else "MEDIUM"
            return PolicyOutcome(
                severity=severity,
                decision="INCREASE_MONITORING",
                action="STORE_EVIDENCE_ONLY",
                requires_human_approval=False,
                next_observation_seconds=self.m.possible_incident_interval_seconds,
                rationale=(
                    f"Signal present for {duration:.1f}s but below confirmed-persistence threshold "
                    f"({self.t.confirmed_incident_seconds}s); increase observation frequency and retain evidence."
                ),
            )

        # state == "confirmed"
        severity = "HIGH" if confidence >= self.p.high_confidence_autonomous_threshold else "MEDIUM"

        person_down_gate = scenario in ("person_down",) and self.p.person_down_always_requires_approval
        low_confidence_gate = confidence < self.p.human_approval_confidence_ceiling
        requires_approval = person_down_gate or low_confidence_gate

        action = "REQUEST_HUMAN_APPROVAL" if requires_approval else "SEND_ALERT"
        rationale_parts = [
            f"Confirmed {scenario} persisted {duration:.1f}s with rolling confidence {confidence:.2f}."
        ]
        if person_down_gate:
            rationale_parts.append("person_down scenario always routes through human approval per policy.")
        elif low_confidence_gate:
            rationale_parts.append(
                f"confidence below autonomous-action ceiling ({self.p.human_approval_confidence_ceiling}); human approval required."
            )
        else:
            rationale_parts.append("confidence meets autonomous-action threshold; alert dispatched directly.")

        return PolicyOutcome(
            severity=severity,
            decision="CREATE_INCIDENT",
            action=action,
            requires_human_approval=requires_approval,
            next_observation_seconds=self.m.confirmed_incident_interval_seconds,
            rationale=" ".join(rationale_parts),
        )
