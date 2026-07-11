from app.main import app
from fastapi.testclient import TestClient


def test_simulation_scene_can_start_advance_and_stop() -> None:
    client = TestClient(app)

    started = client.post(
        "/api/v1/simulation/start",
        json={"device_count": 3, "mode": "degrading"},
    )
    advanced = client.post("/api/v1/simulation/tick")
    stopped = client.post("/api/v1/simulation/stop")

    assert started.status_code == 200
    assert started.json()["running"] is True
    assert len(started.json()["devices"]) == 3
    assert advanced.json()["cycle"] == 2
    assert advanced.json()["devices"][0]["readings"]["spindle_temperature"]["value"] > 0
    assert stopped.json()["running"] is False
