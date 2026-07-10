from datetime import UTC, datetime

from app.models.anomaly import detect_anomaly
from app.models.health_score import calculate_health_score
from app.models.inference import predict_device_risk
from app.schemas.timeseries import TimeSeriesWindow
from app.services.maintenance import generate_maintenance_advice


def _window(**feature_values: float) -> TimeSeriesWindow:
    return TimeSeriesWindow(
        device_id="D001",
        start_time=datetime(2026, 1, 1, tzinfo=UTC),
        end_time=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        feature_values=feature_values,
    )


def test_detect_anomaly_scores_peak_trend_and_quality() -> None:
    result = detect_anomaly(_window(peak=3.5, trend=1.2, rolling_std_last_3=1.0, quality_mean=0.7))

    assert result.is_anomaly is True
    assert result.anomaly_score >= 0.7
    assert "peak" in result.reasons
    assert "quality" in result.reasons


def test_health_score_combines_risk_anomaly_trend_and_quality() -> None:
    score = calculate_health_score(
        failure_probability=0.7,
        anomaly_score=0.8,
        trend_factor=0.5,
        quality_score=0.75,
    )

    assert 0 <= score <= 100
    assert score < 40


def test_prediction_and_advice_include_anomaly_explanation() -> None:
    prediction = predict_device_risk(
        _window(mean=0.8, peak=3.5, trend=1.0, rolling_std_last_3=0.9, quality_mean=0.75)
    )
    advice = generate_maintenance_advice(prediction)

    assert prediction.anomaly_score > 0
    assert prediction.health_score < 100
    assert advice.risk_level in {"medium", "high", "critical"}
    assert "异常分数" in advice.detail
    assert "趋势" in advice.suggested_action or "异常" in advice.suggested_action
