from app.api.v1 import runtime
from app.main import app
from app.quality.idempotency import create_redis_client
from fastapi.testclient import TestClient


def test_runtime_redis_probe_uses_shared_redis_client_factory() -> None:
    assert runtime.create_redis_client is create_redis_client


def test_runtime_diagnostics_reports_ready_when_all_dependencies_available(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime,
        "build_runtime_diagnostics",
        lambda: {
            "status": "ready",
            "dependencies": [
                {"name": "mysql", "status": "ok"},
                {"name": "redis", "status": "ok"},
            ],
            "stream_consumers": [
                {
                    "name": "mqtt-to-kafka",
                    "enabled": True,
                    "source": "MQTT",
                    "target": "factory.telemetry.raw",
                },
            ],
            "production_gaps": [],
        },
    )

    response = TestClient(app).get("/api/v1/runtime/diagnostics")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["dependencies"][0]["name"] == "mysql"
    assert response.json()["stream_consumers"][0]["source"] == "MQTT"
    assert response.json()["stream_consumers"][0]["target"] == "factory.telemetry.raw"


def test_build_runtime_diagnostics_marks_disabled_consumers_as_production_gap(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "_check_mysql", lambda: {"name": "mysql", "status": "ok"})
    monkeypatch.setattr(runtime, "_check_tsdb", lambda: {"name": "tsdb", "status": "ok"})
    monkeypatch.setattr(runtime, "_check_redis", lambda: {"name": "redis", "status": "ok"})
    monkeypatch.setattr(runtime, "_check_kafka", lambda: {"name": "kafka", "status": "ok"})
    monkeypatch.setattr(runtime, "_check_mqtt", lambda: {"name": "mqtt", "status": "ok"})
    monkeypatch.setattr(
        runtime,
        "_stream_consumer_states",
        lambda: [
            {"name": "mqtt-to-kafka", "enabled": True},
            {"name": "raw-telemetry", "enabled": False},
        ],
    )
    monkeypatch.setattr(
        runtime,
        "get_active_model_state",
        lambda: type("ModelState", (), {"available": True, "saved_at": "2026-07-10T00:00:00Z"})(),
    )

    diagnostics = runtime.build_runtime_diagnostics()

    assert diagnostics["status"] == "degraded"
    assert "raw-telemetry 消费者未启用" in diagnostics["production_gaps"]


def test_stream_consumer_states_include_topics_groups_and_responsibilities() -> None:
    states = runtime._stream_consumer_states()

    assert states[1]["name"] == "raw-telemetry"
    assert states[1]["source"] == "factory.telemetry.raw"
    assert states[1]["target"] == "factory.telemetry.cleaned"
    assert states[1]["group_id"] == "pdm-raw-telemetry-cleaner"
    assert "清洗" in states[1]["responsibility"]


def test_runtime_diagnostics_includes_operations_readiness(monkeypatch) -> None:
    monkeypatch.setattr(runtime.settings, "auth_enabled", True)
    monkeypatch.setattr(runtime.settings, "auth_token_secret", "change-me-in-production")
    diagnostics = runtime.build_operations_readiness(
        dependencies=[{"name": "mysql", "status": "ok"}],
        stream_consumers=[{"name": "raw-telemetry", "enabled": True}],
        active_model_available=True,
    )

    assert diagnostics[0]["area"] == "security"
    assert diagnostics[0]["status"] == "warning"
    assert "AUTH_TOKEN_SECRET" in diagnostics[0]["items"][0]
    assert any(item["area"] == "backup" for item in diagnostics)
