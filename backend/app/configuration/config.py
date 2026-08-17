"""
Central configuration for RescueVision AI.

Every threshold, interval, and region referenced elsewhere in the codebase
is read from here (which in turn reads from environment variables / .env).
Nothing in vision/, agent/, or api/ should hard-code a magic number.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ScenarioType = Literal["fire_smoke", "person_down", "route_obstruction"]
Backend = Literal["local", "aws"]


class MonitoringConfig(BaseSettings):
    """Adaptive monitoring intervals, in seconds, per system state."""

    normal_interval_seconds: float = Field(default=5.0)
    possible_incident_interval_seconds: float = Field(default=2.0)
    confirmed_incident_interval_seconds: float = Field(default=0.5)


class DetectionThresholds(BaseSettings):
    """Confidence / persistence thresholds shared by all scenario detectors."""

    # Frame-level detector confidence required to count a frame as "positive"
    min_frame_confidence: float = Field(default=0.35)

    # Temporal persistence required to escalate possible -> confirmed
    possible_incident_seconds: float = Field(default=3.0)
    confirmed_incident_seconds: float = Field(default=8.0)

    # Rolling window (seconds) used by the temporal analyzer
    temporal_window_seconds: float = Field(default=15.0)

    # Motion score (0-1) above which a region is considered "active"
    motion_score_threshold: float = Field(default=0.15)

    # Fire/smoke color-ratio threshold (fraction of ROI pixels matching fire/smoke color model)
    fire_color_ratio_threshold: float = Field(default=0.06)
    smoke_color_ratio_threshold: float = Field(default=0.10)

    # Person-down: aspect ratio (width/height) of bounding box above which a
    # person silhouette is considered "horizontal" rather than standing
    horizontal_aspect_ratio_threshold: float = Field(default=1.4)
    fall_no_recovery_seconds: float = Field(default=5.0)

    # Route obstruction: fraction of restricted-region area occluded
    obstruction_area_ratio_threshold: float = Field(default=0.20)
    obstruction_persistence_seconds: float = Field(default=6.0)


class AgentPolicyConfig(BaseSettings):
    """Bounds on what the agent is allowed to decide autonomously."""

    high_confidence_autonomous_threshold: float = Field(default=0.85)
    human_approval_confidence_ceiling: float = Field(default=0.85)
    max_notifications_per_incident: int = Field(default=3)
    person_down_always_requires_approval: bool = Field(default=True)


class RegionOfInterest(BaseSettings):
    """Normalized (0-1) ROI box: x, y, w, h. Defaults cover the full frame."""

    x: float = 0.0
    y: float = 0.0
    w: float = 1.0
    h: float = 1.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", extra="ignore")

    environment: str = Field(default="local")
    storage_backend: Backend = Field(default="local")
    incident_backend: Backend = Field(default="local")
    notification_backend: Backend = Field(default="local")

    aws_region: str = Field(default="us-east-1")
    s3_bucket: str = Field(default="")
    dynamodb_table: str = Field(default="rescuevision-incidents")
    sns_topic_arn: str = Field(default="")

    local_storage_dir: str = Field(default="./data/evidence")
    local_db_path: str = Field(default="./data/incidents.db")

    default_scenario: ScenarioType = Field(default="fire_smoke")
    region_of_interest: RegionOfInterest = Field(default_factory=RegionOfInterest)

    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    thresholds: DetectionThresholds = Field(default_factory=DetectionThresholds)
    agent_policy: AgentPolicyConfig = Field(default_factory=AgentPolicyConfig)

    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()
