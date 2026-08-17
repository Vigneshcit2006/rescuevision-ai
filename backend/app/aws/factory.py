"""Builds the LocalStorage/S3Storage, Local/DynamoDBIncidentRepository, and
Mock/SNSNotificationService instances based on Settings, so the rest of the
app never branches on `environment` itself.
"""
from __future__ import annotations

from app.aws.notifications import MockNotificationService, NotificationService, SNSNotificationService
from app.aws.storage import LocalStorage, S3Storage, StorageService
from app.configuration.config import Settings
from app.incidents.repository import DynamoDBIncidentRepository, IncidentRepository, LocalIncidentRepository


def build_storage(settings: Settings) -> StorageService:
    if settings.storage_backend == "aws" and settings.s3_bucket:
        return S3Storage(settings.s3_bucket, settings.aws_region)
    return LocalStorage(settings.local_storage_dir)


def build_incident_repository(settings: Settings) -> IncidentRepository:
    if settings.incident_backend == "aws":
        return DynamoDBIncidentRepository(settings.dynamodb_table, settings.aws_region)
    return LocalIncidentRepository(settings.local_db_path)


def build_notification_service(settings: Settings) -> NotificationService:
    if settings.notification_backend == "aws" and settings.sns_topic_arn:
        return SNSNotificationService(settings.sns_topic_arn, settings.aws_region)
    return MockNotificationService()
