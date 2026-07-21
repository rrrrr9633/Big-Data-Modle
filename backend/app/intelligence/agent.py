from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.intelligence.provider import (
    LlmNotConfiguredError,
    LlmRequestError,
    get_default_provider,
    get_llm_provider_status,
)
from app.intelligence.rag import knowledge_status, search_knowledge
from app.intelligence.tools import gather_operational_facts
from app.intelligence.types import AgentAnswer, ChatMessage
from app.repositories import intelligence_repository as repo
from app.services.simulation_runtime import runtime as simulation_runtime


def build_status(db: Session | None = None) -> dict[str, Any]:
    from app.intelligence.inspection import inspection_scheduler

    provider = get_llm_provider_status()
    model = provider.model or settings.resolved_llm_chat_model()
    schedule_runtime = inspection_scheduler.snapshot().get("schedule") or {
        "enabled": settings.inspection_enabled,
        "minute_of_hour": settings.inspection_minute,
        "device_limit": settings.inspection_device_limit,
    }
    schedule_db: dict[str, Any] | None = None
    knowledge: dict[str, Any]
    if db is not None:
        try:
            schedule_db = repo.get_inspection_schedule(
                db,
                default_enabled=settings.inspection_enabled,
                default_minute=settings.inspection_minute,
                default_device_limit=settings.inspection_device_limit,
            )
        except Exception:  # noqa: BLE001
            schedule_db = None
        try:
            knowledge = knowledge_status(db)
        except Exception as exc:  # noqa: BLE001
            knowledge = {
                "document_total": 0,
                "chunk_total": 0,
                "mode": "keyword-fallback",
                "error": str(exc),
            }
    else:
        knowledge = {
            "document_total": 0,
            "chunk_total": 0,
            "mode": "keyword-fallback",
        }

    schedule = {
        **schedule_runtime,
        "persisted": schedule_db,
    }
    try:
        simulation_running = bool(simulation_runtime.snapshot().running)
    except Exception:  # noqa: BLE001
        simulation_running = False

    llm_configured = bool(provider.configured)
    available = bool(settings.intelligence_enabled)
    degraded = (not available) or (not llm_configured)

    return {
        # Frontend-facing top-level fields
        "available": available,
        "llm_configured": llm_configured,
        "provider": provider.provider,
        "model": model,
        "simulation_running": simulation_running,
        "degraded": degraded,
        "knowledge": knowledge,
        "schedule": schedule,
        # Backward-compatible fields
        "enabled": available,
        "provider_status": provider.to_dict(),
        "rag_mode": "keyword-fallback",
        "inspection": {
            "enabled": bool(schedule_runtime.get("enabled")),
            "minute_of_hour": schedule_runtime.get("minute_of_hour"),
            "device_limit": schedule_runtime.get("device_limit"),
            "schedule": schedule_db,
            "runtime": schedule_runtime,
        },
        "ai4i_dataset_path": settings.resolved_ai4i_dataset_path(),
        "ai4i_archive_dir": settings.ai4i_archive_dir,
        "llm_embedding_model": settings.llm_embedding_model,
        "max_tool_rounds": settings.intelligence_max_tool_rounds,
        "history_limit": settings.intelligence_history_limit,
    }


