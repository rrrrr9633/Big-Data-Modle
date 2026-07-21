from __future__ import annotations

import threading

from app.core.config import settings
from app.ingestion.schemas import TelemetryEvent
from app.quality.idempotency import create_redis_client

_local_snapshots: dict[str, dict[str, object]] = {}
_local_snapshot_lock = threading.RLock()
_local_source_authoritative = False


def _coerce_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def update_local_device_snapshot(event: TelemetryEvent) -> None:
    global _local_source_authoritative
    with _local_snapshot_lock:
        _local_source_authoritative = True
        current = _local_snapshots.setdefault(
            event.device_code,
            {
                "device_code": event.device_code,
                "points": {},
                "online": True,
            },
        )
        points = current["points"]
        if isinstance(points, dict):
            points[event.point_code] = {
                "point_code": event.point_code,
                "value": event.value,
                "unit": event.unit,
                "quality": event.quality,
                "status": event.status,
                "ts": event.ts.isoformat(),
                "event_id": event.event_id,
            }
        current.update(
            {
                "point_code": event.point_code,
                "value": event.value,
                "unit": event.unit,
                "quality": event.quality,
                "status": event.status,
                "ts": event.ts.isoformat(),
                "event_id": event.event_id,
                "gateway_id": event.gateway_id,
                "online": True,
            }
        )


def clear_local_device_snapshots(*, authoritative: bool | None = None) -> None:
    global _local_source_authoritative
    with _local_snapshot_lock:
        _local_snapshots.clear()
        if authoritative is not None:
            _local_source_authoritative = authoritative


def _uses_local_snapshot_source() -> bool:
    with _local_snapshot_lock:
        return _local_source_authoritative


def _read_local_device_snapshot(device_code: str) -> dict[str, object] | None:
    with _local_snapshot_lock:
        snapshot = _local_snapshots.get(device_code)
        if snapshot is None:
            return None
        return {
            **snapshot,
            "points": dict(snapshot.get("points", {})),
        }


def _read_all_local_device_snapshots() -> list[dict[str, object]]:
    with _local_snapshot_lock:
        device_codes = sorted(_local_snapshots)
    return [
        snapshot
        for device_code in device_codes
        if (snapshot := _read_local_device_snapshot(device_code)) is not None
    ]


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
                "status": event.status,
                "ts": event.ts.isoformat(),
                "event_id": event.event_id,
                "gateway_id": event.gateway_id or "",
            },
        )
        client.expire(latest_key, settings.redis_latest_snapshot_ttl_seconds)
        client.set(online_key, "1", ex=settings.redis_online_ttl_seconds)
    finally:
        client.close()


def read_device_snapshot(device_code: str) -> dict[str, object] | None:
    local_snapshot = _read_local_device_snapshot(device_code)
    if local_snapshot is not None:
        return local_snapshot
    if _uses_local_snapshot_source():
        return None
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
            "status": payload.get("status") or "good",
            "ts": payload.get("ts") or None,
            "event_id": payload.get("event_id") or None,
            "gateway_id": payload.get("gateway_id") or None,
            "online": bool(client.exists(f"device:{device_code}:online")),
        }
    finally:
        client.close()


def read_all_device_snapshots() -> list[dict[str, object]]:
    local_snapshots = _read_all_local_device_snapshots()
    if local_snapshots or _uses_local_snapshot_source():
        return local_snapshots
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
