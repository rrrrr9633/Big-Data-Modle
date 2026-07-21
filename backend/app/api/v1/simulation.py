from __future__ import annotations

from typing import Literal

from app.core.config import settings
from app.edge.device_stream import DeviceStreamConfig
from app.services.simulation_runtime import runtime, validate_complete_stream_configuration
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
SimulationMode = Literal["normal", "degrading", "sudden_fault", "sensor_stuck", "sensor_drift"]
SimulationTransport = Literal["local", "mqtt"]


class SimulationStartIn(BaseModel):
    device_count: int = Field(default=6, ge=1, le=24)
    mode: SimulationMode = "degrading"
    transport: SimulationTransport = "local"


def _state() -> dict[str, object]:
    state = runtime.snapshot()
    return {
        "running": state.running,
        "cycle": state.cycle,
        "mode": state.config.mode,
        "device_count": state.config.device_count,
        "interval_seconds": state.config.interval_seconds,
        "transport": state.config.transport,
        "pipeline": "本地进程内设备流" if state.config.transport == "local" else "MQTT → Kafka → 后端处理链路",
        "gateway_id": state.config.gateway_id,
        "devices": state.device_codes,
        "scenario_devices": state.scenario_devices,
        "accepted_events": state.accepted_events,
        "failed_cycles": state.failed_cycles,
        "last_published_at": state.last_published_at,
        "last_error": state.last_error,
    }


@router.get("/state")
def get_simulation_state() -> dict[str, object]:
    return _state()


def _require_control_api() -> None:
    if not settings.simulation_control_api_enabled:
        raise HTTPException(
            status_code=403,
            detail="完整模拟由后端启动流程托管，手动控制接口已关闭",
        )


@router.post("/start")
def start_simulation(payload: SimulationStartIn) -> dict[str, object]:
    _require_control_api()
    try:
        if payload.transport == "mqtt":
            validate_complete_stream_configuration()
        runtime.start(DeviceStreamConfig(device_count=payload.device_count, mode=payload.mode, transport=payload.transport))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"设备流启动失败：{exc}") from exc
    return _state()


@router.post("/tick")
def tick_simulation() -> dict[str, object]:
    _require_control_api()
    if not runtime.snapshot().running:
        raise HTTPException(status_code=409, detail="仿真场景未启动")
    runtime.emit_cycle()
    return _state()


@router.post("/stop")
def stop_simulation() -> dict[str, object]:
    _require_control_api()
    runtime.stop()
    return _state()
