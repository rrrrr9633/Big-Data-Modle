from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.intelligence import agent as intelligence_agent
from app.intelligence.inspection import inspection_scheduler
from app.intelligence.rag import knowledge_status, sync_knowledge_from_history
from app.repositories import intelligence_repository as repo
from app.schemas.intelligence import ChatIn, InspectionScheduleIn, KnowledgeSyncIn, QueryIn

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/status")
def get_intelligence_status(db: DbSession) -> dict[str, Any]:
    status = intelligence_agent.build_status(db)
    status["scheduler"] = inspection_scheduler.snapshot()
    return status


@router.post("/query")
def post_intelligence_query(payload: QueryIn, db: DbSession) -> dict[str, Any]:
    question = payload.question or ""
    if not settings.intelligence_enabled:
        answer = intelligence_agent.answer_query(
            db,
            question=question,
            session_key=payload.session_key,
            user_id=payload.user_id,
            use_llm=False,
        )
        return answer.to_dict()
    answer = intelligence_agent.answer_query(
        db,
        question=question,
        session_key=payload.session_key,
        user_id=payload.user_id,
        use_llm=payload.use_llm,
    )
    return answer.to_dict()


@router.post("/chat")
def post_intelligence_chat(payload: ChatIn, db: DbSession) -> dict[str, Any]:
    answer = intelligence_agent.answer_chat(
        db,
        message=payload.message,
        session_key=payload.session_key,
        session_id=payload.session_id,
        user_id=payload.user_id,
        title=payload.title,
    )
    db.commit()
    return answer.to_dict()


@router.get("/sessions")
def list_intelligence_sessions(db: DbSession, limit: int = 50) -> dict[str, Any]:
    sessions = repo.list_sessions(db, limit=max(1, min(limit, 200)))
    return {"items": sessions, "total": len(sessions)}


@router.get("/sessions/{session_id}")
def get_intelligence_session(session_id: int, db: DbSession) -> dict[str, Any]:
    session = repo.get_session_by_id(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = repo.fetch_messages(db, session_id=session_id, limit=200)
    return {"session": session, "messages": messages}


@router.get("/sessions/by-key/{session_key}")
def get_intelligence_session_by_key(session_key: str, db: DbSession) -> dict[str, Any]:
    session = repo.get_session_by_key(db, session_key)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = repo.fetch_messages(db, session_id=int(session["id"]), limit=200)
    return {"session": session, "messages": messages}


@router.get("/knowledge/status")
def get_knowledge_status(db: DbSession) -> dict[str, Any]:
    return knowledge_status(db)


@router.post("/knowledge/sync")
def post_knowledge_sync(db: DbSession, payload: KnowledgeSyncIn | None = None) -> dict[str, Any]:
    batch_size = payload.batch_size if payload is not None else None
    result = sync_knowledge_from_history(db, batch_size=batch_size)
    db.commit()
    return result


@router.get("/inspection/schedule")
def get_inspection_schedule(db: DbSession) -> dict[str, Any]:
    schedule = repo.get_inspection_schedule(
        db,
        default_enabled=settings.inspection_enabled,
        default_minute=settings.inspection_minute,
        default_device_limit=settings.inspection_device_limit,
    )
    runtime = inspection_scheduler.snapshot()
    return {
        "schedule": schedule,
        "runtime": runtime,
        "config": {
            "inspection_enabled": settings.inspection_enabled,
            "inspection_minute": settings.inspection_minute,
            "inspection_device_limit": settings.inspection_device_limit,
        },
    }


@router.put("/inspection/schedule")
def put_inspection_schedule(payload: InspectionScheduleIn, db: DbSession) -> dict[str, Any]:
    schedule = repo.upsert_inspection_schedule(
        db,
        enabled=payload.enabled,
        minute_of_hour=payload.minute_of_hour,
        device_limit=payload.device_limit,
    )
    db.commit()
    runtime_schedule = inspection_scheduler.configure(
        enabled=payload.enabled,
        minute_of_hour=payload.minute_of_hour,
        device_limit=payload.device_limit,
    )
    return {
        "schedule": schedule,
        "runtime": inspection_scheduler.snapshot(),
        "applied": runtime_schedule,
        "note": "已写入数据库并立即 configure 巡检运行时；自动调度使用持久化 enabled/minute/device_limit。",
    }


@router.post("/inspection/run")
def post_inspection_run(db: DbSession) -> dict[str, Any]:
    del db  # run opens its own session for thread-safe commits
    result = inspection_scheduler.run_once(trigger_type="manual")
    if result.get("status") == "busy":
        raise HTTPException(status_code=409, detail=result.get("reason") or "巡检进行中")
    return result


@router.get("/inspection/reports")
def list_inspection_reports(
    db: DbSession,
    run_id: int | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    runs = repo.list_inspection_runs(db, limit=max(1, min(limit, 200)))
    reports = repo.list_inspection_reports(
        db,
        run_id=run_id,
        limit=max(1, min(limit, 500)),
    )
    return {"runs": runs, "reports": reports}


@router.get("/inspection/reports/{run_id}")
def get_inspection_report(run_id: int, db: DbSession) -> dict[str, Any]:
    run = repo.get_inspection_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="巡检 run 不存在")
    reports = repo.list_inspection_reports(db, run_id=run_id, limit=500)
    return {"run": run, "reports": reports}
