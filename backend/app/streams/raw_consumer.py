from __future__ import annotations

import json
import logging
import threading

from app.core.config import settings
from app.core.database import SessionLocal
from app.ingestion.kafka_producer import KafkaJsonProducer
from app.ingestion.schemas import parse_telemetry_event
from app.quality.idempotency import claim_event
from app.quality.normalizer import normalize_telemetry_event
from app.quality.point_catalog import validate_event_against_point_catalog
from app.quality.validator import validate_telemetry_event
from app.streams.kafka_client import parse_kafka_api_version

logger = logging.getLogger(__name__)


def start_raw_telemetry_consumer() -> object | None:
    try:
        from kafka import KafkaConsumer
    except ImportError:
        logger.warning("Raw telemetry consumer skipped: kafka-python is not installed")
        return None

    stop_event = threading.Event()
    producer = KafkaJsonProducer()

    def publish_invalid(raw: bytes, reason: str) -> None:
        invalid = {"reason": reason, "raw": raw.decode("utf-8", errors="replace")}
        producer.send(
            settings.kafka_telemetry_invalid_topic,
            json.dumps(invalid, ensure_ascii=False).encode("utf-8"),
        )

    def consume() -> None:
        consumer = KafkaConsumer(
            settings.kafka_telemetry_raw_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            api_version=parse_kafka_api_version(settings.kafka_api_version),
            group_id=settings.kafka_raw_group_id,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            consumer_timeout_ms=1000,
        )
        logger.info("Raw telemetry consumer started: topic=%s", settings.kafka_telemetry_raw_topic)
        try:
            while not stop_event.is_set():
                for message in consumer:
                    source_topic = message.key.decode("utf-8") if message.key else None
                    try:
                        event = normalize_telemetry_event(
                            parse_telemetry_event(message.value, source_topic=source_topic)
                        )
                        validation = validate_telemetry_event(event)
                        if not validation.valid:
                            publish_invalid(
                                message.value,
                                validation.reason or "invalid telemetry event",
                            )
                            continue
                        with SessionLocal() as db:
                            point_validation = validate_event_against_point_catalog(event, db)
                        if not point_validation.valid:
                            publish_invalid(
                                message.value,
                                point_validation.reason or "point catalog validation failed",
                            )
                            continue
                        if not claim_event(event.event_id):
                            logger.info("Duplicated telemetry ignored: event_id=%s", event.event_id)
                            continue
                        producer.send(
                            settings.kafka_telemetry_cleaned_topic,
                            event.to_json_bytes(),
                            key=event.device_code,
                        )
                    except Exception as exc:
                        logger.warning("Raw telemetry failed: %s", exc)
                        publish_invalid(message.value, str(exc))
                    if stop_event.is_set():
                        break
        finally:
            consumer.close()
            producer.close()
            logger.info("Raw telemetry consumer stopped")

    thread = threading.Thread(target=consume, name="raw-telemetry-consumer", daemon=True)
    thread.start()
    return stop_event.set
