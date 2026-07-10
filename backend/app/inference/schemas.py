from __future__ import annotations

from dataclasses import dataclass

from app.features.schemas import WindowFeatureEvent
from app.models.model_suite import RiskExplanation
from app.schemas.timeseries import PredictionResult


@dataclass(frozen=True)
class AsyncInferenceOutput:
    prediction_id: int
    feature_window_id: int
    model_version: str
    result: PredictionResult
    explanations: list[RiskExplanation]
    warning_created: bool
    source_event: WindowFeatureEvent


def serialize_prediction_event(output: AsyncInferenceOutput) -> dict[str, object]:
    return {
        "prediction_id": output.prediction_id,
        "feature_window_id": output.feature_window_id,
        "model_version": output.model_version,
        "device_code": output.result.device_id,
        "failure_probability": output.result.failure_probability,
        "health_score": output.result.health_score,
        "risk_level": output.result.risk_level,
        "anomaly_score": output.result.anomaly_score,
        "anomaly_reasons": output.result.anomaly_reasons,
        "trend_factor": output.result.trend_factor,
        "quality_score": output.result.quality_score,
        "rul_hours": output.result.rul_hours,
        "source_feature_event_id": output.source_event.event_id,
    }


def serialize_warning_event(output: AsyncInferenceOutput) -> dict[str, object]:
    return {
        "prediction_id": output.prediction_id,
        "feature_window_id": output.feature_window_id,
        "model_version": output.model_version,
        "device_code": output.result.device_id,
        "risk_level": output.result.risk_level,
        "failure_probability": output.result.failure_probability,
        "health_score": output.result.health_score,
        "source_feature_event_id": output.source_event.event_id,
    }
