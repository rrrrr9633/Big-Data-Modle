import asyncio
from pathlib import Path

import pytest
from app import main as app_main
from app.edge.device_stream import DeviceStreamConfig, DeviceStreamRuntime
from app.models.registry import ActiveModelState
from app.services import simulation_runtime


def test_complete_simulation_requires_every_real_stream_stage(monkeypatch) -> None:
    monkeypatch.setattr(simulation_runtime.settings, "mqtt_to_kafka_enabled", True)
    monkeypatch.setattr(simulation_runtime.settings, "raw_telemetry_consumer_enabled", True)
    monkeypatch.setattr(simulation_runtime.settings, "cleaned_telemetry_consumer_enabled", False)
    monkeypatch.setattr(simulation_runtime.settings, "feature_consumer_enabled", True)
    monkeypatch.setattr(simulation_runtime.settings, "inference_consumer_enabled", True)

    with pytest.raises(RuntimeError, match="CLEANED_TELEMETRY_CONSUMER_ENABLED"):
        simulation_runtime.start_complete_simulation()


def test_complete_simulation_bootstraps_model_before_mqtt_source(monkeypatch) -> None:
    for name in (
        "mqtt_to_kafka_enabled",
        "raw_telemetry_consumer_enabled",
        "cleaned_telemetry_consumer_enabled",
        "feature_consumer_enabled",
        "inference_consumer_enabled",
    ):
        monkeypatch.setattr(simulation_runtime.settings, name, True)
    monkeypatch.setattr(simulation_runtime.settings, "simulation_device_count", 3)
    monkeypatch.setattr(simulation_runtime.settings, "simulation_mode", "degrading")
    monkeypatch.setattr(simulation_runtime.settings, "simulation_interval_seconds", 0.5)

    calls: list[str] = []

    class FakeRuntime:
        def start(self, config: DeviceStreamConfig) -> DeviceStreamRuntime:
            calls.append("mqtt-source")
            return DeviceStreamRuntime(
                running=True,
                config=config,
                device_codes=["A", "B", "C"],
            )

    monkeypatch.setattr(
        simulation_runtime,
        "ensure_simulation_model",
        lambda: calls.append("model"),
    )
    monkeypatch.setattr(simulation_runtime, "runtime", FakeRuntime())

    state = simulation_runtime.start_complete_simulation()

    assert calls == ["model", "mqtt-source"]
    assert state.running is True
    assert state.config.device_count == 3
    assert state.config.interval_seconds == 0.5


def test_missing_model_is_trained_from_configured_dataset(monkeypatch, tmp_path: Path) -> None:
    dataset = tmp_path / "ai4i.csv"
    dataset.write_text(
        "UDI,Product ID,Type,Air temperature [K],Process temperature [K],"
        "Rotational speed [rpm],Torque [Nm],Tool wear [min],Machine failure\n"
        "1,M10001,M,298.1,308.6,1551,42.8,17,0\n",
        encoding="utf-8",
    )
    unavailable = ActiveModelState(available=False, path=None)
    available = ActiveModelState(available=True, path="active.pkl")
    states = iter([unavailable, available])
    monkeypatch.setattr(simulation_runtime, "get_active_model_state", lambda: next(states))
    monkeypatch.setattr(simulation_runtime.settings, "simulation_model_bootstrap_enabled", True)
    monkeypatch.setattr(simulation_runtime.settings, "simulation_model_dataset_path", str(dataset))

    trained_rows: list[list[dict[str, str]]] = []

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def commit(self) -> None:
            pass

    monkeypatch.setattr(simulation_runtime, "SessionLocal", FakeSession)
    monkeypatch.setattr(
        simulation_runtime,
        "train_and_register_ai4i_model",
        lambda _db, rows: trained_rows.append(rows),
    )

    state = simulation_runtime.ensure_simulation_model()

    assert state.available is True
    assert len(trained_rows) == 1
    assert trained_rows[0][0]["Product ID"] == "M10001"


def test_lifespan_orders_model_streams_source_and_shutdown(monkeypatch) -> None:
    calls: list[str] = []
    state = DeviceStreamRuntime(
        running=True,
        config=DeviceStreamConfig(device_count=2),
        device_codes=["A", "B"],
    )

    class FakeSimulationRuntime:
        def stop(self) -> None:
            calls.append("stop-source")

    async def no_delay(_seconds: float) -> None:
        calls.append("delay")

    monkeypatch.setattr(app_main.settings, "simulation_auto_start", True)
    monkeypatch.setattr(app_main, "ensure_simulation_model", lambda: calls.append("model"))
    monkeypatch.setattr(
        app_main,
        "start_stream_runtime",
        lambda *, require_all: calls.append(f"streams:{require_all}") or ["stream-handle"],
    )
    monkeypatch.setattr(
        app_main,
        "start_complete_simulation",
        lambda: calls.append("source") or state,
    )
    monkeypatch.setattr(
        app_main,
        "stop_stream_runtime",
        lambda _handles: calls.append("stop-streams"),
    )
    monkeypatch.setattr(app_main, "simulation_runtime", FakeSimulationRuntime())
    monkeypatch.setattr(app_main.asyncio, "sleep", no_delay)

    async def exercise() -> None:
        async with app_main.lifespan(app_main.app):
            calls.append("serving")

    asyncio.run(exercise())

    assert calls == [
        "model",
        "streams:True",
        "delay",
        "source",
        "serving",
        "stop-source",
        "stop-streams",
    ]
