from __future__ import annotations

from app.ingestion.schemas import TelemetryEvent
from app.quality.idempotency import create_redis_client


def _coerce_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def update_device_snapshot(event: TelemetryEvent) -> None:
    client = create_redis_client()
    try:
        latest_key = f"device:{event.device_code}:latest"
        online_key = f"device:{event.device_code}:online"
        client.hset(
            latest_key,
            mapping={
                "device_code": event.device_code,
                "point_code": event.point_code,
                "value": event.value,
                "unit": event.unit or "",
                "quality": event.quality,
                "ts": event.ts.isoformat(),
                "event_id": event.event_id,
                "gateway_id": event.gateway_id or "",
            },
        )
        client.set(online_key, "1", ex=120)
    finally:
        client.close()


def read_device_snapshot(device_code: str) -> dict[str, object] | None:
    client = create_redis_client()
    try:
        payload = client.hgetall(f"device:{device_code}:latest")
        if not payload:
            return None
        return {
            "device_code": payload.get("device_code") or device_code,
            "point_code": payload.get("point_code") or "",
            "value": _coerce_float(payload.get("value")),
            "unit": payload.get("unit") or None,
            "quality": _coerce_float(payload.get("quality")),
            "ts": payload.get("ts") or None,
            "event_id": payload.get("event_id") or None,
            "gateway_id": payload.get("gateway_id") or None,
            "online": bool(client.exists(f"device:{device_code}:online")),
        }
    finally:
        client.close()


def read_all_device_snapshots() -> list[dict[str, object]]:
    client = create_redis_client()
    try:
        keys = sorted(client.keys("device:*:latest"))
    finally:
        client.close()

    snapshots: list[dict[str, object]] = []
    for key in keys:
        device_code = key.removeprefix("device:").removesuffix(":latest")
        snapshot = read_device_snapshot(device_code)
        if snapshot is not None:
            snapshots.append(snapshot)
    return snapshots