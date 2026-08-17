"""FastAPI application entrypoint for RescueVision AI."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.aws.factory import build_incident_repository, build_notification_service
from app.configuration.config import get_settings
from app.logging.structured_logger import new_request_id
from app.services.monitoring_service import MonitoringService

app = FastAPI(
    title="RescueVision AI",
    description="Agentic vision system for disaster-response monitoring, built on OpenCV 5.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request, call_next):
    request_id = new_request_id()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.on_event("startup")
def startup() -> None:
    settings = get_settings()
    app.state.settings = settings
    app.state.monitoring_service = MonitoringService(settings)
    app.state.incident_repo = build_incident_repository(settings)
    app.state.notifications = build_notification_service(settings)

    Path(settings.local_storage_dir).mkdir(parents=True, exist_ok=True)
    app.mount("/evidence", StaticFiles(directory=settings.local_storage_dir), name="evidence")


app.include_router(router)
