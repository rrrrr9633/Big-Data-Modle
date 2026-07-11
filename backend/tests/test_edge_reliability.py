from datetime import UTC, datetime, timedelta

import pytest
from app.edge.adapters.cnc import CncAdapter, CncDriverUnavailable
from app.edge.contracts import EdgeGatewayConfig, EdgePointBinding
from app.edge.runner import EdgeRunner
from app.edge.runtime import collect_live_once
from app.edge.simulation import IndustrialDeviceSimulator
from app.edge.spool import EdgeSpool
from app.ingestion.schemas import TelemetryEvent


def _event(event_id: str, offset: int = 0) -> TelemetryEvent:
    return TelemetryEvent(
        event_id=event_id,
        device_code="CNC-001",
        point_code="spindle_temperature",
        value=42.0,
        unit="C",
        ts=datetime(2026, 7, 10, tzinfo=UTC) + timedelta(seconds=offset),
    )


def _gateway() -> EdgeGatewayConfig:
    return EdgeGatewayConfig(
        gateway_id="gateway-cnc-001",
        mqtt_topic="factory/a/workshop/b/line/c/machine/CNC-001/telemetry",
    )


def test_edge_spool_replays_pending_events_after_failure_in_order(tmp_path) -> None:
    spool = EdgeSpool(tmp_path / "edge-spool.db")
    spool.enqueue([_event("first"), _event("second", 1)])
    sent: list[str] = []

    with pytest.raises(ConnectionError):
        spool.flush(lambda _event: (_ for _ in ()).throw(ConnectionError("offline")))

    assert spool.pending_count() == 2
    assert spool.flush(lambda event: sent.append(event.event_id)) == 2
    assert sent == ["first", "second"]
    assert spool.pending_count() == 0


def test_edge_runner_persists_cycle_before_publish_and_replays_it_on_next_cycle(tmp_path) -> None:
    config = type("Config", (), {"gateway": _gateway()})()
    attempts = 0
    sent: list[str] = []

    def publisher(events, _gateway):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("broker unavailable")
        sent.extend(event.event_id for event in events)
        return {"status": "accepted"}

    runner = EdgeRunner(
        config,
        collector=lambda _config: [_event("cycle-1")],
        publisher=publisher,
        spool=EdgeSpool(tmp_path / "runner-spool.db"),
    )

    with pytest.raises(ConnectionError):
        runner.run_once()
    runner.run_once()

    assert sent == ["cycle-1"]
    assert runner.pending_event_count == 0


def test_unavailable_cnc_vendor_is_never_reported_as_a_simulated_live_read() -> None:
    binding = EdgePointBinding(
        device_code="CNC-001",
        point_code="spindle_load",
        protocol="cnc",
        source_address="PMC:R0100",
        protocol_options={"vendor": "fanuc"},
    )

    with pytest.raises(CncDriverUnavailable, match="driver_unavailable: fanuc"):
        CncAdapter().read(binding)


def test_live_collection_emits_bad_quality_event_when_one_protocol_point_fails(monkeypatch) -> None:
    binding = EdgePointBinding(
        device_code="CNC-001",
        point_code="spindle_load",
        protocol="cnc",
        source_address="PMC:R0100",
        protocol_options={"vendor": "fanuc"},
    )
    config = type("Config", (), {"gateway": _gateway(), "points": [binding]})()
    monkeypatch.setattr("app.edge.runtime.get_adapter", lambda _protocol: CncAdapter())

    event = collect_live_once(config)[0]

    assert event.value == 0.0
    assert event.quality == 0.0


def test_industrial_simulator_models_degradation_and_quality_faults_deterministically() -> None:
    simulator = IndustrialDeviceSimulator(device_code="SIM-CNC-001", seed=7, mode="degrading")

    early = simulator.next_cycle(cycle=1)
    late = simulator.next_cycle(cycle=120)
    fault = IndustrialDeviceSimulator(
        device_code="SIM-CNC-002", seed=7, mode="sensor_stuck"
    ).next_cycle(cycle=3)

    assert late["tool_wear"].value > early["tool_wear"].value
    assert late["spindle_temperature"].value > early["spindle_temperature"].value
    assert fault["spindle_temperature"].quality < 1.0
    assert fault["spindle_temperature"].raw_status == "sensor_stuck"
