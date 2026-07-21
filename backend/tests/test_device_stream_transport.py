import random

from app.edge.device_stream import DeviceStreamConfig, DeviceStreamSimulator
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
