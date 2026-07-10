from __future__ import annotations

from app.ingestion.schemas import TelemetryEvent


def normalize_telemetry_event(event: TelemetryEvent) -> TelemetryEvent:
    return event.model_copy(
        update={
            "device_code": event.device_code.upper(),
            "point_code": event.point_code.strip(),
            "unit": event.unit.strip() if event.unit else None,
            "gateway_id": event.gateway_id.strip() if event.gateway_id else None,
        }
    )
