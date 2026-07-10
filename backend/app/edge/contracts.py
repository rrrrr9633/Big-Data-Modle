from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EdgeProtocol = Literal["modbus", "opcua", "s7", "cnc"]
PublishMode = Literal["mqtt", "kafka", "dry-run"]


class EdgeGatewayConfig(BaseModel):
    gateway_id: str = Field(min_length=1, max_length=64)
    factory: str = Field(default="default", max_length=128)
    workshop: str = Field(default="default", max_length=128)
    production_line: str = Field(default="default", max_length=128)
    mqtt_topic: str
    publish_mode: PublishMode = "mqtt"


class EdgePointBinding(BaseModel):
    device_code: str = Field(min_length=1, max_length=64)
    point_code: str = Field(min_length=1, max_length=128)
    point_name: str | None = Field(default=None, max_length=128)
    unit: str | None = Field(default=None, max_length=32)
    sampling_frequency: str = Field(default="realtime", max_length=64)
    protocol: EdgeProtocol
    source_address: str = Field(min_length=1, max_length=255)
    feature_name: str | None = Field(default=None, max_length=128)
    quality_rule: str | None = Field(default=None, max_length=255)
    min_value: float | None = None
    max_value: float | None = None
    enabled: bool = True
    protocol_options: dict[str, Any] = Field(default_factory=dict)


class EdgeAdapterConfig(BaseModel):
    gateway: EdgeGatewayConfig
    points: list[EdgePointBinding]
    payload_schema: list[str]
    runtime_contract: dict[str, Any]


class RawPointValue(BaseModel):
    binding: EdgePointBinding
    value: float
    quality: float = Field(default=1.0, ge=0.0, le=1.0)
    acquired_at: datetime
    raw_status: str = "simulated"
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class PublishResult(BaseModel):
    mode: PublishMode
    status: str
    accepted_events: int
    target: str
    event_ids: list[str]
