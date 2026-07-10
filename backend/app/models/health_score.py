from app.models.risk_rules import evaluate_risk_level


def calculate_health_score(
    *,
    failure_probability: float,
    anomaly_score: float,
    trend_factor: float,
    quality_score: float,
) -> float:
    risk_penalty = _clip01(failure_probability) * 45
    anomaly_penalty = _clip01(anomaly_score) * 30
    trend_penalty = _clip01(abs(trend_factor)) * 15
    quality_penalty = _clip01(1 - quality_score) * 10
    score = 100 - risk_penalty - anomaly_penalty - trend_penalty - quality_penalty
    return round(max(score, 0), 2)


def risk_level_from_score(
    health_score: float,
    failure_probability: float,
    anomaly_score: float,
) -> str:
    return evaluate_risk_level(
        failure_probability=max(failure_probability, anomaly_score),
        health_score=health_score,
    )


def _clip01(value: float) -> float:
    return min(max(value, 0.0), 1.0)