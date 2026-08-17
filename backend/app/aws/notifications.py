"""Notification abstraction: MockNotificationService (local) and SNSNotificationService."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.incidents.models import Incident
from app.logging.structured_logger import get_logger, log_event

logger = get_logger("aws.notifications")


class NotificationService(ABC):
    @abstractmethod
    def notify(self, incident: Incident) -> bool: ...


class MockNotificationService(NotificationService):
    """Records notifications in-memory; used for local dev and tests."""

    def __init__(self):
        self.sent: list[Incident] = []

    def notify(self, incident: Incident) -> bool:
        self.sent.append(incident)
        log_event(
            logger,
            "notification.mock.sent",
            incident_id=incident.incident_id,
            severity=incident.severity,
            incident_type=incident.incident_type,
        )
        return True


class SNSNotificationService(NotificationService):
    def __init__(self, topic_arn: str, region: str):
        import boto3

        self.topic_arn = topic_arn
        self._client = boto3.client("sns", region_name=region)

    def notify(self, incident: Incident) -> bool:
        message = (
            f"RescueVision AI Incident {incident.incident_id}\n"
            f"Type: {incident.incident_type}\nSeverity: {incident.severity}\n"
            f"Confidence: {incident.confidence:.2f}\nLocation: {incident.location}\n"
            f"Recommended action: {incident.recommended_action}"
        )
        self._client.publish(
            TopicArn=self.topic_arn,
            Subject=f"RescueVision Incident {incident.incident_id} ({incident.severity})",
            Message=message,
        )
        log_event(logger, "notification.sns.sent", incident_id=incident.incident_id, topic_arn=self.topic_arn)
        return True
