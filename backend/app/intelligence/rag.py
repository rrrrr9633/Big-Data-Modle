from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.intelligence.types import KnowledgeHit
from app.repositories import intelligence_repository as repo


_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text or "") if token.strip()]


def search_knowledge(
    db: Session,
    query: str,
    *,
    top_k: int | None = None,
) -> list[KnowledgeHit]:
    limit = top_k if top_k is not None else settings.intelligence_rag_top_k
    tokens = tokenize(query)
    chunks = repo.fetch_knowledge_chunks(db, limit=500)
    if not chunks:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    query_lower = (query or "").lower()
    for chunk in chunks:
        content = str(chunk.get("content") or "")
        title = str(chunk.get("title") or "")
        keywords = str(chunk.get("keywords") or "")
        haystack = f"{title}\n{keywords}\n{content}".lower()
        score = 0.0
        if query_lower and query_lower in haystack:
            score += 5.0
        for token in tokens:
            if token in haystack:
                score += 1.0 + (0.2 if token in keywords.lower() else 0.0)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: (-item[0], -int(item[1].get("id") or 0)))
    hits: list[KnowledgeHit] = []
    for score, chunk in scored[: max(limit, 1)]:
        hits.append(
            KnowledgeHit(
                document_id=int(chunk.get("document_id") or 0),
                chunk_id=int(chunk.get("id") or 0),
                source_type=str(chunk.get("source_type") or ""),
                source_id=str(chunk.get("source_id") or ""),
                title=str(chunk.get("title") or ""),
                content=str(chunk.get("content") or ""),
                score=float(score),
            )
        )
    return hits


def sync_knowledge_from_history(
    db: Session,
    *,
    batch_size: int | None = None,
) -> dict[str, Any]:
    size = batch_size if batch_size is not None else settings.intelligence_knowledge_batch_size
    prediction_cursor = repo.get_sync_cursor(db, "prediction")
    warning_cursor = repo.get_sync_cursor(db, "warning")
    last_prediction_id = int(prediction_cursor.get("last_source_id") or 0)
    last_warning_id = int(warning_cursor.get("last_source_id") or 0)

    prediction_rows = repo.fetch_predictions_after(
        db, after_id=last_prediction_id, limit=size
    )
    warning_rows = repo.fetch_warnings_after(db, after_id=last_warning_id, limit=size)

    synced_predictions = 0
    synced_warnings = 0
    max_prediction_id = last_prediction_id
    max_warning_id = last_warning_id

    for row in prediction_rows:
        source_id = str(row.get("id"))
        title = (
            f"预测 {row.get('device_code')} "
            f"风险={row.get('risk_level')} 健康={row.get('health_score')}"
        )
        content = _format_prediction_document(row)
        document_id = repo.upsert_knowledge_document(
            db,
            source_type="prediction",
            source_id=source_id,
            title=title,
            content=content,
            metadata={
                "device_code": row.get("device_code"),
                "risk_level": row.get("risk_level"),
                "prediction_id": row.get("id"),
            },
            content_hash=_hash_text(content),
        )
        repo.replace_knowledge_chunks(
            db,
            document_id=document_id,
            chunks=[
                {
                    "chunk_index": 0,
                    "content": content,
                    "keywords": _keywords_from_text(content),
                    "metadata": {
                        "source_type": "prediction",
                        "source_id": source_id,
                    },
                }
            ],
        )
        synced_predictions += 1
        max_prediction_id = max(max_prediction_id, int(row.get("id") or 0))

    for row in warning_rows:
        source_id = str(row.get("id"))
        title = f"预警 {row.get('device_code')} {row.get('title') or ''}".strip()
        content = _format_warning_document(row)
        document_id = repo.upsert_knowledge_document(
            db,
            source_type="warning",
            source_id=source_id,
            title=title,
            content=content,
            metadata={
                "device_code": row.get("device_code"),
                "risk_level": row.get("risk_level"),
                "warning_id": row.get("id"),
                "status": row.get("status"),
            },
            content_hash=_hash_text(content),
        )
        repo.replace_knowledge_chunks(
            db,
            document_id=document_id,
            chunks=[
                {
                    "chunk_index": 0,
                    "content": content,
                    "keywords": _keywords_from_text(content),
                    "metadata": {
                        "source_type": "warning",
                        "source_id": source_id,
                    },
                }
            ],
        )
        synced_warnings += 1
        max_warning_id = max(max_warning_id, int(row.get("id") or 0))

    if synced_predictions:
        repo.update_sync_cursor(
            db,
            source_type="prediction",
            last_source_id=max_prediction_id,
            total_synced=int(prediction_cursor.get("total_synced") or 0) + synced_predictions,
        )
    if synced_warnings:
        repo.update_sync_cursor(
            db,
            source_type="warning",
            last_source_id=max_warning_id,
            total_synced=int(warning_cursor.get("total_synced") or 0) + synced_warnings,
        )

    return {
        "synced_predictions": synced_predictions,
        "synced_warnings": synced_warnings,
        "prediction_cursor": max_prediction_id,
        "warning_cursor": max_warning_id,
        "document_total": repo.count_knowledge_documents(db),
        "chunk_total": repo.count_knowledge_chunks(db),
    }


