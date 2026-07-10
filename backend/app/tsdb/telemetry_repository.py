from __future__ import annotations

import json
from datetime import datetime

from app.ingestion.schemas import TelemetryEvent
from app.schemas.timeseries import PredictionResult, SensorReading
from app.tsdb.client import tsdb_connection

INSERT_TELEMETRY_SQL = """
INSERT INTO telemetry_readings (
  time,
  device_code,
  point_code,
  value,
  unit,
  quality,
  event_id,
  gateway_id,
  source_topic
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING
"""

INSERT_FEATURE_WINDOW_SQL = """
INSERT INTO feature_window_events (
  time,
  event_id,
  device_code,
  window_start,
  window_end,
  feature_values,
  source
) VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING
"""

INSERT_PREDICTION_METRIC_SQL = """
INSERT INTO prediction_metrics (
  time,
  prediction_id,
  feature_window_id,
  device_code,
  model_version,
  failure_probability,
  health_score,
  risk_level,
  anomaly_score,
  trend_factor,
  quality_score,
  rul_hours
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING
"""

INSERT_DEVICE_STATUS_SQL = """
INSERT INTO device_status_events (
  time,
  device_code,
  status,
  reason,
  source
) VALUES (%s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING
"""


def insert_telemetry_reading(event: TelemetryEvent) -> None:
    with tsdb_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                INSERT_TELEMETRY_SQL,
                (
                    event.ts,
                    event.device_code,
                    event.point_code,
                    event.value,
                    event.unit,
                    event.quality,
                    event.event_id,
                    event.gateway_id,
                    event.source_topic,
                ),
            )


def insert_sensor_reading_timeseries(
    *,
    device_code: str,
    sensor_code: str,
    recorded_at: datetime,
    value: float,
    unit: str | None,
    event_id: str,
    gateway_id: str | None = None,
    source_topic: str | None = None,
    quality: float = 1.0,
) -> None:
    insert_telemetry_reading(
        TelemetryEvent(
            event_id=event_id,
            device_code=device_code,
            point_code=sensor_code,
            value=value,
            unit=unit,
            quality=quality,
            ts=recorded_at,
            gateway_id=gateway_id,
            source_topic=source_topic,
        )
    )


def insert_feature_window_event(
    *,
    event_id: str,
    device_code: str,
    start_time: datetime,
    end_time: datetime,
    feature_values: dict[str, float],
    source: str,
) -> None:
    with tsdb_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                INSERT_FEATURE_WINDOW_SQL,
                (
                    end_time,
                    event_id,
                    device_code,
                    start_time,
                    end_time,
                    json.dumps(feature_values, ensure_ascii=False),
                    source,
                ),
            )


def insert_prediction_metric(
    *,
    prediction_id: int,
    feature_window_id: int,
    model_version: str,
    result: PredictionResult,
    created_at: datetime,
) -> None:
    with tsdb_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                INSERT_PREDICTION_METRIC_SQL,
                (
                    created_at,
                    prediction_id,
                    feature_window_id,
                    result.device_id,
                    model_version,
                    result.failure_probability,
                    result.health_score,
                    result.risk_level,
                    result.anomaly_score,
                    result.trend_factor,
                    result.quality_score,
                    result.rul_hours,
                ),
            )


def insert_device_status_event(
    *,
    device_code: str,
    status: str,
    time: datetime,
    reason: str | None = None,
    source: str | None = None,
) -> None:
    with tsdb_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                INSERT_DEVICE_STATUS_SQL,
                (time, device_code, status, reason, source),
            )


def fetch_recent_telemetry_readings(
    *,
    device_code: str,
    limit: int = 120,
) -> list[SensorReading]:
    with tsdb_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT device_code, point_code, time, value, unit
                FROM (
                  SELECT device_code, point_code, time, value, unit
                  FROM telemetry_readings
                  WHERE device_code = %s
                  ORDER BY time DESC
                  LIMIT %s
                ) recent
                ORDER BY time ASC
                """,
                (device_code, limit),
            )
            rows = cursor.fetchall()
    return [
        SensorReading(
            device_id=str(row[0]),
            sensor_code=str(row[1]),
            timestamp=row[2],
            value=float(row[3]) if row[3] is not None else None,
            unit=row[4],
        )
        for row in rows
    ]


def fetch_latest_telemetry_points(
    *,
    device_code: str,
    limit: int = 20,
) -> list[dict[str, object]]:
    with tsdb_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (point_code)
                  point_code,
                  value,
                  unit,
                  quality,
                  time,
                  event_id,
                  gateway_id
                FROM telemetry_readings
                WHERE device_code = %s
                ORDER BY point_code, time DESC
                LIMIT %s
                """,
                (device_code, limit),
            )
            rows = cursor.fetchall()
    return [
        {
            "point_code": str(row[0]),
            "value": float(row[1]) if row[1] is not None else None,
            "unit": row[2],
            "quality": float(row[3]) if row[3] is not None else None,
            "ts": row[4].isoformat() if row[4] is not None else None,
            "event_id": row[5],
            "gateway_id": row[6],
        }
        for row in rows
    ]