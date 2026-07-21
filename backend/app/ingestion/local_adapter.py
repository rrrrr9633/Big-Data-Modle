from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.ingestion.http_schemas import TelemetryPayloadIn, parse_telemetry_payload
from app.ingestion.schemas import TelemetryEvent
from app.realtime.device_snapshot import update_local_device_snapshot


def accept_payload_locally(
    raw: str | bytes | dict[str, object] | TelemetryPayloadIn,
    *,
    gateway_id: str = "local-simulator",
) -> dict[str, object]:
    payload = raw if isinstance(raw, TelemetryPayloadIn) else parse_telemetry_payload(raw)
    recorded_at = payload.recorded_at or datetime.now(timezone.utc)
    events = [
        TelemetryEvent(
            event_id=str(uuid4()),
            device_code=payload.device_code,
            point_code=reading.sensor_code,
            value=reading.value,
            unit=reading.unit,
            quality=reading.quality,
            status=reading.status,
            ts=recorded_at,
            gateway_id=gateway_id,
            source_topic="local:device-stream",
        )
        for reading in payload.readings
    ]
    for event in events:
        update_local_device_snapshot(event)

    return {
        "status": "accepted",
        "mode": "local_memory_ingestion",
        "device_code": payload.device_code,
        "accepted_events": len(events),
        "next_stages": ["in_process_snapshot"],
    }