def knowledge_status(db: Session) -> dict[str, Any]:
    return {
        "document_total": repo.count_knowledge_documents(db),
        "chunk_total": repo.count_knowledge_chunks(db),
        "cursors": {
            "prediction": repo.get_sync_cursor(db, "prediction"),
            "warning": repo.get_sync_cursor(db, "warning"),
        },
        "mode": "keyword-fallback",
    }


def ingest_inspection_run_to_knowledge(db: Session, *, run_id: int) -> dict[str, Any]:
    """Idempotently upsert a completed inspection run into the knowledge base."""
    run = repo.get_inspection_run(db, run_id)
    if run is None:
        return {"ingested": False, "reason": "run_not_found", "run_id": run_id}

    reports = repo.list_inspection_reports(db, run_id=run_id, limit=500)
    source_id = str(run_id)
    title = f"巡检报告 #{run_id} status={run.get('status')}"
    content = _format_inspection_document(run, reports)
    document_id = repo.upsert_knowledge_document(
        db,
        source_type="inspection_run",
        source_id=source_id,
        title=title,
        content=content,
        metadata={
            "run_id": run_id,
            "status": run.get("status"),
            "trigger_type": run.get("trigger_type"),
            "device_total": run.get("device_total"),
            "issue_total": run.get("issue_total"),
            "report_count": len(reports),
        },
        content_hash=_hash_text(content),
    )
    repo.replace_knowledge_chunks(
        db,
        document_id=document_id,
        chunks=[
            {
                "chunk_index": 0,
                "content": content,
                "keywords": _keywords_from_text(content),
                "metadata": {
                    "source_type": "inspection_run",
                    "source_id": source_id,
                },
            }
        ],
    )
    return {
        "ingested": True,
        "run_id": run_id,
        "document_id": document_id,
        "source_type": "inspection_run",
        "source_id": source_id,
        "report_count": len(reports),
    }


def _format_inspection_document(
    run: dict[str, Any],
    reports: list[dict[str, Any]],
) -> str:
    lines = [
        f"巡检 run #{run.get('id')}，触发方式 {run.get('trigger_type')}，状态 {run.get('status')}。",
        f"摘要: {run.get('summary') or '无'}。",
        f"扫描设备 {run.get('device_total')} 台，问题 {run.get('issue_total')} 项。",
        f"开始 {run.get('started_at')}，结束 {run.get('finished_at')}。",
    ]
    if run.get("error_message"):
        lines.append(f"错误: {run.get('error_message')}")
    for report in reports[:50]:
        lines.append(
            f"- [{report.get('severity')}] 设备 {report.get('device_code')}: "
            f"{report.get('title')}。{report.get('detail')}"
        )
    if not reports:
        lines.append("本轮无设备级问题明细。")
    return "\n".join(lines)


def _format_prediction_document(row: dict[str, Any]) -> str:
    reasons = row.get("anomaly_reasons")
    reason_text = ", ".join(str(item) for item in reasons) if isinstance(reasons, list) else ""
    return (
        f"设备 {row.get('device_code')} 预测记录 #{row.get('id')}。"
        f"风险等级 {row.get('risk_level')}，健康分 {row.get('health_score')}，"
        f"故障概率 {row.get('failure_probability')}，"
        f"异常分 {row.get('anomaly_score')}，RUL {row.get('rul_hours')}。"
        f"异常原因: {reason_text or '无'}。"
        f"时间 {row.get('created_at')}。"
    )


def _format_warning_document(row: dict[str, Any]) -> str:
    return (
        f"设备 {row.get('device_code')} 预警 #{row.get('id')}。"
        f"标题: {row.get('title')}。"
        f"风险 {row.get('risk_level')}，状态 {row.get('status')}。"
        f"详情: {row.get('detail')}。"
        f"建议: {row.get('suggested_action')}。"
        f"时间 {row.get('created_at')}。"
    )


def _keywords_from_text(text: str) -> str:
    tokens = tokenize(text)
    unique = list(dict.fromkeys(tokens))
    return " ".join(unique[:40])


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
