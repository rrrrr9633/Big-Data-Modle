from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import quote
from uuid import uuid4

from app.core.config import settings
from app.ingestion.http_schemas import TelemetryPayloadIn, parse_telemetry_payload
from app.ingestion.schemas import TelemetryEvent


def publish_payload_to_mqtt(
    raw: str | bytes | dict[str, object] | TelemetryPayloadIn,
    *,
    gateway_id: str = "frontend-simulator",
) -> dict[str, object]:
    payload = raw if isinstance(raw, TelemetryPayloadIn) else parse_telemetry_payload(raw)
    recorded_at = payload.recorded_at or datetime.now(timezone.utc)
    topic = build_device_telemetry_topic(payload.device_code)
    events = [
        TelemetryEvent(
            event_id=str(uuid4()),
            device_code=payload.device_code,
            point_code=reading.sensor_code,
            value=reading.value,
            unit=reading.unit,
            quality=1.0,
            ts=recorded_at,
            gateway_id=gateway_id,
            source_topic=topic,
        )
        for reading in payload.readings
    ]

    _publish_events(topic, events)

    return {
        "status": "accepted",
        "mode": "mqtt_emqx_ingestion",
        "device_code": payload.device_code,
        "accepted_events": len(events),
        "mqtt_topic": topic,
        "raw_topic": settings.kafka_telemetry_raw_topic,
        "next_stages": [
            settings.kafka_telemetry_raw_topic,
            settings.kafka_telemetry_cleaned_topic,
            settings.kafka_features_windowed_topic,
            settings.kafka_predictions_created_topic,
        ],
    }


def build_device_telemetry_topic(device_code: str) -> str:
    return (
        "factory/default"
        "/workshop/default"
        "/line/default"
        f"/machine/{quote(device_code, safe='')}"
        "/telemetry"
    )


def _publish_events(topic: str, events: list[TelemetryEvent]) -> None:
    try:
        import paho.mqtt.publish as publish
    except ImportError as exc:
        raise RuntimeError("paho-mqtt is not installed") from exc

    for event in events:
        publish.single(
            topic,
            payload=json.dumps(event.model_dump(mode="json"), ensure_ascii=False),
            hostname=settings.mqtt_broker_host,
            port=settings.mqtt_broker_port,
        )
