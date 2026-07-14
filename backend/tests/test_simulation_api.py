from app.api.v1 import simulation
from app.edge.device_stream import DeviceStreamConfig, DeviceStreamRuntime
from app.main import app
from fastapi.testclient import TestClient


def test_simulation_scene_starts_a_continuous_device_stream(monkeypatch) -> None:
    runtime = DeviceStreamRuntime()

    class FakeStream:
        def start(self, config: DeviceStreamConfig) -> None:
            runtime.running = True
            runtime.config = config
            runtime.device_codes = ["CNC-L01-001", "CNC-L01-002", "CNC-L01-003"]
            runtime.cycle = 1
            runtime.accepted_events = 24

        def emit_cycle(self) -> None:
            runtime.cycle += 1
            runtime.accepted_events += 24

        def stop(self) -> None:
            runtime.running = False

        def snapshot(self) -> DeviceStreamRuntime:
            return runtime

    monkeypatch.setattr(simulation, "runtime", FakeStream())
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
    assert started.json()["accepted_events"] == 24
    assert advanced.json()["cycle"] == 2
    assert advanced.json()["accepted_events"] == 48
    assert stopped.json()["running"] is False
