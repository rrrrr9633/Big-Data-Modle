from __future__ import annotations

import logging
import threading

from app.core.config import settings
from app.features.schemas import window_event_from_window
from app.features.window_builder import build_device_window_from_tsdb
from app.ingestion.kafka_producer import KafkaJsonProducer
from app.ingestion.schemas import parse_telemetry_event
from app.streams.kafka_client import parse_kafka_api_version

logger = logging.getLogger(__name__)


def start_feature_consumer() -> object | None:
    try:
        from kafka import KafkaConsumer
    except ImportError:
        logger.warning("Feature consumer skipped: kafka-python is not installed")
        return None

    stop_event = threading.Event()
    producer = KafkaJsonProducer()

    def consume() -> None:
        consumer = KafkaConsumer(
            settings.kafka_telemetry_cleaned_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            api_version=parse_kafka_api_version(settings.kafka_api_version),
            group_id=settings.kafka_feature_group_id,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            consumer_timeout_ms=1000,
        )
        logger.info("Feature consumer started: topic=%s", settings.kafka_telemetry_cleaned_topic)
        try:
            while not stop_event.is_set():
                for message in consumer:
                    try:
                        event = parse_telemetry_event(message.value)
                        window = build_device_window_from_tsdb(
                            device_code=event.device_code,
                            limit=settings.feature_window_reading_limit,
                        )
                        if window is None:
                            continue
                        feature_event = window_event_from_window(window)
                        producer.send(
                            settings.kafka_features_windowed_topic,
                            feature_event.to_json_bytes(),
                            key=feature_event.device_code,
                        )
                    except Exception as exc:
                        logger.warning("Feature window build failed: %s", exc)
                    if stop_event.is_set():
                        break
        finally:
            consumer.close()
            producer.close()
            logger.info("Feature consumer stopped")

    thread = threading.Thread(target=consume, name="feature-consumer", daemon=True)
    thread.start()
    return stop_event.set
