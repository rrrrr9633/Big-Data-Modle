from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.core.config import settings
from app.ingestion.mqtt_to_kafka import start_mqtt_to_kafka
from app.streams.cleaned_consumer import start_cleaned_telemetry_consumer
from app.streams.feature_consumer import start_feature_consumer
from app.streams.inference_consumer import start_inference_consumer
from app.streams.raw_consumer import start_raw_telemetry_consumer

logger = logging.getLogger(__name__)


@dataclass
class StreamRuntimeHandle:
    name: str
    stop: Callable[[], None]


def start_stream_runtime(*, require_all: bool = False) -> list[StreamRuntimeHandle]:
    handles: list[StreamRuntimeHandle] = []
    stages: list[tuple[str, bool, Callable[[], object | None]]] = [
        ("mqtt-to-kafka", settings.mqtt_to_kafka_enabled, start_mqtt_to_kafka),
        ("raw-telemetry", settings.raw_telemetry_consumer_enabled, start_raw_telemetry_consumer),
        (
            "cleaned-telemetry",
            settings.cleaned_telemetry_consumer_enabled,
            start_cleaned_telemetry_consumer,
        ),
        ("feature-window", settings.feature_consumer_enabled, start_feature_consumer),
        ("async-inference", settings.inference_consumer_enabled, start_inference_consumer),
    ]

    try:
        for name, enabled, starter in stages:
            if not enabled:
                continue
            stop = starter()
            if callable(stop):
                handles.append(StreamRuntimeHandle(name=name, stop=stop))
            elif require_all:
                raise RuntimeError(f"完整模拟模式无法启动数据链路阶段：{name}")
    except Exception:
        stop_stream_runtime(handles)
        raise
    return handles


def stop_stream_runtime(handles: list[StreamRuntimeHandle]) -> None:
    for handle in handles:
        handle.stop()
        logger.info("%s stream runtime stop requested", handle.name)
