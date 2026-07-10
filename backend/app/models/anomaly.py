from dataclasses import dataclass

from app.schemas.timeseries import TimeSeriesWindow


@dataclass(frozen=True)
class AnomalyDetectionResult:
    anomaly_score: float
    is_anomaly: bool
    threshold: float
    reasons: list[str]


def detect_anomaly(window: TimeSeriesWindow, *, threshold: float = 0.65) -> AnomalyDetectionResult:
    features = window.feature_values
    peak_score = _clip01(abs(features.get("peak", features.get("max", 0.0))) / 4)
    trend_score = _clip01(abs(features.get("trend", 0.0)) / 2)
    volatility_score = _clip01(features.get("rolling_std_last_3", features.get("std", 0.0)) / 2)
    quality_penalty = _clip01(1 - features.get("quality_mean", 1.0))

    score = _clip01(
        peak_score * 0.4
        + trend_score * 0.3
        + volatility_score * 0.2
        + quality_penalty * 0.1
    )

    reasons = []
    if peak_score >= 0.7:
        reasons.append("peak")
    if trend_score >= 0.5:
        reasons.append("trend")
    if volatility_score >= 0.5:
        reasons.append("volatility")
    if quality_penalty >= 0.2:
        reasons.append("quality")

    if len(reasons) >= 3:
        score = _clip01(score + 0.08)

    return AnomalyDetectionResult(
        anomaly_score=score,
        is_anomaly=score >= threshold,
        threshold=threshold,
        reasons=reasons,
    )


def _clip01(value: float) -> float:
    return min(max(value, 0.0), 1.0)