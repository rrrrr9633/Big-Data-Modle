import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.services.simulation_runtime import (
    ensure_simulation_model,
    start_complete_simulation,
)
from app.services.simulation_runtime import (
    runtime as simulation_runtime,
)
from app.streams.runtime import start_stream_runtime, stop_stream_runtime

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if settings.simulation_auto_start:
        ensure_simulation_model()
    consumers = (
        start_stream_runtime(require_all=True)
        if settings.simulation_auto_start
        else []
    )
    try:
        if settings.simulation_auto_start:
            await asyncio.sleep(max(settings.simulation_start_delay_seconds, 0.0))
            state = start_complete_simulation()
            logger.info(
                "Complete simulation started: mode=%s devices=%s interval=%ss",
                state.config.mode,
                len(state.device_codes),
                state.config.interval_seconds,
            )
        yield
    finally:
        simulation_runtime.stop()
        stop_stream_runtime(consumers)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        description="工业设备预测性维护系统 API",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
