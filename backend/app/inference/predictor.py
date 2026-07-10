from __future__ import annotations

import logging

from app.core.database import SessionLocal
from app.features.schemas import WindowFeatureEvent
from app.inference.schemas import AsyncInferenceOutput
from app.models.model_suite import explain_prediction, model_suite_version, predict_with_model_suite
from app.models.registry import load_active_model_suite
from app.realtime.warning_suppression import should_create_warning
from app.repositories.maintenance_repository import (
    ensure_prediction_model_schema,
    insert_feature_window,
    insert_prediction,
    insert_prediction_explanations,
    insert_warning,
    upsert_device,
)
from app.schemas.timeseries import PredictionResult
from app.services.maintenance import generate_maintenance_advice
from app.tsdb.telemetry_repository import (
    insert_device_status_event,
    insert_feature_window_event,
    insert_prediction_metric,
)

logger = logging.getLogger(__name__)


def run_async_inference(feature_event: WindowFeatureEvent) -> AsyncInferenceOutput:
    db = SessionLocal()
    try:
        ensure_prediction_model_schema(db)
        model_suite = load_active_model_suite()
        window = feature_event.to_window()
        model_version = model_suite_version(model_suite)

        upsert_device(
            db,
            device_code=window.device_id,
            device_name=window.device_id,
            device_type="industrial-machine",
            status="online",
        )
        _mirror_device_status_to_tsdb(
            device_code=window.device_id,
            status="online",
            time=window.end_time,
            reason="async_inference_window_received",
            source=feature_event.source,
        )

        feature_window_id = insert_feature_window(
            db,
            device_code=window.device_id,
            start_time=window.start_time,
            end_time=window.end_time,
            feature_values=window.feature_values,
        )
        _mirror_feature_window_to_tsdb(feature_event)

        result = predict_with_model_suite(window, model_suite)
        prediction_id = insert_prediction(
            db,
            device_code=result.device_id,
            feature_window_id=feature_window_id,
            model_version=model_version,
            failure_probability=result.failure_probability,
            health_score=result.health_score,
            risk_level=result.risk_level,
            anomaly_score=result.anomaly_score,
            anomaly_reasons=result.anomaly_reasons,
            trend_factor=result.trend_factor,
            quality_score=result.quality_score,
            rul_hours=result.rul_hours,
        )
        _mirror_prediction_metric_to_tsdb(
            prediction_id=prediction_id,
            feature_window_id=feature_window_id,
            model_version=model_version,
            result=result,
            created_at=window.end_time,
        )

        explanations = explain_prediction(window, model_suite)[:5]
        insert_prediction_explanations(
            db,
            prediction_id=prediction_id,
            device_code=result.device_id,
            explanations=explanations,
        )

        warning_created = False
        if result.risk_level in {"medium", "high", "critical"} and should_create_warning(
            result.device_id,
            result.risk_level,
        ):
            advice = generate_maintenance_advice(result)
            insert_warning(
                db,
                prediction_id=prediction_id,
                feature_window_id=feature_window_id,
                model_version=model_version,
                device_code=advice.device_id,
                risk_level=advice.risk_level,
                failure_probability=result.failure_probability,
                health_score=result.health_score,
                title=advice.title,
                detail=advice.detail,
                suggested_action=advice.suggested_action,
                warning_explanation=[
                    {
                        "feature_name": item.feature_name,
                        "feature_value": item.feature_value,
                        "contribution": item.contribution,
                    }
                    for item in explanations
                ],
            )
            warning_created = True

        output = AsyncInferenceOutput(
            prediction_id=prediction_id,
            feature_window_id=feature_window_id,
            model_version=model_version,
            result=result,
            explanations=explanations,
            warning_created=warning_created,
            source_event=feature_event,
        )
        db.commit()
        return output
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _mirror_feature_window_to_tsdb(feature_event: WindowFeatureEvent) -> None:
    try:
        insert_feature_window_event(
            event_id=feature_event.event_id,
            device_code=feature_event.device_code,
            start_time=feature_event.start_time,
            end_time=feature_event.end_time,
            feature_values=feature_event.feature_values,
            source=feature_event.source,
        )
    except Exception as exc:
        logger.warning("Async feature window TSDB mirror skipped: %s", exc)


def _mirror_prediction_metric_to_tsdb(
    *,
    prediction_id: int,
    feature_window_id: int,
    model_version: str,
    result: PredictionResult,
    created_at,
) -> None:
    try:
        insert_prediction_metric(
            prediction_id=prediction_id,
            feature_window_id=feature_window_id,
            model_version=model_version,
            result=result,
            created_at=created_at,
        )
    except Exception as exc:
        logger.warning("Async prediction metric TSDB mirror skipped: %s", exc)


def _mirror_device_status_to_tsdb(
    *,
    device_code: str,
    status: str,
    time,
    reason: str,
    source: str,
) -> None:
    try:
        insert_device_status_event(
            device_code=device_code,
            status=status,
            time=time,
            reason=reason,
            source=source,
        )
    except Exception as exc:
        logger.warning("Async device status TSDB mirror skipped: %s", exc)
