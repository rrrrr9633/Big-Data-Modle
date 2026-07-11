from fastapi import APIRouter

from app.api.v1 import (
    auth,
    dashboard,
    devices,
    health,
    ingestion,
    ingress,
    models,
    predictions,
    quality,
    realtime,
    runtime,
    simulation,
    telemetry,
    warnings,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(predictions.router, prefix="/predictions", tags=["predictions"])
api_router.include_router(warnings.router, prefix="/warnings", tags=["warnings"])
api_router.include_router(realtime.router, prefix="/realtime", tags=["realtime"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["ingestion"])
api_router.include_router(ingress.router, prefix="/ingress", tags=["ingress"])
api_router.include_router(quality.router, prefix="/quality", tags=["quality"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(runtime.router, prefix="/runtime", tags=["runtime"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["simulation"])
