from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.streams.runtime import start_stream_runtime, stop_stream_runtime


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    consumers = start_stream_runtime()
    try:
        yield
    finally:
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
