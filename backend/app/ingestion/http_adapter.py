from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import settings
from app.ingestion.http_schemas import TelemetryPayloadIn, parse_telemetry_payload
from app.ingestion.kafka_producer import KafkaJsonProducer
from app.ingestion.schemas import TelemetryEvent


def publish_payload_to_raw_topic(
    raw: str | bytes | dict[str, object] | TelemetryPayloadIn,
    *,
    protocol: str,
) -> dict[str, object]:
    payload = raw if isinstance(raw, TelemetryPayloadIn) else parse_telemetry_payload(raw)
    recorded_at = payload.recorded_at or datetime.now(UTC)
    events = [
        TelemetryEvent(
            event_id=str(uuid4()),
            device_code=payload.device_code,
            point_code=reading.sensor_code,
            value=reading.value,
            unit=reading.unit,
            quality=1.0,
            ts=recorded_at,
            gateway_id=protocol,
            source_topic=f"{protocol}:/api/v1/telemetry/readings",
        )
        for reading in payload.readings
    ]

    producer = KafkaJsonProducer()
    try:
        for event in events:
            producer.send(
                settings.kafka_telemetry_raw_topic,
                event.to_json_bytes(),
                key=event.device_code,
            )
    finally:
        producer.close()

    return {
        "status": "accepted",
        "mode": "async_raw_ingestion",
        "device_code": payload.device_code,
        "accepted_events": len(events),
        "raw_topic": settings.kafka_telemetry_raw_topic,
        "next_stages": [
            settings.kafka_telemetry_cleaned_topic,
            settings.kafka_features_windowed_topic,
            settings.kafka_predictions_created_topic,
        ],
    }