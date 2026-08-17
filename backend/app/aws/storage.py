"""Evidence storage abstraction: LocalStorage (filesystem) and S3Storage."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.logging.structured_logger import get_logger, log_event

logger = get_logger("aws.storage")


class StorageService(ABC):
    @abstractmethod
    def store_evidence(self, incident_id: str, jpeg_bytes: bytes) -> str:
        """Persist evidence bytes and return a retrievable URL/path."""


class LocalStorage(StorageService):
    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def store_evidence(self, incident_id: str, jpeg_bytes: bytes) -> str:
        path = self.directory / f"{incident_id}.jpg"
        path.write_bytes(jpeg_bytes)
        log_event(logger, "storage.local.store_evidence", incident_id=incident_id, path=str(path))
        return f"/evidence/{path.name}"


class S3Storage(StorageService):
    def __init__(self, bucket: str, region: str):
        import boto3

        self.bucket = bucket
        self._client = boto3.client("s3", region_name=region)

    def store_evidence(self, incident_id: str, jpeg_bytes: bytes) -> str:
        key = f"evidence/{incident_id}.jpg"
        self._client.put_object(Bucket=self.bucket, Key=key, Body=jpeg_bytes, ContentType="image/jpeg")
        url = f"s3://{self.bucket}/{key}"
        log_event(logger, "storage.s3.store_evidence", incident_id=incident_id, url=url)
        return url
