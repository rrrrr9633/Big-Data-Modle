from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.schemas.timeseries import SensorReading


@dataclass(frozen=True)
class ImportedAi4iDeviceSample:
    device_code: str
    device_name: str
    device_type: str
    failed: bool
    readings: list[SensorReading]


AI4I_SENSOR_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("Air temperature [K]", "air_temperature", "K"),
    ("Process temperature [K]", "process_temperature", "K"),
    ("Rotational speed [rpm]", "rotational_speed", "rpm"),
    ("Torque [Nm]", "torque", "Nm"),
    ("Tool wear [min]", "tool_wear", "min"),
)


def ai4i_feature_values(row: dict[str, str]) -> dict[str, float]:
    return {column: float(row[column]) for column, _sensor_code, _unit in AI4I_SENSOR_COLUMNS}


def transform_ai4i_row(
    row: dict[str, str],
    *,
    recorded_at: datetime | None = None,
) -> ImportedAi4iDeviceSample:
    device_code = row["Product ID"].strip()
    timestamp = recorded_at or _timestamp_from_udi(row.get("UDI"))
    readings = [
        SensorReading(
            device_id=device_code,
            sensor_code=sensor_code,
            timestamp=timestamp,
            value=float(row[column]),
            unit=unit,
        )
        for column, sensor_code, unit in AI4I_SENSOR_COLUMNS
    ]

    return ImportedAi4iDeviceSample(
        device_code=device_code,
        device_name=f"AI4I-{device_code}",
        device_type=row.get("Type", "unknown").strip() or "unknown",
        failed=row.get("Machine failure", "0").strip() == "1",
        readings=readings,
    )


def _timestamp_from_udi(udi: str | None) -> datetime:
    offset_minutes = max(int(udi or "1") - 1, 0)
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=offset_minutes)
