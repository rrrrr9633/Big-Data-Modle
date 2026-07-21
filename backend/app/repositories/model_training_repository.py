"""Persistence helpers for asynchronous AI4I retrain jobs."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

_SCHEMA_READY = False

# Planned columns — do not silently adapt mismatched legacy tables.
_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "id",
        "status",
        "version",
        "trained_rows",
        "error_message",
        "metrics_json",
        "detail_json",
        "created_by",
        "created_at",
        "started_at",
        "finished_at",
    }
)


def ensure_model_training_jobs_schema(db: Session) -> None:
    """Create planned table if missing; fail if an existing table lacks planned columns."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS model_training_jobs (
              id BIGINT PRIMARY KEY AUTO_INCREMENT,
              status VARCHAR(32) NOT NULL DEFAULT 'pending',
              version VARCHAR(64) NULL,
              trained_rows INT NULL,
              error_message TEXT NULL,
              metrics_json JSON NULL,
              detail_json JSON NULL,
              created_by VARCHAR(64) NULL,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              started_at TIMESTAMP NULL,
              finished_at TIMESTAMP NULL,
              INDEX idx_model_training_jobs_status_time (status, created_at)
            )
            """
        )
    )
    _assert_planned_columns(db)
    db.commit()
    _SCHEMA_READY = True


def _assert_planned_columns(db: Session) -> None:
    rows = db.execute(
        text(
            """
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'model_training_jobs'
            """
        )
    ).fetchall()
    if not rows:
        # SQLite / non-MySQL test paths: fall back to a lightweight probe.
        try:
            db.execute(
                text(
                    """
                    SELECT
                      id, status, version, trained_rows, error_message,
                      metrics_json, detail_json, created_by,
                      created_at, started_at, finished_at
                    FROM model_training_jobs
                    LIMIT 0
                    """
                )
            )
            return
        except Exception as exc:
            raise RuntimeError(
                "model_training_jobs 表缺少计划字段，拒绝静默适配错误旧表"
            ) from exc

    present = {str(row[0]).lower() for row in rows}
    missing = sorted(name for name in _REQUIRED_COLUMNS if name not in present)
    if missing:
        raise RuntimeError(
            "model_training_jobs 表缺少计划字段，拒绝静默适配错误旧表："
            + ", ".join(missing)
        )


def create_training_job(
    db: Session,
    *,
    created_by: str | None = None,
    detail: dict[str, Any] | None = None,
) -> int:
    ensure_model_training_jobs_schema(db)
    result = db.execute(
        text(
            """
            INSERT INTO model_training_jobs (
              status,
              created_by,
              detail_json
            )
            VALUES (
              'pending',
              :created_by,
              :detail_json
            )
            """
        ),
        {
            "created_by": created_by,
            "detail_json": json.dumps(detail or {}, ensure_ascii=False),
        },
    )
    job_id = int(result.lastrowid or 0)
    db.commit()
    return job_id


def mark_training_job_running(db: Session, job_id: int, *, version: str) -> None:
    ensure_model_training_jobs_schema(db)
    db.execute(
        text(
            """
            UPDATE model_training_jobs
            SET
              status = 'running',
              version = :version,
              started_at = CURRENT_TIMESTAMP,
              error_message = NULL
            WHERE id = :job_id
            """
        ),
        {"job_id": job_id, "version": version},
    )
    db.commit()


def mark_training_job_succeeded(
    db: Session,
    job_id: int,
    *,
    version: str,
    trained_rows: int,
    metrics: list[dict[str, Any]] | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    ensure_model_training_jobs_schema(db)
    db.execute(
        text(
            """
            UPDATE model_training_jobs
            SET
              status = 'succeeded',
              version = :version,
              trained_rows = :trained_rows,
              metrics_json = :metrics_json,
              detail_json = COALESCE(:detail_json, detail_json),
              finished_at = CURRENT_TIMESTAMP,
              error_message = NULL
            WHERE id = :job_id
            """
        ),
        {
            "job_id": job_id,
            "version": version,
            "trained_rows": trained_rows,
            "metrics_json": json.dumps(metrics or [], ensure_ascii=False),
            "detail_json": json.dumps(detail, ensure_ascii=False) if detail is not None else None,
        },
    )
    db.commit()


def mark_training_job_failed(db: Session, job_id: int, *, error_message: str) -> None:
    ensure_model_training_jobs_schema(db)
    db.execute(
        text(
            """
            UPDATE model_training_jobs
            SET
              status = 'failed',
              error_message = :error_message,
              finished_at = CURRENT_TIMESTAMP
            WHERE id = :job_id
            """
        ),
        {"job_id": job_id, "error_message": error_message[:4000]},
    )
    db.commit()


def fetch_training_job(db: Session, job_id: int) -> dict[str, Any] | None:
    ensure_model_training_jobs_schema(db)
    row = (
        db.execute(
            text(
                """
                SELECT
                  id,
                  status,
                  version,
                  trained_rows,
                  error_message,
                  metrics_json,
                  detail_json,
                  created_by,
                  created_at,
                  started_at,
                  finished_at
                FROM model_training_jobs
                WHERE id = :job_id
                """
            ),
            {"job_id": job_id},
        )
        .mappings()
        .first()
    )
    return _normalize_job(dict(row)) if row else None


def fetch_training_jobs(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    ensure_model_training_jobs_schema(db)
    result = db.execute(
        text(
            """
            SELECT
              id,
              status,
              version,
              trained_rows,
              error_message,
              metrics_json,
              detail_json,
              created_by,
              created_at,
              started_at,
              finished_at
            FROM model_training_jobs
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
            """
        ),
        {"limit": max(int(limit), 1)},
    )
    return [_normalize_job(dict(row)) for row in result.mappings()]


def present_training_job(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """Shape a DB job row for frontend consumption."""
    if row is None:
        return None
    status = str(row.get("status") or "pending")
    error_message = row.get("error_message")
    trained_rows = row.get("trained_rows")
    version = row.get("version")
    return {
        "id": row.get("id"),
        "type": "ai4i_retrain",
        "status": status,
        "version": version,
        "trained_rows": trained_rows,
        "message": _job_message(status=status, version=version, trained_rows=trained_rows, error_message=error_message),
        "error_message": error_message,
        "metrics": row.get("metrics") if row.get("metrics") is not None else row.get("metrics_json"),
        "detail": row.get("detail") if row.get("detail") is not None else row.get("detail_json"),
        "metrics_json": row.get("metrics_json"),
        "detail_json": row.get("detail_json"),
        "created_by": row.get("created_by"),
        "created_at": row.get("created_at"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
    }


def _job_message(
    *,
    status: str,
    version: str | None,
    trained_rows: int | None,
    error_message: str | None,
) -> str:
    if status == "pending":
        return "二次训练任务已创建，等待执行"
    if status == "running":
        return f"正在执行全量二次训练（版本 {version or 'pending'}）"
    if status == "succeeded":
        rows = trained_rows if trained_rows is not None else 0
        return f"二次训练完成：版本 {version or 'unknown'}，样本 {rows} 条"
    if status == "failed":
        return f"二次训练失败：{error_message or '未知错误'}"
    if status == "accepted":
        return f"二次训练任务已受理（版本 {version or 'pending'}）"
    return f"训练任务状态：{status}"


def _normalize_job(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("metrics_json", "detail_json"):
        value = row.get(key)
        if isinstance(value, str):
            try:
                row[key] = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"model_training_jobs.{key} 不是合法 JSON") from exc
    row["metrics"] = row.get("metrics_json")
    row["detail"] = row.get("detail_json")
    return row