def answer_query(
    db: Session,
    *,
    question: str,
    session_key: str | None = None,
    user_id: str | None = None,
    use_llm: bool = True,
) -> AgentAnswer:
    facts = gather_operational_facts(db)
    citations = [hit.to_dict() for hit in search_knowledge(db, question)]
    provider_status = get_llm_provider_status()

    if not settings.intelligence_enabled:
        return AgentAnswer(
            mode="query",
            status="disabled",
            answer="智能中台已关闭。以下为实时事实摘要。\n" + _facts_summary(facts),
            facts=facts,
            citations=citations,
            tool_results=facts.get("tools", []),
            degraded=True,
            reason="INTELLIGENCE_ENABLED=false",
        )

    if use_llm and provider_status.configured:
        try:
            completion = get_default_provider().chat(
                [
                    ChatMessage(
                        role="system",
                        content=(
                            "你是工业设备预测性维护智能助手。只根据提供的事实回答，"
                            "不要编造未给出的数据。用简洁中文。"
                        ),
                    ),
                    ChatMessage(
                        role="user",
                        content=_compose_prompt(question, facts, citations),
                    ),
                ]
            )
            return AgentAnswer(
                mode="query",
                status="ok",
                answer=completion.content,
                facts=facts,
                citations=citations,
                tool_results=facts.get("tools", []),
                degraded=False,
            )
        except (LlmNotConfiguredError, LlmRequestError) as exc:
            return AgentAnswer(
                mode="query",
                status="degraded",
                answer=_facts_summary(facts) + f"\n\n（LLM 不可用：{exc}）",
                facts=facts,
                citations=citations,
                tool_results=facts.get("tools", []),
                degraded=True,
                reason=str(exc),
            )

    return AgentAnswer(
        mode="query",
        status="facts_only",
        answer=_facts_summary(facts),
        facts=facts,
        citations=citations,
        tool_results=facts.get("tools", []),
        degraded=not provider_status.configured,
        reason=provider_status.reason,
        session_key=session_key,
    )


def answer_chat(
    db: Session,
    *,
    message: str,
    session_key: str | None = None,
    session_id: int | None = None,
    user_id: str | None = None,
    title: str | None = None,
) -> AgentAnswer:
    session = _resolve_chat_session(
        db,
        session_key=session_key,
        session_id=session_id,
        user_id=user_id,
        title=title or _default_title(message),
    )
    resolved_session_id = int(session["id"])
    session_key_value = str(session["session_key"])
    history_limit = max(int(settings.intelligence_history_limit), 2)

    repo.insert_message(
        db,
        session_id=resolved_session_id,
        role="user",
        content=message,
        mode="chat",
        status="ok",
    )

    facts = gather_operational_facts(db)
    citations = [hit.to_dict() for hit in search_knowledge(db, message)]
    history = repo.fetch_messages(db, session_id=resolved_session_id, limit=history_limit)
    provider_status = get_llm_provider_status()

    if not settings.intelligence_enabled:
        answer_text = "智能中台已关闭，已保存对话记忆，并返回实时事实。\n" + _facts_summary(facts)
        repo.insert_message(
            db,
            session_id=resolved_session_id,
            role="assistant",
            content=answer_text,
            mode="chat",
            status="disabled",
            facts=facts,
            citations=citations,
        )
        return AgentAnswer(
            mode="chat",
            status="disabled",
            answer=answer_text,
            facts=facts,
            citations=citations,
            tool_results=facts.get("tools", []),
            session_id=resolved_session_id,
            session_key=session_key_value,
            degraded=True,
            reason="INTELLIGENCE_ENABLED=false",
        )

    if not provider_status.configured:
        answer_text = (
            "当前 LLM 未配置（API Key 为空），对话已降级。"
            "已保存本次问答记忆，并附上实时运营事实，未伪造模型回答。\n\n"
            + _facts_summary(facts)
        )
        repo.insert_message(
            db,
            session_id=resolved_session_id,
            role="assistant",
            content=answer_text,
            mode="chat",
            status="degraded",
            facts=facts,
            citations=citations,
        )
        return AgentAnswer(
            mode="chat",
            status="degraded",
            answer=answer_text,
            facts=facts,
            citations=citations,
            tool_results=facts.get("tools", []),
            session_id=resolved_session_id,
            session_key=session_key_value,
            degraded=True,
            reason=provider_status.reason or "LLM_API_KEY 未配置",
        )

    try:
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "你是工业设备预测性维护智能助手。结合历史对话、知识检索和实时事实回答。"
                    "不要编造未给出的数据。"
                ),
            )
        ]
        for item in history[:-1]:
            role = str(item.get("role") or "user")
            if role not in {"user", "assistant", "system"}:
                continue
            messages.append(ChatMessage(role=role, content=str(item.get("content") or "")))
        messages.append(
            ChatMessage(
                role="user",
                content=_compose_prompt(message, facts, citations),
            )
        )
        completion = get_default_provider().chat(messages)
        answer_text = completion.content
        status = "ok"
        degraded = False
        reason = None
    except (LlmNotConfiguredError, LlmRequestError) as exc:
        answer_text = (
            f"LLM 调用失败：{exc}。已保存对话记忆，并返回实时事实（未伪造回答）。\n\n"
            + _facts_summary(facts)
        )
        status = "degraded"
        degraded = True
        reason = str(exc)

    repo.insert_message(
        db,
        session_id=resolved_session_id,
        role="assistant",
        content=answer_text,
        mode="chat",
        status=status,
        facts=facts,
        citations=citations,
    )
    return AgentAnswer(
        mode="chat",
        status=status,
        answer=answer_text,
        facts=facts,
        citations=citations,
        tool_results=facts.get("tools", []),
        session_id=resolved_session_id,
        session_key=session_key_value,
        degraded=degraded,
        reason=reason,
    )


