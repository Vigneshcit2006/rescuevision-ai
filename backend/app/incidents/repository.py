"""
IncidentRepository interface plus Local (in-memory + SQLite persistence) and
DynamoDB implementations, selected by Settings.incident_backend so the whole
app works identically with or without AWS credentials.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.incidents.models import Incident


class IncidentRepository(ABC):
    @abstractmethod
    def create(self, incident: Incident) -> Incident: ...

    @abstractmethod
    def get(self, incident_id: str) -> Optional[Incident]: ...

    @abstractmethod
    def list(self, limit: int = 100) -> list[Incident]: ...

    @abstractmethod
    def update(self, incident_id: str, **fields) -> Optional[Incident]: ...


class LocalIncidentRepository(IncidentRepository):
    """SQLite-backed repository for local/offline development and tests."""

    def __init__(self, db_path: str):
        self._lock = threading.Lock()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=10000")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS incidents (incident_id TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )
        self._conn.commit()

    def create(self, incident: Incident) -> Incident:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO incidents (incident_id, data) VALUES (?, ?)",
                (incident.incident_id, incident.model_dump_json()),
            )
            self._conn.commit()
        return incident

    def get(self, incident_id: str) -> Optional[Incident]:
        row = self._conn.execute(
            "SELECT data FROM incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        return Incident.model_validate_json(row[0]) if row else None

    def list(self, limit: int = 100) -> list[Incident]:
        rows = self._conn.execute(
            "SELECT data FROM incidents ORDER BY incident_id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Incident.model_validate_json(r[0]) for r in rows]

    def update(self, incident_id: str, **fields) -> Optional[Incident]:
        existing = self.get(incident_id)
        if existing is None:
            return None
        updated = existing.model_copy(update=fields)
        return self.create(updated)


class DynamoDBIncidentRepository(IncidentRepository):
    """Production repository backed by Amazon DynamoDB."""

    def __init__(self, table_name: str, region: str):
        import boto3

        self._table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    def create(self, incident: Incident) -> Incident:
        self._table.put_item(Item=json.loads(incident.model_dump_json()))
        return incident

    def get(self, incident_id: str) -> Optional[Incident]:
        resp = self._table.get_item(Key={"incident_id": incident_id})
        item = resp.get("Item")
        return Incident.model_validate(item) if item else None

    def list(self, limit: int = 100) -> list[Incident]:
        resp = self._table.scan(Limit=limit)
        return [Incident.model_validate(i) for i in resp.get("Items", [])]

    def update(self, incident_id: str, **fields) -> Optional[Incident]:
        existing = self.get(incident_id)
        if existing is None:
            return None
        updated = existing.model_copy(update=fields)
        return self.create(updated)
