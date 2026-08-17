import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.configuration.config import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        storage_backend="local",
        incident_backend="local",
        notification_backend="local",
        local_storage_dir=str(tmp_path / "evidence"),
        local_db_path=str(tmp_path / "incidents.db"),
    )
