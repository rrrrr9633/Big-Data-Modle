import json
from datetime import UTC, datetime
from pathlib import Path

from app.api.v1 import telemetry
from app.api.v1.telemetry import TelemetryPayloadIn, router
from app.ingestion.http_adapter import publish_payload_to_raw_topic
from app.ingestion.http_schemas import parse_telemetry_payload
from app.ingestion.mqtt_simulator import build_device_telemetry_topic, publish_payload_to_mqtt
from app.repositories.maintenance_repository import readings_from_rows
from app.streams.kafka_client import parse_kafka_api_version
from app.streams import runtime


def test_telemetry_payload_accepts_device_readings() -> None:
    payload = TelemetryPayloadIn(
        device_code="CNC-001",
        device_name="数控机床 001",
        device_type="CNC",
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
        readings=[
            {"sensor_code": "air_temperature", "value": 298.2, "unit": "K"},
            {"sensor_code": "torque", "value": 42.3, "unit": "Nm"},
        ],
    )

    assert payload.device_code == "CNC-001"
    assert payload.readings[0].sensor_code == "air_temperature"


def test_telemetry_router_is_registered() -> None:
    paths = {route.path for route in router.routes if hasattr(route, "path")}

    assert "/readings" in paths
    assert "/mqtt/simulate" in paths
    assert "/ws/readings" in paths


def test_recent_sensor_rows_are_rehydrated_as_pipeline_readings() -> None:
    rows = [
        {
            "device_code": "CNC-001",
            "sensor_code": "torque",
            "recorded_at": datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            "value": 40.0,
            "unit": "Nm",
        },
        {
            "device_code": "CNC-001",
            "sensor_code": "torque",
            "recorded_at": datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            "value": 44.0,
            "unit": "Nm",
        },
    ]

    readings = readings_from_rows(rows)

    assert [reading.device_id for reading in readings] == ["CNC-001", "CNC-001"]
    assert [reading.value for reading in readings] == [40.0, 44.0]


