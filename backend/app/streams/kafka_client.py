from __future__ import annotations


def parse_kafka_api_version(version: str) -> tuple[int, ...]:
    parts = [part.strip() for part in version.split(".") if part.strip()]
    if not parts:
        raise ValueError("Kafka API version must not be empty")
    return tuple(int(part) for part in parts)
