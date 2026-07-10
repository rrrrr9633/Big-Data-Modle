from __future__ import annotations

import logging

from app.core.config import settings
from app.ingestion.kafka_producer import KafkaJsonProducer

logger = logging.getLogger(__name__)


def start_mqtt_to_kafka() -> object | None:
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        logger.warning("MQTT to Kafka skipped: paho-mqtt is not installed")
        return None

    producer = KafkaJsonProducer()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=settings.mqtt_client_id)

    def on_connect(client, _userdata, _flags, reason_code, _properties) -> None:
        if reason_code == 0:
            client.subscribe(settings.mqtt_telemetry_topic)
            logger.info("MQTT to Kafka started: topic=%s", settings.mqtt_telemetry_topic)
        else:
            logger.warning("MQTT to Kafka connect failed: %s", reason_code)

    def on_message(_client, _userdata, message) -> None:
        try:
            producer.send(
                settings.kafka_telemetry_raw_topic,
                bytes(message.payload),
                key=message.topic,
            )
        except Exception as exc:
            logger.warning("MQTT message produce failed: topic=%s error=%s", message.topic, exc)

    def stop() -> None:
        client.loop_stop()
        client.disconnect()
        producer.close()

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, keepalive=60)
    client.loop_start()
    return stop
