from __future__ import annotations

from app.core.config import Settings
from app.intelligence import agent as intelligence_agent
from app.intelligence import rag as intelligence_rag
from app.intelligence.inspection import InspectionScheduler
from app.intelligence.provider import OpenAICompatibleProvider, get_llm_provider_status
from app.intelligence.rag import tokenize
from app.intelligence.types import KnowledgeHit
from app.schemas.intelligence import ChatIn, QueryIn
from pydantic import ValidationError


def test_llm_provider_unconfigured_by_default() -> None:
    status = get_llm_provider_status()
    assert status.configured is False
    assert status.provider == "openai-compatible"
    assert "API" in (status.reason or "") or "未配置" in (status.reason or "")


def test_openai_provider_raises_when_unconfigured() -> None:
    provider = OpenAICompatibleProvider(api_key="")
    try:
        provider.chat([{"role": "user", "content": "hi"}])
        assert False, "expected LlmNotConfiguredError"
    except Exception as exc:
        assert "未配置" in str(exc) or "LLM" in str(exc)


def test_provider_uses_chat_model_over_legacy_model(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "legacy-model")
    monkeypatch.setenv("LLM_CHAT_MODEL", "chat-preferred")
    Settings.model_config  # keep reference for linters
    # Build a fresh Settings without touching global lru_cache settings object fields directly.
    local = Settings(
        llm_model="legacy-model",
        llm_chat_model="chat-preferred",
        llm_api_key="",
    )
    assert local.resolved_llm_chat_model() == "chat-preferred"
    assert local.resolved_ai4i_dataset_path() == local.ai4i_dataset_path
    local2 = Settings(ai4i_dataset_path="../old.csv", ai4i_base_dataset_path="../base.csv")
    assert local2.resolved_ai4i_dataset_path() == "../base.csv"


def test_tokenize_supports_chinese_and_english() -> None:
    tokens = tokenize("设备 CNC-01 风险 high")
    assert "设备" in tokens
    assert "cnc" in tokens or "01" in tokens
    assert "风险" in tokens
    assert "high" in tokens


def test_query_in_accepts_question_or_query_alias() -> None:
    by_question = QueryIn(question="设备健康如何？")
    assert by_question.question == "设备健康如何？"
    by_query = QueryIn(query="当前预警有哪些？")
    assert by_query.question == "当前预警有哪些？"
    try:
        QueryIn()
        assert False, "expected validation error"
    except ValidationError:
        pass


def test_chat_in_accepts_session_id() -> None:
    payload = ChatIn(message="继续", session_id=12, session_key="k1")
    assert payload.session_id == 12
    assert payload.session_key == "k1"
    payload2 = ChatIn.model_validate({"message": "hi", "session_id": "99"})
    assert payload2.session_id == 99


def test_query_returns_facts_without_llm(monkeypatch) -> None:
    monkeypatch.setattr(
        intelligence_agent,
        "gather_operational_facts",
        lambda _db: {
            "tools": [{"name": "realtime.overview", "ok": True, "data": {}}],
            "realtime.overview": {
                "device_total": 2,
                "online_total": 1,
                "warning_total": 0,
                "prediction_total": 0,
                "high_risk_devices": [],
            },
            "maintenance.repository": {
                "summary": {
                    "device_total": 2,
                    "high_risk_device_total": 0,
                    "today_warning_total": 0,
                    "average_health_score": 90,
                }
            },
            "simulation.runtime": {"running": False, "mode": "degrading", "device_count": 0},
            "model.registry": {"available": False},
        },
    )
    monkeypatch.setattr(intelligence_agent, "search_knowledge", lambda _db, _q: [])
    monkeypatch.setattr(
        intelligence_agent,
        "get_llm_provider_status",
        lambda: type(
            "S",
            (),
            {
                "configured": False,
                "reason": "LLM_API_KEY 未配置",
                "to_dict": lambda self: {"configured": False},
            },
        )(),
    )

    answer = intelligence_agent.answer_query(db=None, question="当前有多少设备？")  # type: ignore[arg-type]
    assert answer.degraded is True
    assert "实时" in answer.answer or "设备" in answer.answer
    assert answer.facts["realtime.overview"]["device_total"] == 2


