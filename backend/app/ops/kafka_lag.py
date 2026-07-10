from __future__ import annotations

from typing import Any

from app.core.config import settings


def summarize_partition_lag(
    *,
    topic: str,
    partition: int,
    committed_offset: int | None,
    end_offset: int,
) -> dict[str, int | str | None]:
    lag = None if committed_offset is None else max(end_offset - committed_offset, 0)
    return {
        "topic": topic,
        "partition": partition,
        "committed_offset": committed_offset,
        "end_offset": end_offset,
        "lag": lag,
        "status": "uncommitted" if committed_offset is None else "ok",
    }


def get_streams_status() -> dict[str, Any]:
    configured_groups = [
        (settings.kafka_telemetry_raw_topic, settings.kafka_raw_group_id),
        (settings.kafka_telemetry_cleaned_topic, settings.kafka_cleaned_group_id),
        (settings.kafka_telemetry_cleaned_topic, settings.kafka_feature_group_id),
        (settings.kafka_features_windowed_topic, settings.kafka_inference_group_id),
    ]
    try:
        from kafka import KafkaConsumer, TopicPartition
    except ImportError:
        return _unavailable(configured_groups, "kafka-python is not installed")

    try:
        groups = [
            _get_group_status(
                KafkaConsumer=KafkaConsumer,
                TopicPartition=TopicPartition,
                topic=topic,
                group_id=group_id,
            )
            for topic, group_id in configured_groups
        ]
        status = "ok" if all(group["status"] in {"ok", "empty"} for group in groups) else "warning"
        return {
            "status": status,
            "bootstrap_servers": settings.kafka_bootstrap_servers,
            "groups": groups,
        }
    except Exception as exc:
        return _unavailable(configured_groups, str(exc))


def _get_group_status(
    *, KafkaConsumer: Any, TopicPartition: Any, topic: str, group_id: str
) -> dict[str, Any]:
    consumer = KafkaConsumer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        api_version=tuple(int(part) for part in settings.kafka_api_version.split(".")),
        group_id=group_id,
        enable_auto_commit=False,
        consumer_timeout_ms=3000,
    )
    try:
        partitions = sorted(consumer.partitions_for_topic(topic) or [])
        topic_partitions = [TopicPartition(topic, partition) for partition in partitions]
        end_offsets = consumer.end_offsets(topic_partitions) if topic_partitions else {}
        offsets = []
        for partition in topic_partitions:
            committed = consumer.committed(partition, metadata=True)
            offsets.append(
                summarize_partition_lag(
                    topic=topic,
                    partition=partition.partition,
                    committed_offset=committed.offset if committed else None,
                    end_offset=end_offsets.get(partition, 0),
                )
            )
        return {
            "group_id": group_id,
            "topic": topic,
            "partitions": offsets,
            "total_lag": sum(item["lag"] or 0 for item in offsets),
            "status": "empty" if not offsets else "ok",
        }
    finally:
        consumer.close()


def _unavailable(groups: list[tuple[str, str]], detail: str) -> dict[str, Any]:
    return {
        "status": "warning",
        "detail": detail,
        "groups": [
            {
                "group_id": group_id,
                "topic": topic,
                "partitions": [],
                "total_lag": None,
                "status": "unavailable",
            }
            for topic, group_id in groups
        ],
    }
