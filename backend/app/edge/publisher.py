from __future__ import annotations

import json

from app.core.config import settings
from app.edge.contracts import EdgeGatewayConfig, PublishMode, PublishResult
from app.ingestion.kafka_producer import KafkaJsonProducer
from app.ingestion.schemas import TelemetryEvent


def publish_events(
    events: list[TelemetryEvent],
    *,
    gateway: EdgeGatewayConfig,
    mode: PublishMode = "dry-run",
) -> PublishResult:
    if mode == "mqtt":
        _publish_mqtt(events, gateway.mqtt_topic)
        target = gateway.mqtt_topic
    elif mode == "kafka":
        _publish_kafka(events)
        target = settings.kafka_telemetry_raw_topic
    else:
        target = "dry-run"
    return PublishResult(
        mode=mode,
        status="accepted",
        accepted_events=len(events),
        target=target,
        event_ids=[event.event_id for event in events],
    )


def _publish_mqtt(events: list[TelemetryEvent], topic: str) -> None:
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


def _publish_kafka(events: list[TelemetryEvent]) -> None:
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
