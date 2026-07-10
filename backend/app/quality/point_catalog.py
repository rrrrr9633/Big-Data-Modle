from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ingestion.schemas import TelemetryEvent
from app.quality.validator import ValidationResult


def validate_event_against_point_catalog(event: TelemetryEvent, db: Session) -> ValidationResult:
    row = (
        db.execute(
            text(
                """
            SELECT
              d.device_code,
              d.status,
              sp.sensor_code,
              sp.unit,
              sp.enabled,
              sp.min_value,
              sp.max_value
            FROM devices d
            LEFT JOIN sensor_points sp
              ON sp.device_code = d.device_code
             AND sp.sensor_code = :point_code
            WHERE d.device_code = :device_code
            LIMIT 1
            """
            ),
            {"device_code": event.device_code, "point_code": event.point_code},
        )
        .mappings()
        .first()
    )
    if not row or not row.get("sensor_code"):
        return ValidationResult(valid=False, reason="device or point is not registered")
    if not bool(row.get("enabled")):
        return ValidationResult(valid=False, reason="point is disabled")

    expected_unit = row.get("unit")
    if expected_unit and event.unit and str(expected_unit) != event.unit:
        return ValidationResult(
            valid=False, reason=f"unit mismatch: expected {expected_unit}, got {event.unit}"
        )

    min_value = row.get("min_value")
    max_value = row.get("max_value")
    if min_value is not None and event.value < float(min_value):
        return ValidationResult(valid=False, reason="value out of configured range")
    if max_value is not None and event.value > float(max_value):
        return ValidationResult(valid=False, reason="value out of configured range")

    return ValidationResult(valid=True)