def _resolve_chat_session(
    db: Session,
    *,
    session_key: str | None,
    session_id: int | None,
    user_id: str | None,
    title: str,
) -> dict[str, Any]:
    if session_id is not None:
        existing = repo.get_session_by_id(db, int(session_id))
        if existing is not None:
            return existing
    if session_key:
        existing = repo.get_session_by_key(db, session_key)
        if existing is not None:
            return existing
    return repo.create_session(
        db,
        session_key=session_key,
        user_id=user_id,
        title=title,
    )


def _compose_prompt(
    question: str,
    facts: dict[str, Any],
    citations: list[dict[str, Any]],
) -> str:
    return (
        f"用户问题：{question}\n\n"
        f"实时事实 JSON：\n{json.dumps(facts, ensure_ascii=False, default=str)[:6000]}\n\n"
        f"知识检索：\n{json.dumps(citations, ensure_ascii=False, default=str)[:3000]}"
    )


def _facts_summary(facts: dict[str, Any]) -> str:
    realtime = facts.get("realtime.overview") or {}
    maintenance = facts.get("maintenance.repository") or {}
    simulation = facts.get("simulation.runtime") or {}
    model = facts.get("model.registry") or {}
    summary = maintenance.get("summary") if isinstance(maintenance, dict) else {}
    high_risk = realtime.get("high_risk_devices") if isinstance(realtime, dict) else []
    lines = [
        "【实时运营事实】",
        f"- 设备总数: {realtime.get('device_total', 0)}，在线: {realtime.get('online_total', 0)}",
        f"- 预警总数(近窗): {realtime.get('warning_total', 0)}，预测总数(近窗): {realtime.get('prediction_total', 0)}",
        f"- 看板: 设备 {summary.get('device_total', 0)}，高风险设备 {summary.get('high_risk_device_total', 0)}，"
        f"今日预警 {summary.get('today_warning_total', 0)}，平均健康分 {summary.get('average_health_score', 0)}",
        f"- 仿真: running={simulation.get('running')} mode={simulation.get('mode')} "
        f"devices={simulation.get('device_count')}",
        f"- 模型: available={model.get('available')}",
    ]
    if isinstance(high_risk, list) and high_risk:
        codes = ", ".join(
            str(item.get("device_code"))
            for item in high_risk[:8]
            if isinstance(item, dict)
        )
        lines.append(f"- 高风险设备: {codes}")
    else:
        lines.append("- 高风险设备: 无")
    return "\n".join(lines)


def _default_title(message: str) -> str:
    text = (message or "").strip().replace("\n", " ")
    return (text[:40] + "…") if len(text) > 40 else (text or "新会话")
