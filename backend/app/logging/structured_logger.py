"""
Structured JSON logging with request/incident correlation IDs.

Every log line is a JSON object with at least: timestamp, level, event,
logger. This lets an incident's full trace (frame -> evidence -> agent
decision -> AWS action -> verification) be reconstructed by filtering on
incident_id, which is what docs/failure-cases.md and the evaluation
scripts rely on.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
import time
import uuid
from contextvars import ContextVar
from typing import Any

_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_incident_id: ContextVar[str] = ContextVar("incident_id", default="-")


def new_request_id() -> str:
    rid = f"req-{uuid.uuid4().hex[:12]}"
    _request_id.set(rid)
    return rid


def set_incident_context(incident_id: str) -> None:
    _incident_id.set(incident_id)


class IncidentIdGenerator:
    """Process-wide, thread-safe incident ID counter. Sharing a single
    instance across every MonitoringSession/VisionAgent prevents concurrent
    sessions from independently generating colliding RV-00001 IDs, which
    would silently overwrite each other's incidents in the repository."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counter = 0

    def next(self) -> str:
        with self._lock:
            self._counter += 1
            return f"RV-{self._counter:05d}"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": _request_id.get(),
            "incident_id": _incident_id.get(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info(event, extra={"extra_fields": fields})
