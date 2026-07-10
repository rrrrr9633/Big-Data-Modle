from __future__ import annotations

from sqlalchemy.orm import Session

from app.realtime.device_snapshot import read_all_device_snapshots, read_device_snapshot
from app.repositories.maintenance_repository import fetch_predictions, fetch_warnings
from app.tsdb.telemetry_repository import fetch_latest_telemetry_points


def fetch_realtime_overview(db: Session) -> dict[str, object]:
    snapshots = read_all_device_snapshots()
    predictions = fetch_predictions(db, limit=50)
    warnings = fetch_warnings(db, limit=50)
    latest_prediction_by_device = _latest_by_device(predictions)
    latest_warning_by_device = _latest_by_device(warnings)

    devices = []
    for snapshot in snapshots:
        device_code = str(snapshot["device_code"])
        devices.append(
            {
                **snapshot,
                "latest_prediction": latest_prediction_by_device.get(device_code),
                "latest_warning": latest_warning_by_device.get(device_code),
            }
        )

    return {
        "devices": sorted(devices, key=_realtime_device_sort_key),
        "online_total": sum(1 for item in devices if item.get("online")),
        "device_total": len(devices),
        "warning_total": len(warnings),
        "prediction_total": len(predictions),
    }


def fetch_realtime_device(db: Session, device_code: str) -> dict[str, object]:
    snapshot = read_device_snapshot(device_code)
    predictions = [
        item for item in fetch_predictions(db, limit=100) if item.get("device_code") == device_code
    ]
    warnings = [
        item for item in fetch_warnings(db, limit=100) if item.get("device_code") == device_code
    ]
    return {
        "device_code": device_code,
        "snapshot": snapshot,
        "latest_points": fetch_latest_telemetry_points(device_code=device_code),
        "latest_prediction": predictions[0] if predictions else None,
        "latest_warning": warnings[0] if warnings else None,
    }


def _latest_by_device(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for row in rows:
        device_code = str(row.get("device_code") or "")
        if device_code and device_code not in latest:
            latest[device_code] = row
    return latest


def _realtime_device_sort_key(item: dict[str, object]) -> tuple[int, str]:
    prediction = item.get("latest_prediction")
    risk = prediction.get("risk_level") if isinstance(prediction, dict) else None
    rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(str(risk), 0)
    return (-rank, str(item.get("device_code") or ""))