def test_chat_degraded_still_persists_memory(monkeypatch) -> None:
    stored: list[dict] = []

    monkeypatch.setattr(
        intelligence_agent.repo,
        "get_or_create_session",
        lambda _db, **kwargs: {"id": 7, "session_key": kwargs.get("session_key") or "s1"},
    )
    monkeypatch.setattr(
        intelligence_agent.repo,
        "create_session",
        lambda _db, **kwargs: {"id": 7, "session_key": kwargs.get("session_key") or "s1"},
    )
    monkeypatch.setattr(
        intelligence_agent.repo,
        "get_session_by_id",
        lambda _db, sid: {"id": sid, "session_key": f"key-{sid}"} if sid == 7 else None,
    )
    monkeypatch.setattr(
        intelligence_agent.repo,
        "insert_message",
        lambda _db, **kwargs: stored.append(kwargs) or len(stored),
    )
    monkeypatch.setattr(intelligence_agent.repo, "fetch_messages", lambda *_a, **_k: [])
    monkeypatch.setattr(
        intelligence_agent,
        "gather_operational_facts",
        lambda _db: {
            "tools": [],
            "realtime.overview": {
                "device_total": 1,
                "online_total": 1,
                "warning_total": 0,
                "prediction_total": 0,
            },
            "maintenance.repository": {"summary": {}},
            "simulation.runtime": {},
            "model.registry": {"available": False},
        },
    )
    monkeypatch.setattr(intelligence_agent, "search_knowledge", lambda *_a, **_k: [])
    monkeypatch.setattr(
        intelligence_agent,
        "get_llm_provider_status",
        lambda: type(
            "S",
            (),
            {"configured": False, "reason": "LLM_API_KEY 未配置", "to_dict": lambda self: {}},
        )(),
    )

    answer = intelligence_agent.answer_chat(db=None, message="你好")  # type: ignore[arg-type]
    assert answer.status == "degraded"
    assert answer.session_id == 7
    assert len(stored) == 2
    assert stored[0]["role"] == "user"
    assert stored[1]["role"] == "assistant"
    assert "未配置" in answer.answer or "降级" in answer.answer

    stored.clear()
    answer2 = intelligence_agent.answer_chat(db=None, message="继续", session_id=7)  # type: ignore[arg-type]
    assert answer2.session_id == 7
    assert answer2.session_key == "key-7"


def test_inspection_configure_controls_runtime_not_only_env() -> None:
    scheduler = InspectionScheduler()
    assert scheduler.snapshot()["enabled"] is False or isinstance(
        scheduler.snapshot()["enabled"], bool
    )
    applied = scheduler.configure(enabled=True, minute_of_hour=17, device_limit=3)
    snap = scheduler.snapshot()
    assert applied["enabled"] is True
    assert snap["enabled"] is True
    assert snap["minute_of_hour"] == 17
    assert snap["device_limit"] == 3
    scheduler.configure(enabled=False, minute_of_hour=0, device_limit=50)
    assert scheduler.snapshot()["enabled"] is False


def test_inspection_run_records_failure_when_model_missing(monkeypatch) -> None:
    class _FakeDb:
        def commit(self) -> None:
            return None

        def rollback(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "app.intelligence.inspection.SessionLocal",
        lambda: _FakeDb(),
    )
    monkeypatch.setattr(
        "app.intelligence.inspection.get_active_model_state",
        lambda: type("M", (), {"available": False})(),
    )
    finished: dict = {}

    def create_run(_db, **kwargs):
        return 11

    def finish_run(_db, **kwargs):
        finished.update(kwargs)

    monkeypatch.setattr("app.intelligence.inspection.repo.create_inspection_run", create_run)
    monkeypatch.setattr("app.intelligence.inspection.repo.finish_inspection_run", finish_run)

    scheduler = InspectionScheduler()
    result = scheduler.run_once(trigger_type="manual")
    assert result["status"] == "failed"
    assert result["run_id"] == 11
    assert finished["status"] == "failed"
    assert "模型" in (finished.get("error_message") or "")


