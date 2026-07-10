from __future__ import annotations

import logging
import threading

from app.core.config import settings
from app.ingestion.schemas import parse_telemetry_event
from app.realtime.device_snapshot import update_device_snapshot
from app.streams.kafka_client import parse_kafka_api_version
from app.tsdb.telemetry_repository import insert_telemetry_reading

logger = logging.getLogger(__name__)


def start_cleaned_telemetry_consumer() -> object | None:
    try:
        from kafka import KafkaConsumer
    except ImportError:
        logger.warning("Cleaned telemetry consumer skipped: kafka-python is not installed")
        return None

    stop_event = threading.Event()

    def consume() -> None:
        consumer = KafkaConsumer(
            settings.kafka_telemetry_cleaned_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            api_version=parse_kafka_api_version(settings.kafka_api_version),
            group_id=settings.kafka_cleaned_group_id,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            consumer_timeout_ms=1000,
        )
        logger.info(
            "Cleaned telemetry consumer started: topic=%s",
            settings.kafka_telemetry_cleaned_topic,
        )
        try:
            while not stop_event.is_set():
                for message in consumer:
                    try:
                        event = parse_telemetry_event(message.value)
                        insert_telemetry_reading(event)
                        update_device_snapshot(event)
                    except Exception as exc:
                        logger.warning("Cleaned telemetry write failed: %s", exc)
                    if stop_event.is_set():
                        break
        finally:
            consumer.close()
            logger.info("Cleaned telemetry consumer stopped")

    thread = threading.Thread(target=consume, name="cleaned-telemetry-consumer", daemon=True)
    thread.start()
    return stop_event.set
