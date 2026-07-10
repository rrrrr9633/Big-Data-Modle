from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class TelemetryReadingIn(BaseModel):
    sensor_code: str = Field(min_length=1, max_length=64)
    value: float
    unit: str | None = None


class TelemetryPayloadIn(BaseModel):
    device_code: str = Field(min_length=1, max_length=64)
    device_name: str = Field(min_length=1, max_length=128)
    device_type: str = Field(default="unknown", max_length=64)
    recorded_at: datetime | None = None
    readings: list[TelemetryReadingIn] = Field(min_length=1)


def parse_telemetry_payload(raw: str | bytes | dict[str, Any]) -> TelemetryPayloadIn:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        raw = json.loads(raw)
    return TelemetryPayloadIn.model_validate(raw)


def error_message_from_payload(reason: Exception) -> str:
    if isinstance(reason, ValidationError):
        return reason.errors()[0].get("msg", "消息结构不符合遥测接入协议")
    if isinstance(reason, json.JSONDecodeError):
        return "消息不是合法 JSON"
    return str(reason)