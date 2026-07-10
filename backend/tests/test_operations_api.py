from app.api.v1 import runtime
from app.main import app
from app.ops.kafka_lag import summarize_partition_lag
from fastapi.testclient import TestClient


def test_summarize_partition_lag_uses_committed_offset() -> None:
    summary = summarize_partition_lag(
        topic="factory.telemetry.raw",
        partition=2,
        committed_offset=12,
        end_offset=20,
    )

    assert summary["lag"] == 8
    assert summary["status"] == "ok"


def test_summarize_partition_lag_reports_uncommitted_partition() -> None:
    summary = summarize_partition_lag(
        topic="factory.telemetry.raw",
        partition=2,
        committed_offset=None,
        end_offset=20,
    )

    assert summary["lag"] is None
    assert summary["status"] == "uncommitted"


def test_runtime_operations_endpoints_return_status_contracts(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "get_streams_status", lambda: {"status": "ok", "groups": []})
    monkeypatch.setattr(runtime, "get_emqx_status", lambda: {"status": "warning", "clients": []})
    monkeypatch.setattr(runtime, "get_backup_status", lambda: {"status": "warning", "backups": {}})
    monkeypatch.setattr(
        runtime, "get_observability_status", lambda: {"status": "warning", "endpoints": {}}
    )
    monkeypatch.setattr(
        runtime, "get_supervision_status", lambda: {"status": "warning", "processes": []}
    )
    client = TestClient(app)

    assert client.get("/api/v1/runtime/streams").json()["status"] == "ok"
    assert client.get("/api/v1/runtime/emqx").json()["clients"] == []
    assert client.get("/api/v1/runtime/backups").json()["backups"] == {}
    assert client.get("/api/v1/runtime/observability").json()["endpoints"] == {}
    assert client.get("/api/v1/runtime/supervision").json()["processes"] == []
