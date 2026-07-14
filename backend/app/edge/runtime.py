from __future__ import annotations

from datetime import datetime, timezone

from app.edge.adapters import get_adapter
from app.edge.contracts import EdgeAdapterConfig, PublishMode, PublishResult, RawPointValue
from app.edge.mapper import map_raw_value_to_event
from app.edge.publisher import publish_events
from app.edge.simulation import simulated_value
from app.ingestion.schemas import TelemetryEvent


def collect_once(config: EdgeAdapterConfig) -> list[TelemetryEvent]:
    events: list[TelemetryEvent] = []
    for binding in config.points:
        if not binding.enabled:
            continue
        events.append(
            map_raw_value_to_event(
                simulated_value(binding, salt=binding.protocol),
                config.gateway,
            )
        )
    return events


def collect_live_once(config: EdgeAdapterConfig) -> list[TelemetryEvent]:
    events: list[TelemetryEvent] = []
    for binding in config.points:
        if not binding.enabled:
            continue
        adapter = get_adapter(binding.protocol)
        try:
            raw_value = adapter.read(binding)
        except Exception as exc:
            raw_value = RawPointValue(
                binding=binding,
                value=0.0,
                quality=0.0,
                acquired_at=datetime.now(timezone.utc),
                raw_status="read_failed",
                raw_payload={"protocol": binding.protocol, "error": str(exc)},
            )
        events.append(map_raw_value_to_event(raw_value, config.gateway))
    return events


def collect_and_publish(
    config: EdgeAdapterConfig,
    *,
    mode: PublishMode = "dry-run",
) -> PublishResult:
    events = collect_once(config)
    return publish_events(events, gateway=config.gateway, mode=mode)
