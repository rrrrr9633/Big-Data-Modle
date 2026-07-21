from __future__ import annotations

import logging
import threading
from typing import Annotated, Any

from app.core.database import SessionLocal, get_db
from app.models.registry import (
    ActiveModelState,
    delete_active_model_artifacts,
    get_active_model_state,
)
from app.repositories.maintenance_repository import (
    fetch_model_versions,
    insert_audit_log,
    reset_training_records,
)
from app.repositories.model_training_repository import (
    create_training_job,
    fetch_training_job,
    fetch_training_jobs,
    mark_training_job_failed,
    mark_training_job_running,
    mark_training_job_succeeded,
    present_training_job,
)
from app.security.auth import CurrentUser
from app.security.policies import require_permission
from app.services.model_training import retrain_ai4i_from_archive
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter()
logger = logging.getLogger(__name__)
DbSession = Annotated[Session, Depends(get_db)]
ModelActivateUser = Annotated[CurrentUser, Depends(require_permission("model.activate"))]
ModelTrainUser = Annotated[CurrentUser, Depends(require_permission("model.train"))]


@router.get("/active")
def get_active_model() -> ActiveModelState:
    return get_active_model_state()


@router.get("")
def list_model_versions(db: DbSession) -> list[dict[str, Any]]:
    return fetch_model_versions(db)


@router.post("/retrain")
def start_model_retrain(db: DbSession, user: ModelTrainUser) -> dict[str, Any]:
    job_id = create_training_job(
        db,
        created_by=user.username,
        detail={"trigger": "api", "source": "base_plus_daily_archive", "type": "ai4i_retrain"},
    )
    version = f"retrain-{job_id}"
    insert_audit_log(
        db,
        actor=user.username,
        role=user.role,
        action="start_model_retrain",
        resource=f"model:training-job:{job_id}",
        detail={"job_id": job_id, "version": version, "type": "ai4i_retrain"},
    )
    db.commit()

    thread = threading.Thread(
        target=_run_retrain_job,
        name=f"model-retrain-{job_id}",
        args=(job_id, version, user.username),
        daemon=True,
    )
    thread.start()

    accepted = present_training_job(
        {
            "id": job_id,
            "status": "accepted",
            "version": version,
            "trained_rows": None,
            "error_message": None,
            "metrics_json": None,
            "detail_json": {"trigger": "api", "source": "base_plus_daily_archive", "type": "ai4i_retrain"},
            "created_by": user.username,
            "created_at": None,
            "started_at": None,
            "finished_at": None,
        }
    )
    assert accepted is not None
    accepted["job_id"] = job_id
    return accepted


@router.get("/training-jobs")
def list_training_jobs(db: DbSession, limit: int = 50) -> list[dict[str, Any]]:
    return [job for row in fetch_training_jobs(db, limit=limit) if (job := present_training_job(row))]


@router.get("/training-jobs/{job_id}")
def get_training_job(job_id: int, db: DbSession) -> dict[str, Any]:
    job = present_training_job(fetch_training_job(db, job_id))
    if job is None:
        raise HTTPException(status_code=404, detail=f"训练任务不存在：{job_id}")
    return job


@router.delete("/active")
def reset_active_model(db: DbSession, user: ModelActivateUser) -> dict[str, object]:
    deleted_records = reset_training_records(db)
    deleted_artifacts = delete_active_model_artifacts()
    insert_audit_log(
        db,
        actor=user.username,
        role=user.role,
        action="reset_active_model",
        resource="model:active",
        detail={"deleted_records": deleted_records, **deleted_artifacts},
    )
    db.commit()
    return {
        "status": "reset",
        "deleted_records": deleted_records,
        **deleted_artifacts,
    }


def _run_retrain_job(job_id: int, version: str, created_by: str) -> None:
    with SessionLocal() as db:
        try:
            mark_training_job_running(db, job_id, version=version)
            result = retrain_ai4i_from_archive(db, version=version)
            metrics = [
                {
                    "model_name": metric.model_name,
                    "model_type": metric.model_type,
                    "version": metric.version,
                    "metric_name": metric.metric_name,
                    "metric_value": metric.metric_value,
                }
                for metric in result.suite.metrics
            ]
            mark_training_job_succeeded(
                db,
                job_id,
                version=version,
                trained_rows=result.trained_rows,
                metrics=metrics,
                detail={
                    "type": "ai4i_retrain",
                    "created_by": created_by,
                    "source_files": result.source_files or [],
                },
            )
            insert_audit_log(
                db,
                actor=created_by,
                role="system",
                action="complete_model_retrain",
                resource=f"model:training-job:{job_id}",
                detail={
                    "job_id": job_id,
                    "version": version,
                    "trained_rows": result.trained_rows,
                    "type": "ai4i_retrain",
                },
            )
            db.commit()
        except Exception as exc:
            logger.exception("Model retrain job %s failed", job_id)
            try:
                # Clear a failed transaction so mark_failed can commit.
                db.rollback()
                mark_training_job_failed(db, job_id, error_message=str(exc))
            except Exception:
                logger.exception("Failed to mark training job %s as failed", job_id)
