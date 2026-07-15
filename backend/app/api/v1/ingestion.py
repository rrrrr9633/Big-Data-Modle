import csv
import logging
from io import StringIO
from typing import Annotated

from app.core.database import get_db
from app.ingestion.ai4i import ai4i_feature_values, transform_ai4i_row
from app.models.model_suite import (
    Ai4iModelSuite,
    explain_ai4i_feature_row,
    model_suite_version,
    predict_ai4i_feature_row,
)
from app.repositories.maintenance_repository import (
    create_import_batch,
    insert_audit_log,
    insert_feature_window,
    insert_prediction,
    insert_prediction_explanations,
    insert_sensor_reading,
    insert_warning,
    upsert_device,
)
from app.security.auth import CurrentUser
from app.security.policies import require_permission
from app.services.maintenance import generate_maintenance_advice
from app.services.model_training import train_and_register_ai4i_model
from app.tsdb.telemetry_repository import (
    insert_device_status_event,
    insert_feature_window_event,
    insert_prediction_metric,
    insert_sensor_reading_timeseries,
)
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

router = APIRouter()
logger = logging.getLogger(__name__)
DbSession = Annotated[Session, Depends(get_db)]
ModelTrainUser = Annotated[CurrentUser, Depends(require_permission("model.train"))]
CsvFile = Annotated[UploadFile, File(...)]
ReplayDemoData = Annotated[bool, Form()]


@router.post("/ai4i")
async def import_ai4i_csv(
    file: CsvFile,
    db: DbSession,
    user: ModelTrainUser,
    replay_demo_data: ReplayDemoData = False,
) -> dict[str, bool | int | str]:
    content = (await file.read()).decode("utf-8-sig")
    rows = list(csv.DictReader(StringIO(content)))
    batch_id = create_import_batch(db, file.filename or "AI4I CSV", len(rows))
    prediction_count = 0
    warning_count = 0

    training = train_and_register_ai4i_model(db, rows)
    model_suite = training.suite

    if replay_demo_data:
        prediction_count, warning_count = _replay_ai4i_rows(db, rows, batch_id, model_suite)

    insert_audit_log(
        db,
        actor=user.username,
        role=user.role,
        action="train_ai4i_model",
        resource=f"model:active:{model_suite_version(model_suite)}",
        detail={
            "filename": file.filename,
            "row_count": len(rows),
            "replay_demo_data": replay_demo_data,
            "prediction_count": prediction_count,
            "warning_count": warning_count,
        },
    )
    db.commit()
    return {
        "status": "completed",
        "mode": "train_and_replay" if replay_demo_data else "train_only",
        "batch_id": batch_id,
        "imported_rows": len(rows),
        "trained_rows": len(rows),
        "replay_enabled": replay_demo_data,
        "prediction_count": prediction_count,
        "warning_count": warning_count,
    }


def _replay_ai4i_rows(
    db: Session,
    rows: list[dict[str, str]],
    batch_id: int,
    model_suite: Ai4iModelSuite,
) -> tuple[int, int]:
    prediction_count = 0
    warning_count = 0
    model_version = model_suite_version(model_suite)
    for row in rows:
        sample = transform_ai4i_row(row)
        feature_values = ai4i_feature_values(row)
        result = predict_ai4i_feature_row(
            device_id=sample.device_code,
            feature_values=feature_values,
            suite=model_suite,
            forced_failure=sample.failed,
        )
        device_status = "fault" if sample.failed else "online"
        upsert_device(
            db,
            device_code=sample.device_code,
            device_name=sample.device_name,
            device_type=sample.device_type,
            status=device_status,
        )
        _mirror_device_status_to_tsdb(
            device_code=sample.device_code,
            status=device_status,
            time=sample.readings[-1].timestamp,
            reason="ai4i_replay_failure_label" if sample.failed else "ai4i_replay_normal_label",
            source="ai4i_replay",
        )
        for reading in sample.readings:
            reading_value = reading.value or 0.0
            insert_sensor_reading(
                db,
                device_code=sample.device_code,
                sensor_code=reading.sensor_code,
                recorded_at=reading.timestamp,
                value=reading_value,
                unit=reading.unit,
                batch_id=batch_id,
            )
            _mirror_sensor_reading_to_tsdb(
                device_code=sample.device_code,
                sensor_code=reading.sensor_code,
                recorded_at=reading.timestamp,
                value=reading_value,
                unit=reading.unit,
                event_id=f"ai4i:{batch_id}:{sample.device_code}:{reading.sensor_code}:{reading.timestamp.isoformat()}",
            )
        window_feature_values = {
            "mean": feature_values["Air temperature [K]"],
            "std": 0.0,
            "max": feature_values["Process temperature [K]"],
            "min": feature_values["Tool wear [min]"],
            "trend": 0.0,
        }
        feature_window_id = insert_feature_window(
            db,
            device_code=sample.device_code,
            start_time=sample.readings[0].timestamp,
            end_time=sample.readings[-1].timestamp,
            feature_values=window_feature_values,
        )
        _mirror_feature_window_to_tsdb(
            event_id=f"ai4i-window:{batch_id}:{sample.device_code}:{sample.readings[-1].timestamp.isoformat()}",
            device_code=sample.device_code,
            start_time=sample.readings[0].timestamp,
            end_time=sample.readings[-1].timestamp,
            feature_values=window_feature_values,
            source="ai4i_replay",
        )
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
            created_at=sample.readings[-1].timestamp,
        )
        explanations = explain_ai4i_feature_row(
            feature_values=feature_values,
            suite=model_suite,
        )[:5]
        insert_prediction_explanations(
            db,
            prediction_id=prediction_id,
            device_code=result.device_id,
            explanations=explanations,
        )
        prediction_count += 1
        if result.risk_level in {"medium", "high", "critical"}:
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
            warning_count += 1
    return prediction_count, warning_count


def _mirror_sensor_reading_to_tsdb(
    *,
    device_code: str,
    sensor_code: str,
    recorded_at,
    value: float,
    unit: str | None,
    event_id: str,
) -> None:
    try:
        insert_sensor_reading_timeseries(
            device_code=device_code,
            sensor_code=sensor_code,
            recorded_at=recorded_at,
            value=value,
            unit=unit,
            event_id=event_id,
            gateway_id="ai4i-import",
            source_topic="ai4i_replay",
        )
    except Exception as exc:
        logger.warning("AI4I sensor reading TSDB mirror skipped: %s", exc)


def _mirror_feature_window_to_tsdb(
    *,
    event_id: str,
    device_code: str,
    start_time,
    end_time,
    feature_values: dict[str, float],
    source: str,
) -> None:
    try:
        insert_feature_window_event(
            event_id=event_id,
            device_code=device_code,
            start_time=start_time,
            end_time=end_time,
            feature_values=feature_values,
            source=source,
        )
    except Exception as exc:
        logger.warning("AI4I feature window TSDB mirror skipped: %s", exc)


def _mirror_prediction_metric_to_tsdb(
    *,
    prediction_id: int,
    feature_window_id: int,
    model_version: str,
    result,
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
        logger.warning("AI4I prediction metric TSDB mirror skipped: %s", exc)


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
        logger.warning("AI4I device status TSDB mirror skipped: %s", exc)
