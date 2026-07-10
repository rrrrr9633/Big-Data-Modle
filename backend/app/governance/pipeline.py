from collections import defaultdict
from statistics import mean, median, pstdev

from app.schemas.timeseries import GovernedReading, GovernedReadingWindow, SensorReading


def govern_readings(
    readings: list[SensorReading],
    *,
    outlier_z_score: float = 3.0,
) -> list[GovernedReading]:
    if not readings:
        return []

    ordered = sorted(
        readings,
        key=lambda item: (item.device_id, item.sensor_code, item.timestamp),
    )
    filled = _fill_missing_values(ordered)
    clipped = _clip_outliers(filled, outlier_z_score=outlier_z_score)
    return _standardize(clipped)


def standardize_readings(readings: list[SensorReading]) -> list[GovernedReading]:
    return govern_readings(readings)


def build_sliding_windows(
    readings: list[GovernedReading],
    *,
    window_size: int,
    step_size: int,
) -> list[GovernedReadingWindow]:
    grouped: dict[tuple[str, str], list[GovernedReading]] = defaultdict(list)
    ordered = sorted(
        readings,
        key=lambda item: (item.device_id, item.sensor_code, item.timestamp),
    )
    for reading in ordered:
        grouped[(reading.device_id, reading.sensor_code)].append(reading)

    windows: list[GovernedReadingWindow] = []
    for (device_id, sensor_code), group in grouped.items():
        for start in range(0, len(group) - window_size + 1, step_size):
            chunk = group[start : start + window_size]
            windows.append(
                GovernedReadingWindow(
                    device_id=device_id,
                    sensor_code=sensor_code,
                    start_time=chunk[0].timestamp,
                    end_time=chunk[-1].timestamp,
                    readings=chunk,
                )
            )
    return windows


def _fill_missing_values(readings: list[SensorReading]) -> list[tuple[SensorReading, float, float]]:
    grouped_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    for reading in readings:
        if reading.value is not None:
            grouped_values[(reading.device_id, reading.sensor_code)].append(reading.value)

    present_values = [reading.value for reading in readings if reading.value is not None]
    global_fallback = mean(present_values or [0.0])
    group_fallback = {
        key: mean(values) if values else global_fallback for key, values in grouped_values.items()
    }

    filled: list[tuple[SensorReading, float, float]] = []
    previous_by_group: dict[tuple[str, str], float] = {}
    for reading in readings:
        key = (reading.device_id, reading.sensor_code)
        if reading.value is None:
            value = previous_by_group.get(key, group_fallback.get(key, global_fallback))
            quality = 0.8
        else:
            value = reading.value
            quality = 1.0
        previous_by_group[key] = value
        filled.append((reading, value, quality))
    return filled


def _clip_outliers(
    readings: list[tuple[SensorReading, float, float]],
    *,
    outlier_z_score: float,
) -> list[tuple[SensorReading, float, float]]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for reading, value, _quality in readings:
        grouped[(reading.device_id, reading.sensor_code)].append(value)

    stats = {
        key: (
            mean(values),
            median(values),
            pstdev(values) if len(values) > 1 else 0.0,
        )
        for key, values in grouped.items()
    }

    result: list[tuple[SensorReading, float, float]] = []
    for reading, value, quality in readings:
        avg, center, std = stats[(reading.device_id, reading.sensor_code)]
        if std and abs(value - avg) / std > outlier_z_score:
            value = center
            quality = min(quality, 0.6)
        result.append((reading, value, quality))
    return result


def _standardize(readings: list[tuple[SensorReading, float, float]]) -> list[GovernedReading]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for reading, value, _quality in readings:
        grouped[(reading.device_id, reading.sensor_code)].append(value)

    stats = {
        key: (mean(values), pstdev(values) if len(values) > 1 else 1.0)
        for key, values in grouped.items()
    }

    governed: list[GovernedReading] = []
    for reading, value, quality in readings:
        avg, std = stats[(reading.device_id, reading.sensor_code)]
        governed.append(
            GovernedReading(
                **reading.model_dump(exclude={"value"}),
                value=value,
                normalized_value=(value - avg) / (std or 1.0),
                quality_score=quality,
            )
        )
    return governed
