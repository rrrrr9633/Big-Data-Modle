import random
from types import SimpleNamespace

from app.core.config import settings
from app.edge.device_stream import DeviceStreamConfig, DeviceStreamSimulator
from app.inference.local_gateway import LocalInferenceGateway
from app.ingestion.http_schemas import TelemetryPayloadIn
from app.ingestion.local_adapter import accept_payload_locally
from app.realtime.device_snapshot import read_all_device_snapshots


def test_local_transport_emits_without_touching_mqtt() -> None:
    mqtt_calls: list[object] = []

    def unavailable_mqtt(*args, **kwargs):
        mqtt_calls.append((args, kwargs))
        raise ConnectionError("MQTT unavailable")

    stream = DeviceStreamSimulator(
        publishers={"local": accept_payload_locally, "mqtt": unavailable_mqtt},
        provisioner=lambda _config, _devices: None,
        archive_observer=None,
    )
    try:
        state = stream.start(
            DeviceStreamConfig(device_count=2, interval_seconds=60, transport="local")
        )
        snapshots = read_all_device_snapshots()
    finally:
        stream.stop()

    assert state.running is True
    assert state.config.transport == "local"
    assert state.cycle == 1
    assert state.accepted_events == 16
    assert mqtt_calls == []
    assert len(snapshots) == 2
    assert all(len(snapshot["points"]) == 8 for snapshot in snapshots)
    assert read_all_device_snapshots() == []


def test_sudden_fault_selects_exactly_two_random_devices_and_progresses() -> None:
    stream = DeviceStreamSimulator(
        scenario_rng=random.Random(11),
        provisioner=lambda _config, _devices: None,
        archive_observer=None,
    )
    try:
        state = stream.start(DeviceStreamConfig(device_count=6, mode="sudden_fault", interval_seconds=60))
        assert len(state.scenario_devices) == 2
        first = {snapshot["device_code"]: snapshot for snapshot in read_all_device_snapshots()}
        for _ in range(5):
            stream.emit_cycle()
        later = {snapshot["device_code"]: snapshot for snapshot in read_all_device_snapshots()}
    finally:
        stream.stop()

    affected = set(state.scenario_devices)
    unaffected = set(first) - affected
    assert unaffected
    assert all(
        all(point.get("status") == "good" for point in first[code]["points"].values())
        for code in unaffected
    )
    assert all(
        any(point.get("status") in {"fault_emerging", "sudden_fault"} for point in later[code]["points"].values())
        for code in affected
    )


def test_local_adapter_passes_complete_payload_to_in_process_inference() -> None:
    received: list[object] = []

    result = accept_payload_locally(
        {
            "device_code": "CNC-L01-001",
            "device_name": "数控机床 CNC-L01-001",
            "device_type": "CNC",
            "readings": [
                {
                    "sensor_code": "air_temperature",
                    "value": 300.0,
                    "unit": "K",
                    "quality": 1.0,
                    "status": "good",
                }
            ],
        },
        inference_runner=lambda payload: received.append(payload) or {"prediction_created": True},
    )

    assert len(received) == 1
    assert result["prediction_created"] is True
    assert result["next_stages"] == ["in_process_snapshot", "in_process_inference"]


def test_local_inference_gateway_builds_model_window_without_middleware(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def run_inference(feature_event, *, forced_failure: bool):
        captured["event"] = feature_event
        captured["forced_failure"] = forced_failure
        return SimpleNamespace(prediction_id=17, warning_created=True)

    monkeypatch.setattr(settings, "local_inference_enabled", True)
    gateway = LocalInferenceGateway(inference_runner=run_inference)
    payload = TelemetryPayloadIn.model_validate(
        {
            "device_code": "CNC-L01-001",
            "device_name": "数控机床 CNC-L01-001",
            "device_type": "CNC",
            "readings": [
                {"sensor_code": "air_temperature", "value": 300, "unit": "K"},
                {"sensor_code": "process_temperature", "value": 310, "unit": "K"},
                {"sensor_code": "rotational_speed", "value": 1200, "unit": "rpm"},
                {"sensor_code": "torque", "value": 40, "unit": "Nm"},
                {"sensor_code": "tool_wear", "value": 120, "unit": "min", "status": "sudden_fault"},
            ],
        }
    )

    result = gateway.infer(payload)

    assert result == {
        "prediction_created": True,
        "prediction_id": 17,
        "warning_created": True,
        "inference_status": "completed",
    }
    assert captured["event"].source == "local-direct"
    assert captured["forced_failure"] is True
