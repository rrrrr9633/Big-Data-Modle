from __future__ import annotations

import json
import secrets
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def _rows(result: Any) -> list[dict[str, Any]]:
    rows = [dict(row) for row in result.mappings()]
    for row in rows:
        for key in (
            "metadata_json",
            "facts_json",
            "citations_json",
            "tool_calls_json",
            "findings_json",
            "metrics_json",
        ):
            if key in row and isinstance(row.get(key), str):
                try:
                    row[key] = json.loads(row[key])
                except json.JSONDecodeError:
                    pass
        if "metadata" not in row and "metadata_json" in row:
            row["metadata"] = row.get("metadata_json")
        if "facts" not in row and "facts_json" in row:
            row["facts"] = row.get("facts_json")
        if "citations" not in row and "citations_json" in row:
            row["citations"] = row.get("citations_json")
        if "findings" not in row and "findings_json" in row:
            row["findings"] = row.get("findings_json")
    return rows


def _json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def create_session(
    db: Session,
    *,
    session_key: str | None = None,
    title: str = "新会话",
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    key = session_key or secrets.token_hex(8)
    db.execute(
        text(
            """
            INSERT INTO agent_sessions (session_key, title, user_id, metadata_json, status)
            VALUES (:session_key, :title, :user_id, :metadata_json, 'active')
            """
        ),
        {
            "session_key": key,
            "title": title,
            "user_id": user_id,
            "metadata_json": _json_dumps(metadata or {}),
        },
    )
    session = get_session_by_key(db, key)
    assert session is not None
    return session


def get_session_by_key(db: Session, session_key: str) -> dict[str, Any] | None:
    rows = _rows(
        db.execute(
            text(
                """
                SELECT id, session_key, title, user_id, status, metadata_json,
                       created_at, updated_at
                FROM agent_sessions
                WHERE session_key = :session_key
                """
            ),
            {"session_key": session_key},
        )
    )
    return rows[0] if rows else None


def get_session_by_id(db: Session, session_id: int) -> dict[str, Any] | None:
    rows = _rows(
        db.execute(
            text(
                """
                SELECT id, session_key, title, user_id, status, metadata_json,
                       created_at, updated_at
                FROM agent_sessions
                WHERE id = :session_id
                """
            ),
            {"session_id": session_id},
        )
    )
    return rows[0] if rows else None


def get_or_create_session(
    db: Session,
    *,
    session_key: str | None = None,
    user_id: str | None = None,
    title: str = "新会话",
) -> dict[str, Any]:
    if session_key:
        existing = get_session_by_key(db, session_key)
        if existing is not None:
            return existing
    return create_session(db, session_key=session_key, user_id=user_id, title=title)


def list_sessions(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    return _rows(
        db.execute(
            text(
                """
                SELECT id, session_key, title, user_id, status, metadata_json,
                       created_at, updated_at
                FROM agent_sessions
                ORDER BY updated_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    )


def insert_message(
    db: Session,
    *,
    session_id: int,
    role: str,
    content: str,
    mode: str = "chat",
    status: str = "ok",
    facts: dict[str, Any] | None = None,
    citations: list[dict[str, Any]] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO agent_messages (
              session_id, role, content, mode, status,
              facts_json, citations_json, tool_calls_json
            )
            VALUES (
              :session_id, :role, :content, :mode, :status,
              :facts_json, :citations_json, :tool_calls_json
            )
            """
        ),
        {
            "session_id": session_id,
            "role": role,
            "content": content,
            "mode": mode,
            "status": status,
            "facts_json": _json_dumps(facts),
            "citations_json": _json_dumps(citations),
            "tool_calls_json": _json_dumps(tool_calls),
        },
    )
    db.execute(
        text(
            """
            UPDATE agent_sessions
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = :session_id
            """
        ),
        {"session_id": session_id},
    )
    return int(result.lastrowid or 0)


def fetch_messages(
    db: Session,
    *,
    session_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return _rows(
        db.execute(
            text(
                """
                SELECT id, session_id, role, content, mode, status,
                       facts_json, citations_json, tool_calls_json, created_at
                FROM agent_messages
                WHERE session_id = :session_id
                ORDER BY id ASC
                LIMIT :limit
                """
            ),
            {"session_id": session_id, "limit": limit},
        )
    )


def upsert_knowledge_document(
    db: Session,
    *,
    source_type: str,
    source_id: str,
    title: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    content_hash: str,
) -> int:
    db.execute(
        text(
            """
            INSERT INTO knowledge_documents (
              source_type, source_id, title, content, metadata_json, content_hash, synced_at
            )
            VALUES (
              :source_type, :source_id, :title, :content, :metadata_json, :content_hash, CURRENT_TIMESTAMP
            )
            ON DUPLICATE KEY UPDATE
              title = VALUES(title),
              content = VALUES(content),
              metadata_json = VALUES(metadata_json),
              content_hash = VALUES(content_hash),
              synced_at = CURRENT_TIMESTAMP
            """
        ),
        {
            "source_type": source_type,
            "source_id": source_id,
            "title": title,
            "content": content,
            "metadata_json": _json_dumps(metadata or {}),
            "content_hash": content_hash,
        },
    )
    row = (
        db.execute(
            text(
                """
                SELECT id FROM knowledge_documents
                WHERE source_type = :source_type AND source_id = :source_id
                """
            ),
            {"source_type": source_type, "source_id": source_id},
        )
        .mappings()
        .first()
    )
    return int(row["id"]) if row else 0


def replace_knowledge_chunks(
    db: Session,
    *,
    document_id: int,
    chunks: list[dict[str, Any]],
) -> None:
    db.execute(
        text("DELETE FROM knowledge_chunks WHERE document_id = :document_id"),
        {"document_id": document_id},
    )
    for chunk in chunks:
        db.execute(
            text(
                """
                INSERT INTO knowledge_chunks (
                  document_id, chunk_index, content, keywords, metadata_json
                )
                VALUES (
                  :document_id, :chunk_index, :content, :keywords, :metadata_json
                )
                """
            ),
            {
                "document_id": document_id,
                "chunk_index": int(chunk.get("chunk_index") or 0),
                "content": str(chunk.get("content") or ""),
                "keywords": chunk.get("keywords"),
                "metadata_json": _json_dumps(chunk.get("metadata") or {}),
            },
        )


def fetch_knowledge_chunks(db: Session, *, limit: int = 500) -> list[dict[str, Any]]:
    return _rows(
        db.execute(
            text(
                """
                SELECT
                  c.id,
                  c.document_id,
                  c.chunk_index,
                  c.content,
                  c.keywords,
                  c.metadata_json,
                  d.source_type,
                  d.source_id,
                  d.title
                FROM knowledge_chunks c
                JOIN knowledge_documents d ON d.id = c.document_id
                ORDER BY c.id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    )


def count_knowledge_documents(db: Session) -> int:
    row = db.execute(text("SELECT COUNT(*) AS total FROM knowledge_documents")).mappings().one()
    return int(row["total"] or 0)


def count_knowledge_chunks(db: Session) -> int:
    row = db.execute(text("SELECT COUNT(*) AS total FROM knowledge_chunks")).mappings().one()
    return int(row["total"] or 0)


def get_sync_cursor(db: Session, source_type: str) -> dict[str, Any]:
    rows = _rows(
        db.execute(
            text(
                """
                SELECT source_type, last_source_id, last_synced_at, total_synced, updated_at
                FROM knowledge_sync_cursors
                WHERE source_type = :source_type
                """
            ),
            {"source_type": source_type},
        )
    )
    if rows:
        return rows[0]
    db.execute(
        text(
            """
            INSERT INTO knowledge_sync_cursors (source_type, last_source_id, total_synced)
            VALUES (:source_type, 0, 0)
            """
        ),
        {"source_type": source_type},
    )
    return {
        "source_type": source_type,
        "last_source_id": 0,
        "last_synced_at": None,
        "total_synced": 0,
        "updated_at": None,
    }


def update_sync_cursor(
    db: Session,
    *,
    source_type: str,
    last_source_id: int,
    total_synced: int,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO knowledge_sync_cursors (
              source_type, last_source_id, last_synced_at, total_synced
            )
            VALUES (
              :source_type, :last_source_id, CURRENT_TIMESTAMP, :total_synced
            )
            ON DUPLICATE KEY UPDATE
              last_source_id = VALUES(last_source_id),
              last_synced_at = CURRENT_TIMESTAMP,
              total_synced = VALUES(total_synced)
            """
        ),
        {
            "source_type": source_type,
            "last_source_id": last_source_id,
            "total_synced": total_synced,
        },
    )


def get_inspection_schedule(
    db: Session,
    *,
    default_enabled: bool = False,
    default_minute: int = 0,
    default_device_limit: int = 50,
) -> dict[str, Any]:
    rows = _rows(
        db.execute(
            text(
                """
                SELECT id, schedule_key, enabled, minute_of_hour, device_limit,
                       last_triggered_at, last_run_id, updated_at, created_at
                FROM inspection_schedules
                WHERE schedule_key = 'default'
                """
            )
        )
    )
    if rows:
        return rows[0]
    db.execute(
        text(
            """
            INSERT INTO inspection_schedules (
              schedule_key, enabled, minute_of_hour, device_limit
            )
            VALUES ('default', :enabled, :minute_of_hour, :device_limit)
            """
        ),
        {
            "enabled": bool(default_enabled),
            "minute_of_hour": int(default_minute) % 60,
            "device_limit": int(default_device_limit),
        },
    )
    return get_inspection_schedule(
        db,
        default_enabled=default_enabled,
        default_minute=default_minute,
        default_device_limit=default_device_limit,
    )


def upsert_inspection_schedule(
    db: Session,
    *,
    enabled: bool,
    minute_of_hour: int,
    device_limit: int,
) -> dict[str, Any]:
    db.execute(
        text(
            """
            INSERT INTO inspection_schedules (
              schedule_key, enabled, minute_of_hour, device_limit
            )
            VALUES ('default', :enabled, :minute_of_hour, :device_limit)
            ON DUPLICATE KEY UPDATE
              enabled = VALUES(enabled),
              minute_of_hour = VALUES(minute_of_hour),
              device_limit = VALUES(device_limit)
            """
        ),
        {
            "enabled": enabled,
            "minute_of_hour": int(minute_of_hour) % 60,
            "device_limit": device_limit,
        },
    )
    return get_inspection_schedule(db)


def touch_inspection_schedule(db: Session, *, last_run_id: int) -> None:
    db.execute(
        text(
            """
            UPDATE inspection_schedules
            SET last_triggered_at = CURRENT_TIMESTAMP,
                last_run_id = :last_run_id
            WHERE schedule_key = 'default'
            """
        ),
        {"last_run_id": last_run_id},
    )


def create_inspection_run(
    db: Session,
    *,
    trigger_type: str,
    status: str = "running",
) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO inspection_runs (trigger_type, status)
            VALUES (:trigger_type, :status)
            """
        ),
        {"trigger_type": trigger_type, "status": status},
    )
    return int(result.lastrowid or 0)


def finish_inspection_run(
    db: Session,
    *,
    run_id: int,
    status: str,
    summary: str | None,
    device_total: int,
    issue_total: int,
    error_message: str | None,
) -> None:
    db.execute(
        text(
            """
            UPDATE inspection_runs
            SET status = :status,
                summary = :summary,
                device_total = :device_total,
                issue_total = :issue_total,
                error_message = :error_message,
                finished_at = CURRENT_TIMESTAMP
            WHERE id = :run_id
            """
        ),
        {
            "run_id": run_id,
            "status": status,
            "summary": summary,
            "device_total": device_total,
            "issue_total": issue_total,
            "error_message": error_message,
        },
    )


def insert_inspection_report(
    db: Session,
    *,
    run_id: int,
    device_code: str | None,
    severity: str,
    title: str,
    detail: str,
    findings: list[dict[str, Any]] | None = None,
) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO inspection_reports (
              run_id, device_code, severity, title, detail, findings_json
            )
            VALUES (
              :run_id, :device_code, :severity, :title, :detail, :findings_json
            )
            """
        ),
        {
            "run_id": run_id,
            "device_code": device_code,
            "severity": severity,
            "title": title,
            "detail": detail,
            "findings_json": _json_dumps(findings or []),
        },
    )
    return int(result.lastrowid or 0)


def list_inspection_runs(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    return _rows(
        db.execute(
            text(
                """
                SELECT id, trigger_type, status, summary, device_total, issue_total,
                       error_message, started_at, finished_at
                FROM inspection_runs
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    )


def get_inspection_run(db: Session, run_id: int) -> dict[str, Any] | None:
    rows = _rows(
        db.execute(
            text(
                """
                SELECT id, trigger_type, status, summary, device_total, issue_total,
                       error_message, started_at, finished_at
                FROM inspection_runs
                WHERE id = :run_id
                """
            ),
            {"run_id": run_id},
        )
    )
    return rows[0] if rows else None


def list_inspection_reports(
    db: Session,
    *,
    run_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if run_id is None:
        return _rows(
            db.execute(
                text(
                    """
                    SELECT id, run_id, device_code, severity, title, detail,
                           findings_json, created_at
                    FROM inspection_reports
                    ORDER BY id DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
        )
    return _rows(
        db.execute(
            text(
                """
                SELECT id, run_id, device_code, severity, title, detail,
                       findings_json, created_at
                FROM inspection_reports
                WHERE run_id = :run_id
                ORDER BY id ASC
                LIMIT :limit
                """
            ),
            {"run_id": run_id, "limit": limit},
        )
    )


def fetch_predictions_after(
    db: Session,
    *,
    after_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return _rows(
        db.execute(
            text(
                """
                SELECT
                  id, device_code, feature_window_id, model_version,
                  failure_probability, health_score, risk_level,
                  anomaly_score, anomaly_reasons, trend_factor,
                  quality_score, rul_hours, created_at
                FROM prediction_logs
                WHERE id > :after_id
                ORDER BY id ASC
                LIMIT :limit
                """
            ),
            {"after_id": after_id, "limit": limit},
        )
    )


def fetch_warnings_after(
    db: Session,
    *,
    after_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return _rows(
        db.execute(
            text(
                """
                SELECT
                  id, prediction_id, feature_window_id, model_version,
                  failure_probability, health_score, warning_explanation,
                  device_code, risk_level, title, detail, suggested_action,
                  CASE WHEN status = 'pending' THEN 'new' ELSE status END AS status,
                  acknowledged_at, resolved_at, latest_action, created_at
                FROM warning_events
                WHERE id > :after_id
                ORDER BY id ASC
                LIMIT :limit
                """
            ),
            {"after_id": after_id, "limit": limit},
        )
    )
