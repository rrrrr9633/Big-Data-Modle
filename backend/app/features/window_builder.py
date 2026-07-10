from __future__ import annotations

from app.compute.features import build_feature_window
from app.governance.pipeline import standardize_readings
from app.schemas.timeseries import SensorReading, TimeSeriesWindow
from app.tsdb.telemetry_repository import fetch_recent_telemetry_readings


def build_device_window_from_tsdb(
    *,
    device_code: str,
    limit: int = 120,
) -> TimeSeriesWindow | None:
    readings = fetch_recent_telemetry_readings(device_code=device_code, limit=limit)
    if not readings:
        return None
    governed = standardize_readings(readings)
    return build_feature_window(governed)


def build_device_window_from_readings(readings: list[SensorReading]) -> TimeSeriesWindow | None:
    if not readings:
        return None
    return build_feature_window(standardize_readings(readings))