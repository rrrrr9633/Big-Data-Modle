from app.models.anomaly import detect_anomaly
from app.models.health_score import calculate_health_score, risk_level_from_score
from app.schemas.timeseries import PredictionResult, TimeSeriesWindow


def predict_device_risk(window: TimeSeriesWindow) -> PredictionResult:
    features = window.feature_values
    probability = _estimate_failure_probability(features)
    anomaly = detect_anomaly(window)
    trend_factor = abs(features.get("trend", 0.0)) / 2
    quality_score = features.get("quality_mean", 1.0)
    health_score = calculate_health_score(
        failure_probability=probability,
        anomaly_score=anomaly.anomaly_score,
        trend_factor=trend_factor,
        quality_score=quality_score,
    )
    risk_level = risk_level_from_score(health_score, probability, anomaly.anomaly_score)

    return PredictionResult(
        device_id=window.device_id,
        failure_probability=probability,
        health_score=health_score,
        risk_level=risk_level,
        anomaly_score=anomaly.anomaly_score,
        anomaly_reasons=anomaly.reasons,
        trend_factor=trend_factor,
        quality_score=quality_score,
        rul_hours=None,
    )


def _estimate_failure_probability(features: dict[str, float]) -> float:
    mean_pressure = abs(features.get("mean", 0.0)) / 3
    peak_pressure = abs(features.get("peak", features.get("max", 0.0))) / 5
    trend_pressure = abs(features.get("trend", 0.0)) / 3
    quality_penalty = 1 - features.get("quality_mean", 1.0)
    probability = (
        mean_pressure * 0.35 + peak_pressure * 0.25 + trend_pressure * 0.25 + quality_penalty * 0.15
    )
    return min(max(probability, 0.0), 1.0)
