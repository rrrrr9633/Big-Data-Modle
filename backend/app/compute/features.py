from statistics import mean, pstdev, pvariance

from app.schemas.timeseries import GovernedReading, TimeSeriesWindow


def build_feature_window(readings: list[GovernedReading]) -> TimeSeriesWindow | None:
    if not readings:
        return None

    ordered = sorted(readings, key=lambda item: item.timestamp)
    values = [item.value for item in ordered]
    normalized_values = [item.normalized_value for item in ordered]
    quality_scores = [item.quality_score for item in ordered]
    rolling_tail = normalized_values[-3:]

    latest_by_sensor = {item.sensor_code: item.value for item in ordered}

    return TimeSeriesWindow(
        device_id=ordered[0].device_id,
        start_time=ordered[0].timestamp,
        end_time=ordered[-1].timestamp,
        feature_values={
            "mean": mean(normalized_values),
            "variance": pvariance(normalized_values) if len(normalized_values) > 1 else 0.0,
            "std": pstdev(normalized_values) if len(normalized_values) > 1 else 0.0,
            "peak": max(normalized_values),
            "max": max(normalized_values),
            "min": min(normalized_values),
            "trend": normalized_values[-1] - normalized_values[0]
            if len(normalized_values) > 1
            else 0.0,
            "raw_mean": mean(values),
            "raw_max": max(values),
            "raw_min": min(values),
            "quality_mean": mean(quality_scores),
            "rolling_mean_last_3": mean(rolling_tail),
            "rolling_std_last_3": pstdev(rolling_tail) if len(rolling_tail) > 1 else 0.0,
            **{
                f"sensor_latest_{sensor_code}": value
                for sensor_code, value in latest_by_sensor.items()
            },
        },
    )