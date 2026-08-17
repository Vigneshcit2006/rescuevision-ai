"""
Explicit agent state machine: OBSERVE -> ANALYZE -> ASSESS -> PLAN -> ACT ->
VERIFY -> back to OBSERVE. Each call to VisionAgent.step() advances through
exactly one full cycle and returns the AgentDecision plus the trace of
states visited, so the audit trail required by docs/agent-workflow.md and
the observability requirements can be reconstructed from a single call.
"""
from __future__ import annotations

from enum import Enum


class AgentState(str, Enum):
    OBSERVE = "OBSERVE"
    ANALYZE = "ANALYZE"
    ASSESS = "ASSESS"
    PLAN = "PLAN"
    ACT = "ACT"
    VERIFY = "VERIFY"
