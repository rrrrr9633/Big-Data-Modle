from datetime import UTC, datetime, timedelta

from app.compute.features import build_feature_window
from app.governance.pipeline import build_sliding_windows, govern_readings
from app.schemas.timeseries import SensorReading


def _reading(offset: int, value: float | None, device_id: str = "D001") -> SensorReading:
    return SensorReading(
        device_id=device_id,
        sensor_code="temperature",
        timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(minutes=offset),
        value=value,
        unit="℃",
    )


def test_govern_readings_fills_missing_values_and_clips_outliers() -> None:
    governed = govern_readings(
        [_reading(0, 10.0), _reading(1, None), _reading(2, 10_000.0)],
        outlier_z_score=1.0,
    )

    assert [item.value for item in governed] == [10.0, 10.0, 10.0]
    assert [item.quality_score for item in governed] == [1.0, 0.8, 0.6]
    assert [round(item.normalized_value, 2) for item in governed] == [0.0, 0.0, 0.0]


def test_build_sliding_windows_keeps_device_scope_and_step_size() -> None:
    readings = govern_readings(
        [
            _reading(0, 10.0),
            _reading(1, 11.0),
            _reading(2, 12.0),
            _reading(3, 13.0),
            _reading(0, 99.0, "D002"),
        ]
    )

    windows = build_sliding_windows(readings, window_size=3, step_size=1)

    assert [window.device_id for window in windows] == ["D001", "D001"]
    assert [[item.value for item in window.readings] for window in windows] == [
        [10.0, 11.0, 12.0],
        [11.0, 12.0, 13.0],
    ]


def test_feature_window_contains_core_and_rolling_statistics() -> None:
    governed = govern_readings([_reading(0, 10.0), _reading(1, 12.0), _reading(2, 14.0)])
    windows = build_sliding_windows(governed, window_size=3, step_size=1)

    feature_window = build_feature_window(windows[0].readings)

    assert feature_window is not None
    assert set(feature_window.feature_values) >= {
        "mean",
        "variance",
        "std",
        "peak",
        "min",
        "trend",
        "rolling_mean_last_3",
        "rolling_std_last_3",
    }
    assert feature_window.feature_values["trend"] > 0