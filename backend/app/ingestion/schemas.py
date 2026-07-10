from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class TelemetryEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=128)
    device_code: str = Field(min_length=1, max_length=64)
    point_code: str = Field(min_length=1, max_length=128)
    value: float
    unit: str | None = Field(default=None, max_length=32)
    quality: float = Field(default=1.0, ge=0.0, le=1.0)
    ts: datetime
    gateway_id: str | None = Field(default=None, max_length=64)
    source_topic: str | None = None

    @field_validator("device_code", "point_code", "gateway_id")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    def to_json_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")


def parse_json_object(raw: str | bytes | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        loaded = json.loads(raw)
    else:
        loaded = raw
    if not isinstance(loaded, dict):
        raise ValueError("遥测消息必须是 JSON 对象")
    return loaded


def parse_telemetry_event(
    raw: str | bytes | dict[str, Any],
    *,
    source_topic: str | None = None,
) -> TelemetryEvent:
    payload = parse_json_object(raw)
    if source_topic and not payload.get("source_topic"):
        payload = {**payload, "source_topic": source_topic}
    return TelemetryEvent.model_validate(payload)
