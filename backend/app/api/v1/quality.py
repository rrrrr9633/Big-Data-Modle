from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.streams.kafka_client import parse_kafka_api_version
from app.tsdb.telemetry_repository import fetch_point_quality_summary
from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/summary")
def get_quality_summary(
    minutes: int = Query(default=60, ge=1, le=1440),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    invalid_trace_status = "ok"
    invalid_trace_error = None
    try:
        invalid_events = fetch_recent_invalid_telemetry_events(min(limit, 50))
    except Exception as exc:
        invalid_events = []
        invalid_trace_status = "unavailable"
        invalid_trace_error = str(exc)

    return {
        "window_minutes": minutes,
        "invalid_topic": settings.kafka_telemetry_invalid_topic,
        "quality_points": fetch_point_quality_summary(minutes=minutes, limit=limit),
        "invalid_events": invalid_events,
        "invalid_trace_status": invalid_trace_status,
        "invalid_trace_error": invalid_trace_error,
    }


def fetch_recent_invalid_telemetry_events(limit: int = 50) -> list[dict[str, Any]]:
    try:
        from kafka import KafkaConsumer
    except ImportError as exc:
        raise RuntimeError("kafka-python is not installed") from exc

    consumer = KafkaConsumer(
        settings.kafka_telemetry_invalid_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        api_version=parse_kafka_api_version(settings.kafka_api_version),
        auto_offset_reset="latest",
        enable_auto_commit=False,
        consumer_timeout_ms=800,
    )
    events: list[dict[str, Any]] = []
    try:
        for message in consumer:
            events.append(_decode_invalid_event(message.value))
            if len(events) >= limit:
                break
    finally:
        consumer.close()
    return events


def _decode_invalid_event(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"reason": "invalid dead-letter payload", "raw": text}
    if isinstance(payload, dict):
        return payload
    return {"reason": "invalid dead-letter payload", "raw": payload}
