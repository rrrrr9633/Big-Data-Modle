from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.edge.contracts import EdgeGatewayConfig, RawPointValue
from app.ingestion.schemas import TelemetryEvent


def map_raw_value_to_event(raw: RawPointValue, gateway: EdgeGatewayConfig) -> TelemetryEvent:
    return TelemetryEvent(
        event_id=f"{gateway.gateway_id}-{raw.binding.device_code}-{raw.binding.point_code}-{uuid4().hex[:12]}",
        device_code=raw.binding.device_code,
        point_code=raw.binding.point_code,
        value=raw.value,
        unit=raw.binding.unit,
        quality=raw.quality,
        ts=raw.acquired_at or datetime.now(timezone.utc),
        gateway_id=gateway.gateway_id,
        source_topic=gateway.mqtt_topic,
    )
