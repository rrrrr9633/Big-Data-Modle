"""AI4I standard row schema and TelemetryPayloadIn projection."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Mapping

from app.ingestion.http_schemas import TelemetryPayloadIn

AI4I_CSV_HEADERS: tuple[str, ...] = (
    "UDI",
    "Product ID",
    "Type",
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
    "Machine failure",
    "TWF",
    "HDF",
    "PWF",
    "OSF",
    "RNF",
)

AI4I_REQUIRED_FIELDS: tuple[str, ...] = AI4I_CSV_HEADERS

# Public AI4I base rows use UDI 1..10000; archived telemetry must stay outside that band.
AI4I_BASE_UDI_MAX = 10_000
DAILY_UDI_OFFSET = 10_000_000

# Telemetry sensor_code -> AI4I feature column
_SENSOR_TO_COLUMN: dict[str, str] = {
    "air_temperature": "Air temperature [K]",
    "process_temperature": "Process temperature [K]",
    "rotational_speed": "Rotational speed [rpm]",
    "torque": "Torque [Nm]",
    "tool_wear": "Tool wear [min]",
}

_DEFAULT_FEATURE_VALUES: dict[str, float] = {
    "Air temperature [K]": 298.1,
    "Process temperature [K]": 308.6,
    "Rotational speed [rpm]": 1500.0,
    "Torque [Nm]": 40.0,
    "Tool wear [min]": 0.0,
}

# degrading: only explicit high-wear / over-temperature thresholds (not soft heuristics)
_DEGRADE_TOOL_WEAR_FAIL = 200.0
_DEGRADE_PROCESS_TEMP_FAIL = 330.0
_SUDDEN_FAULT_STATUS = "sudden_fault"


def project_telemetry_to_ai4i_row(
    payload: TelemetryPayloadIn,
    *,
    mode: str = "normal",
    recorded_at: datetime | None = None,
) -> dict[str, str]:
    """Project a device telemetry payload into one AI4I CSV row (all string values)."""
    ts = recorded_at or payload.recorded_at or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    machine_type = map_device_profile_type(payload.device_code)
    product_id = stable_product_id(payload.device_code, machine_type)
    udi = stable_udi(payload.device_code, ts)

    values = dict(_DEFAULT_FEATURE_VALUES)
    statuses: list[str] = []
    for reading in payload.readings:
        column = _SENSOR_TO_COLUMN.get(reading.sensor_code)
        if column is not None:
            values[column] = float(reading.value)
        statuses.append((reading.status or "good").strip().lower())

    failure_flags = _map_failure_labels(mode=mode, values=values, statuses=statuses)

    row = {
        "UDI": str(udi),
        "Product ID": product_id,
        "Type": machine_type,
        "Air temperature [K]": _fmt_number(values["Air temperature [K]"]),
        "Process temperature [K]": _fmt_number(values["Process temperature [K]"]),
        "Rotational speed [rpm]": _fmt_number(values["Rotational speed [rpm]"], digits=0),
        "Torque [Nm]": _fmt_number(values["Torque [Nm]"]),
        "Tool wear [min]": _fmt_number(values["Tool wear [min]"], digits=0),
        "Machine failure": failure_flags["Machine failure"],
        "TWF": failure_flags["TWF"],
        "HDF": failure_flags["HDF"],
        "PWF": failure_flags["PWF"],
        "OSF": failure_flags["OSF"],
        "RNF": failure_flags["RNF"],
    }
    validate_ai4i_row(row)
    return row


def map_device_profile_type(device_code: str) -> str:
    """Map a device code to AI4I quality class L / M / H (stable per device)."""
    cleaned = device_code.strip().upper()
    if re.match(r"^[LMH]\d+$", cleaned):
        return cleaned[:1]

    digest = hashlib.sha256(device_code.strip().encode("utf-8")).digest()
    # Prefer L (low quality / higher failure rate in AI4I), then M, then H — stable 50/30/20
    bucket = digest[0] % 10
    if bucket < 5:
        return "L"
    if bucket < 8:
        return "M"
    return "H"


def stable_product_id(device_code: str, machine_type: str | None = None) -> str:
    """Stable Product ID aligned with Type prefix, derived from device_code."""
    cleaned = device_code.strip()
    upper = cleaned.upper()
    if re.match(r"^[LMH]\d+$", upper):
        return upper

    machine_type = machine_type or map_device_profile_type(device_code)
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    numeric = int(digest[:8], 16) % 90_000 + 10_000
    return f"{machine_type}{numeric}"


def stable_udi(device_code: str, recorded_at: datetime) -> int:
    """Deterministic daily UDI outside AI4I base band 1..10000."""
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
    key = f"{device_code.strip()}|{recorded_at.astimezone(timezone.utc).isoformat()}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    # Always >= DAILY_UDI_OFFSET so base+daily UDI dedupe cannot collide with 1..10000.
    return DAILY_UDI_OFFSET + (int(digest[:8], 16) % 1_000_000_000)


def validate_ai4i_row(row: Mapping[str, object]) -> None:
    missing = [name for name in AI4I_REQUIRED_FIELDS if name not in row or row[name] in (None, "")]
    if missing:
        raise ValueError(f"AI4I 行缺少必填字段：{', '.join(missing)}")
    try:
        int(str(row["UDI"]))
        float(str(row["Air temperature [K]"]))
        float(str(row["Process temperature [K]"]))
        float(str(row["Rotational speed [rpm]"]))
        float(str(row["Torque [Nm]"]))
        float(str(row["Tool wear [min]"]))
        int(str(row["Machine failure"]))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"AI4I 行字段类型无效：{exc}") from exc
    if str(row.get("Type", "")).strip().upper() not in {"L", "M", "H"}:
        raise ValueError("AI4I Type 必须是 L/M/H")


def _map_failure_labels(
    *,
    mode: str,
    values: dict[str, float],
    statuses: list[str],
) -> dict[str, str]:
    """Map simulation modes onto Machine failure with conservative labels."""
    normalized_mode = (mode or "normal").strip().lower()
    flags = {
        "Machine failure": "0",
        "TWF": "0",
        "HDF": "0",
        "PWF": "0",
        "OSF": "0",
        "RNF": "0",
    }

    # normal / data-quality modes never contribute machine-failure labels
    if normalized_mode in {"normal", "sensor_stuck", "sensor_drift"}:
        return flags

    if normalized_mode == "sudden_fault":
        # Only after the simulator marks a real sudden fault on raw_status.
        # fault_emerging (pre-fault window) stays unlabeled.
        if any(status == _SUDDEN_FAULT_STATUS for status in statuses):
            flags["Machine failure"] = "1"
            torque = values["Torque [Nm]"]
            speed = values["Rotational speed [rpm]"]
            if torque >= 55 or speed <= 1200:
                flags["PWF"] = "1"
            else:
                flags["OSF"] = "1"
        return flags

    if normalized_mode == "degrading":
        tool_wear = values["Tool wear [min]"]
        process_temp = values["Process temperature [K]"]
        failed = False
        if tool_wear >= _DEGRADE_TOOL_WEAR_FAIL:
            flags["TWF"] = "1"
            failed = True
        if process_temp >= _DEGRADE_PROCESS_TEMP_FAIL:
            flags["HDF"] = "1"
            failed = True
        if failed:
            flags["Machine failure"] = "1"
        return flags

    # Unknown modes stay unlabeled (do not invent failures).
    return flags


def _fmt_number(value: float, *, digits: int = 1) -> str:
    if digits == 0:
        return str(int(round(float(value))))
    return f"{float(value):.{digits}f}".rstrip("0").rstrip(".") if digits > 0 else str(value)
