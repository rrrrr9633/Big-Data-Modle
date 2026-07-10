from __future__ import annotations

import json
import logging
import threading

from app.core.config import settings
from app.features.schemas import parse_window_feature_event
from app.inference.predictor import run_async_inference
from app.inference.schemas import serialize_prediction_event, serialize_warning_event
from app.ingestion.kafka_producer import KafkaJsonProducer
from app.streams.kafka_client import parse_kafka_api_version

logger = logging.getLogger(__name__)


def start_inference_consumer() -> object | None:
    try:
        from kafka import KafkaConsumer
    except ImportError:
        logger.warning("Inference consumer skipped: kafka-python is not installed")
        return None

    stop_event = threading.Event()
    producer = KafkaJsonProducer()

    def publish(topic: str, payload: dict[str, object], *, key: str) -> None:
        producer.send(
            topic,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            key=key,
        )

    def consume() -> None:
        consumer = KafkaConsumer(
            settings.kafka_features_windowed_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            api_version=parse_kafka_api_version(settings.kafka_api_version),
            group_id=settings.kafka_inference_group_id,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            consumer_timeout_ms=1000,
        )
        logger.info("Inference consumer started: topic=%s", settings.kafka_features_windowed_topic)
        try:
            while not stop_event.is_set():
                for message in consumer:
                    try:
                        feature_event = parse_window_feature_event(message.value)
                        output = run_async_inference(feature_event)
                        publish(
                            settings.kafka_predictions_created_topic,
                            serialize_prediction_event(output),
                            key=output.result.device_id,
                        )
                        if output.warning_created:
                            publish(
                                settings.kafka_warnings_created_topic,
                                serialize_warning_event(output),
                                key=output.result.device_id,
                            )
                    except Exception as exc:
                        logger.warning("Async inference failed: %s", exc)
                    if stop_event.is_set():
                        break
        finally:
            consumer.close()
            producer.close()
            logger.info("Inference consumer stopped")

    thread = threading.Thread(target=consume, name="inference-consumer", daemon=True)
    thread.start()
    return stop_event.set
