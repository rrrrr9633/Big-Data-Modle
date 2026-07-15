from __future__ import annotations

import csv
from pathlib import Path

from app.core.config import settings
from app.core.database import SessionLocal
from app.edge.device_stream import DeviceStreamConfig, DeviceStreamRuntime, DeviceStreamSimulator
from app.models.registry import ActiveModelState, get_active_model_state
from app.services.model_training import train_and_register_ai4i_model

runtime = DeviceStreamSimulator()


def ensure_simulation_model() -> ActiveModelState:
    state = get_active_model_state()
    if state.available:
        return state
    if not settings.simulation_model_bootstrap_enabled:
        raise RuntimeError("完整模拟模式缺少 active 模型，且模型自动训练未启用")

    dataset_path = _dataset_path(settings.simulation_model_dataset_path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"完整模拟模式训练数据不存在：{dataset_path}")
    with dataset_path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    with SessionLocal() as db:
        train_and_register_ai4i_model(db, rows)
        db.commit()
    return get_active_model_state()


def start_complete_simulation() -> DeviceStreamRuntime:
    _validate_stream_configuration()
    ensure_simulation_model()
    return runtime.start(
        DeviceStreamConfig(
            device_count=settings.simulation_device_count,
            mode=settings.simulation_mode,
            interval_seconds=settings.simulation_interval_seconds,
        )
    )


def _validate_stream_configuration() -> None:
    stages = {
        "MQTT_TO_KAFKA_ENABLED": settings.mqtt_to_kafka_enabled,
        "RAW_TELEMETRY_CONSUMER_ENABLED": settings.raw_telemetry_consumer_enabled,
        "CLEANED_TELEMETRY_CONSUMER_ENABLED": settings.cleaned_telemetry_consumer_enabled,
        "FEATURE_CONSUMER_ENABLED": settings.feature_consumer_enabled,
        "INFERENCE_CONSUMER_ENABLED": settings.inference_consumer_enabled,
    }
    disabled = [name for name, enabled in stages.items() if not enabled]
    if disabled:
        raise RuntimeError(f"完整模拟模式要求启用全部真实数据链路：{', '.join(disabled)}")


def _dataset_path(configured_path: str) -> Path:
    path = Path(configured_path).expanduser()
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()