def test_telemetry_endpoint_accepts_payload_to_kafka_raw(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_publish(payload: TelemetryPayloadIn, *, protocol: str) -> dict[str, object]:
        calls["payload"] = payload
        calls["protocol"] = protocol
        return {
            "status": "accepted",
            "mode": "async_raw_ingestion",
            "device_code": payload.device_code,
            "accepted_events": len(payload.readings),
            "raw_topic": "factory.telemetry.raw",
            "next_stages": ["factory.telemetry.cleaned", "factory.features.windowed"],
        }

    monkeypatch.setattr(telemetry, "publish_payload_to_raw_topic", fake_publish)

    response = telemetry.ingest_realtime_readings(
        TelemetryPayloadIn(
            device_code="CNC-001",
            device_name="数控机床 001",
            device_type="CNC",
            recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
            readings=[
                {"sensor_code": "air_temperature", "value": 298.2, "unit": "K"},
                {"sensor_code": "torque", "value": 42.3, "unit": "Nm"},
            ],
        )
    )

    payload = calls["payload"]
    assert calls["protocol"] == "http"
    assert payload.device_code == "CNC-001"
    assert response["status"] == "accepted"
    assert response["mode"] == "async_raw_ingestion"
    assert response["accepted_events"] == 2
    assert response["raw_topic"] == "factory.telemetry.raw"


def test_parse_telemetry_payload_accepts_json_bytes() -> None:
    raw = {
        "device_code": "CNC-001",
        "device_name": "数控机床 001",
        "device_type": "CNC",
        "readings": [{"sensor_code": "torque", "value": 42.3, "unit": "Nm"}],
    }
    payload = parse_telemetry_payload(json.dumps(raw).encode())

    assert payload.device_code == "CNC-001"
    assert payload.readings[0].value == 42.3


def test_publish_payload_to_raw_topic_splits_device_payload_into_point_events(monkeypatch) -> None:
    sent: list[tuple[str, bytes, str | None]] = []

    class FakeProducer:
        def send(self, topic: str, payload: bytes, *, key: str | None = None) -> None:
            sent.append((topic, payload, key))

        def close(self) -> None:
            sent.append(("closed", b"", None))

    monkeypatch.setattr("app.ingestion.http_adapter.KafkaJsonProducer", FakeProducer)

    result = publish_payload_to_raw_topic(
        TelemetryPayloadIn(
            device_code="CNC-001",
            device_name="数控机床 001",
            device_type="CNC",
            recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
            readings=[
                {"sensor_code": "air_temperature", "value": 298.2, "unit": "K"},
                {"sensor_code": "torque", "value": 42.3, "unit": "Nm"},
            ],
        ),
        protocol="http",
    )

    first_event = json.loads(sent[0][1].decode("utf-8"))
    assert result["status"] == "accepted"
    assert result["mode"] == "async_raw_ingestion"
    assert result["accepted_events"] == 2
    assert [item[0] for item in sent] == [
        "factory.telemetry.raw",
        "factory.telemetry.raw",
        "closed",
    ]
    assert [item[2] for item in sent[:2]] == ["CNC-001", "CNC-001"]
    assert first_event["device_code"] == "CNC-001"
    assert first_event["point_code"] == "air_temperature"
    assert first_event["gateway_id"] == "http"


def test_publish_payload_to_mqtt_splits_device_payload_into_point_events(monkeypatch) -> None:
    published: list[tuple[str, str, str, int]] = []

    def fake_publish_single(topic: str, *, payload: str, hostname: str, port: int) -> None:
        published.append((topic, payload, hostname, port))

    monkeypatch.setattr("app.ingestion.mqtt_simulator.settings.mqtt_broker_host", "127.0.0.1")
    monkeypatch.setattr("app.ingestion.mqtt_simulator.settings.mqtt_broker_port", 1883)
    monkeypatch.setattr("paho.mqtt.publish.single", fake_publish_single)

    result = publish_payload_to_mqtt(
        TelemetryPayloadIn(
            device_code="CNC-001",
            device_name="数控机床 001",
            device_type="CNC",
            recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
            readings=[
                {"sensor_code": "air_temperature", "value": 298.2, "unit": "K"},
                {"sensor_code": "torque", "value": 42.3, "unit": "Nm"},
            ],
        )
    )

    first_event = json.loads(published[0][1])
    assert result["status"] == "accepted"
    assert result["mode"] == "mqtt_emqx_ingestion"
    assert result["accepted_events"] == 2
    assert result["mqtt_topic"] == (
        "factory/default/workshop/default/line/default/machine/CNC-001/telemetry"
    )
    assert [item[0] for item in published] == [result["mqtt_topic"], result["mqtt_topic"]]
    assert first_event["device_code"] == "CNC-001"
    assert first_event["point_code"] == "air_temperature"
    assert first_event["gateway_id"] == "frontend-simulator"
    assert published[0][2:] == ("127.0.0.1", 1883)


def test_mqtt_device_topic_matches_backend_subscription_pattern() -> None:
    assert (
        build_device_telemetry_topic("CNC-001")
        == "factory/default/workshop/default/line/default/machine/CNC-001/telemetry"
    )


def test_kafka_api_version_is_parsed_for_kafka_python() -> None:
    assert parse_kafka_api_version("4.0") == (4, 0)
    assert parse_kafka_api_version("3.7.1") == (3, 7, 1)


def test_stream_runtime_starts_only_enabled_async_stages(monkeypatch) -> None:
    started: list[str] = []
    stopped: list[str] = []

    def starter(name: str):
        def _start():
            started.append(name)
            return lambda: stopped.append(name)

        return _start

    monkeypatch.setattr(runtime.settings, "mqtt_to_kafka_enabled", True)
    monkeypatch.setattr(runtime.settings, "raw_telemetry_consumer_enabled", True)
    monkeypatch.setattr(runtime.settings, "cleaned_telemetry_consumer_enabled", False)
    monkeypatch.setattr(runtime.settings, "feature_consumer_enabled", True)
    monkeypatch.setattr(runtime.settings, "inference_consumer_enabled", False)
    monkeypatch.setattr(runtime, "start_mqtt_to_kafka", starter("mqtt-to-kafka"))
    monkeypatch.setattr(runtime, "start_raw_telemetry_consumer", starter("raw-telemetry"))
    monkeypatch.setattr(runtime, "start_cleaned_telemetry_consumer", starter("cleaned-telemetry"))
    monkeypatch.setattr(runtime, "start_feature_consumer", starter("feature-window"))
    monkeypatch.setattr(runtime, "start_inference_consumer", starter("async-inference"))

    handles = runtime.start_stream_runtime()
    runtime.stop_stream_runtime(handles)

    assert started == ["mqtt-to-kafka", "raw-telemetry", "feature-window"]
    assert stopped == ["mqtt-to-kafka", "raw-telemetry", "feature-window"]


def test_legacy_sync_telemetry_pipeline_is_removed() -> None:
    app_dir = Path(__file__).resolve().parents[1] / "app"

    assert not (app_dir / "services" / "telemetry_ingestion.py").exists()
    assert not (app_dir / "services" / "prediction_pipeline.py").exists()
