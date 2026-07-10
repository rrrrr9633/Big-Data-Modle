from __future__ import annotations

import logging

from app.core.config import settings
from app.streams.kafka_client import parse_kafka_api_version

logger = logging.getLogger(__name__)


class KafkaJsonProducer:
    def __init__(self) -> None:
        try:
            from kafka import KafkaProducer
        except ImportError as exc:
            raise RuntimeError("kafka-python is not installed") from exc

        self._producer = KafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            api_version=parse_kafka_api_version(settings.kafka_api_version),
            value_serializer=lambda value: value,
            retries=3,
        )

    def send(self, topic: str, payload: bytes, *, key: str | None = None) -> None:
        encoded_key = key.encode("utf-8") if key else None
        future = self._producer.send(topic, value=payload, key=encoded_key)
        future.get(timeout=10)
        logger.debug("Kafka event produced: topic=%s key=%s", topic, key)

    def close(self) -> None:
        self._producer.flush(timeout=10)
        self._producer.close(timeout=10)