def test_inspection_completed_ingests_knowledge(monkeypatch) -> None:
    class _FakeDb:
        def commit(self) -> None:
            return None

        def rollback(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.intelligence.inspection.SessionLocal", lambda: _FakeDb())
    monkeypatch.setattr(
        "app.intelligence.inspection.get_active_model_state",
        lambda: type("M", (), {"available": True})(),
    )
    monkeypatch.setattr(
        "app.intelligence.inspection.gather_operational_facts",
        lambda _db: {
            "realtime.overview": {
                "devices": [
                    {
                        "device_code": "CNC-1",
                        "online": False,
                        "latest_prediction": None,
                        "latest_warning": None,
                    }
                ]
            }
        },
    )
    monkeypatch.setattr(
        "app.intelligence.inspection.repo.create_inspection_run",
        lambda *_a, **_k: 21,
    )
    monkeypatch.setattr(
        "app.intelligence.inspection.repo.insert_inspection_report",
        lambda *_a, **_k: 1,
    )
    monkeypatch.setattr(
        "app.intelligence.inspection.repo.finish_inspection_run",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "app.intelligence.inspection.repo.touch_inspection_schedule",
        lambda *_a, **_k: None,
    )
    ingested: dict = {}

    def fake_ingest(_db, *, run_id: int):
        ingested["run_id"] = run_id
        return {"ingested": True, "run_id": run_id, "document_id": 9}

    monkeypatch.setattr(
        "app.intelligence.inspection.ingest_inspection_run_to_knowledge",
        fake_ingest,
    )

    scheduler = InspectionScheduler()
    scheduler.configure(enabled=False, minute_of_hour=0, device_limit=10)
    result = scheduler.run_once(trigger_type="manual")
    assert result["status"] == "completed"
    assert ingested["run_id"] == 21
    assert result["knowledge"]["ingested"] is True


def test_ingest_inspection_run_to_knowledge_idempotent(monkeypatch) -> None:
    upserts: list[dict] = []

    monkeypatch.setattr(
        intelligence_rag.repo,
        "get_inspection_run",
        lambda _db, run_id: {
            "id": run_id,
            "status": "completed",
            "trigger_type": "manual",
            "summary": "ok",
            "device_total": 1,
            "issue_total": 1,
            "started_at": "t0",
            "finished_at": "t1",
        },
    )
    monkeypatch.setattr(
        intelligence_rag.repo,
        "list_inspection_reports",
        lambda _db, run_id=None, limit=500: [
            {
                "severity": "high",
                "device_code": "CNC-1",
                "title": "离线",
                "detail": "不在线",
            }
        ],
    )

    def upsert(_db, **kwargs):
        upserts.append(kwargs)
        return 100

    monkeypatch.setattr(intelligence_rag.repo, "upsert_knowledge_document", upsert)
    monkeypatch.setattr(
        intelligence_rag.repo,
        "replace_knowledge_chunks",
        lambda *_a, **_k: None,
    )

    first = intelligence_rag.ingest_inspection_run_to_knowledge(db=None, run_id=5)  # type: ignore[arg-type]
    second = intelligence_rag.ingest_inspection_run_to_knowledge(db=None, run_id=5)  # type: ignore[arg-type]
    assert first["ingested"] is True
    assert second["ingested"] is True
    assert first["source_type"] == "inspection_run"
    assert first["source_id"] == "5"
    assert len(upserts) == 2
    assert upserts[0]["source_type"] == "inspection_run"
    assert upserts[0]["source_id"] == "5"


def test_knowledge_keyword_search_scores_hits(monkeypatch) -> None:
    monkeypatch.setattr(
        intelligence_rag.repo,
        "fetch_knowledge_chunks",
        lambda _db, limit=500: [
            {
                "id": 1,
                "document_id": 10,
                "source_type": "warning",
                "source_id": "3",
                "title": "预警 CNC-01 高温",
                "content": "设备 CNC-01 温度异常",
                "keywords": "cnc 温度 预警",
            },
            {
                "id": 2,
                "document_id": 11,
                "source_type": "prediction",
                "source_id": "9",
                "title": "其他",
                "content": "无关内容",
                "keywords": "",
            },
        ],
    )
    hits = intelligence_rag.search_knowledge(db=None, query="CNC 温度")  # type: ignore[arg-type]
    assert hits
    assert isinstance(hits[0], KnowledgeHit)
    assert hits[0].source_type == "warning"


def test_build_status_top_level_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        intelligence_agent,
        "get_llm_provider_status",
        lambda: type(
            "S",
            (),
            {
                "configured": False,
                "provider": "openai-compatible",
                "model": "gpt-4o-mini",
                "to_dict": lambda self: {
                    "configured": False,
                    "provider": "openai-compatible",
                    "model": "gpt-4o-mini",
                },
            },
        )(),
    )
    monkeypatch.setattr(
        intelligence_agent,
        "knowledge_status",
        lambda _db: {"document_total": 0, "chunk_total": 0, "mode": "keyword-fallback"},
    )
    monkeypatch.setattr(
        intelligence_agent.simulation_runtime,
        "snapshot",
        lambda: type("R", (), {"running": False})(),
    )
    from app.intelligence.inspection import inspection_scheduler

    inspection_scheduler.configure(enabled=False, minute_of_hour=5, device_limit=9)
    status = intelligence_agent.build_status(db=None)
    assert status["available"] is True
    assert status["llm_configured"] is False
    assert status["provider"] == "openai-compatible"
    assert status["model"] == "gpt-4o-mini"
    assert status["simulation_running"] is False
    assert status["degraded"] is True
    assert "knowledge" in status
    assert status["schedule"]["minute_of_hour"] == 5
    assert status["enabled"] is True
    assert "provider_status" in status


def test_intelligence_routes_registered() -> None:
    from app.api.v1 import intelligence as intelligence_api

    paths = {getattr(route, "path", "") for route in intelligence_api.router.routes}
    assert "/status" in paths
    assert "/query" in paths
    assert "/chat" in paths
    assert "/knowledge/sync" in paths
    assert "/inspection/run" in paths


def test_model_training_jobs_ddl_matches_repository() -> None:
    from pathlib import Path

    init_sql = Path(__file__).resolve().parents[2] / "infra" / "mysql" / "init.sql"
    text = init_sql.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS model_training_jobs" in text
    assert "trained_rows" in text
    assert "detail_json" in text
    assert "created_by" in text
    assert "job_name" not in text.split("model_training_jobs")[1].split("CREATE TABLE")[0]
    assert "dataset_path" not in text.split("model_training_jobs")[1].split("CREATE TABLE")[0]
    assert "progress" not in text.split("model_training_jobs")[1].split("CREATE TABLE")[0]
