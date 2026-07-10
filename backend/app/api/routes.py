from fastapi import APIRouter

from app.api.v1 import (
    dashboard,
    devices,
    health,
    ingestion,
    models,
    predictions,
    realtime,
    telemetry,
    warnings,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(predictions.router, prefix="/predictions", tags=["predictions"])
api_router.include_router(warnings.router, prefix="/warnings", tags=["warnings"])
api_router.include_router(realtime.router, prefix="/realtime", tags=["realtime"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["ingestion"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])