from app.api.v1 import quality
from app.main import app
from fastapi.testclient import TestClient


def test_quality_summary_endpoint_returns_point_quality_and_invalid_events(monkeypatch) -> None:
    monkeypatch.setattr(
        quality,
        "fetch_point_quality_summary",
        lambda minutes, limit: [
            {
                "device_code": "CNC-001",
                "point_code": "spindle_temperature",
                "reading_count": 12,
                "average_quality": 0.96,
                "last_seen": "2026-07-10T15:30:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(
        quality,
        "fetch_recent_invalid_telemetry_events",
        lambda limit: [
            {
                "reason": "unit mismatch: expected C, got F",
                "raw": '{"device_code":"CNC-001"}',
            }
        ],
    )

    response = TestClient(app).get("/api/v1/quality/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["window_minutes"] == 60
    assert body["quality_points"][0]["device_code"] == "CNC-001"
    assert body["quality_points"][0]["average_quality"] == 0.96
    assert body["invalid_events"][0]["reason"] == "unit mismatch: expected C, got F"


def test_quality_summary_marks_unknown_when_invalid_topic_cannot_be_read(monkeypatch) -> None:
    monkeypatch.setattr(quality, "fetch_point_quality_summary", lambda minutes, limit: [])

    def fail_invalid_topic(_limit: int) -> list[dict[str, object]]:
        raise RuntimeError("Kafka unavailable")

    monkeypatch.setattr(quality, "fetch_recent_invalid_telemetry_events", fail_invalid_topic)

    response = TestClient(app).get("/api/v1/quality/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["invalid_events"] == []
    assert body["invalid_trace_status"] == "unavailable"
    assert body["invalid_trace_error"] == "Kafka unavailable"
