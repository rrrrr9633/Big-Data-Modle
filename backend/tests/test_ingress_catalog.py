from app.api.v1 import ingress
from app.main import app
from fastapi.testclient import TestClient


def test_ingress_catalog_endpoint_exposes_topic_contract_and_catalog(monkeypatch) -> None:
    monkeypatch.setattr(
        ingress,
        "build_ingress_catalog",
        lambda _db: {
            "mqtt_topic": "factory/+/workshop/+/line/+/machine/+/telemetry",
            "payload_schema": ["event_id", "device_code", "point_code"],
            "devices": [{"device_code": "CNC-001", "sensor_points": []}],
            "production_gaps": [],
        },
    )

    response = TestClient(app).get("/api/v1/ingress/catalog")

    assert response.status_code == 200
    assert response.json()["mqtt_topic"].startswith("factory/")
    assert response.json()["devices"][0]["device_code"] == "CNC-001"


def test_build_ingress_catalog_reports_devices_without_sensor_points(monkeypatch) -> None:
    monkeypatch.setattr(
        ingress,
        "fetch_devices",
        lambda _db: [
            {"device_code": "CNC-001", "sensor_points": [{"sensor_code": "torque"}]},
            {"device_code": "CNC-002", "sensor_points": []},
        ],
    )

    catalog = ingress.build_ingress_catalog(object())

    assert catalog["payload_schema"] == [
        "event_id",
        "device_code",
        "point_code",
        "value",
        "unit",
        "quality",
        "ts",
        "gateway_id",
    ]
    assert "CNC-002 未配置传感器点位" in catalog["production_gaps"]


def test_build_ingress_catalog_includes_edge_gateway_mapping(monkeypatch) -> None:
    monkeypatch.setattr(
        ingress,
        "fetch_devices",
        lambda _db: [
            {
                "device_code": "CNC-001",
                "factory": "factory-a",
                "workshop": "machining",
                "production_line": "line-1",
                "sensor_points": [
                    {
                        "sensor_code": "spindle_temperature",
                        "sensor_name": "主轴温度",
                        "unit": "C",
                        "sampling_frequency": "1s",
                        "protocol": "opcua",
                        "source_address": "ns=2;s=CNC001.Spindle.Temp",
                        "feature_name": "spindle_temperature_mean",
                        "quality_rule": "quality=0 when OPC UA status is bad",
                        "min_value": 0,
                        "max_value": 120,
                        "enabled": True,
                    }
                ],
            }
        ],
    )

    catalog = ingress.build_ingress_catalog(object())

    mapping = catalog["edge_gateway_mappings"][0]
    assert mapping["device_code"] == "CNC-001"
    assert (
        mapping["mqtt_topic"]
        == "factory/factory-a/workshop/machining/line/line-1/machine/CNC-001/telemetry"
    )
    assert mapping["points"][0]["point_code"] == "spindle_temperature"
    assert mapping["points"][0]["protocol"] == "opcua"
    assert mapping["points"][0]["source_address"] == "ns=2;s=CNC001.Spindle.Temp"
    assert mapping["points"][0]["feature_name"] == "spindle_temperature_mean"
    assert mapping["points"][0]["target_payload"]["unit"] == "C"
    assert catalog["edge_adapter_contract"]["publish_mode"] == "single-point-json"


def test_edge_config_endpoint_exports_adapter_configs(monkeypatch) -> None:
    monkeypatch.setattr(
        ingress,
        "fetch_devices",
        lambda _db: [
            {
                "device_code": "CNC-001",
                "factory": "factory-a",
                "workshop": "machining",
                "production_line": "line-1",
                "sensor_points": [
                    {
                        "sensor_code": "spindle_temperature",
                        "sensor_name": "主轴温度",
                        "unit": "C",
                        "sampling_frequency": "1s",
                        "protocol": "modbus",
                        "source_address": "holding:40001:int16:scale=0.1",
                        "feature_name": "spindle_temperature_mean",
                        "quality_rule": "quality=0 when Modbus read fails",
                        "min_value": 0,
                        "max_value": 120,
                        "enabled": True,
                    }
                ],
            }
        ],
    )

    response = TestClient(app).get("/api/v1/ingress/edge-configs")

    assert response.status_code == 200
    body = response.json()
    assert body["config_format"] == "edge-adapter-config.v1"
    assert body["configs"][0]["gateway"]["gateway_id"] == "gateway-cnc-001"
    assert body["configs"][0]["points"][0]["protocol"] == "modbus"
    assert body["configs"][0]["points"][0]["source_address"] == "holding:40001:int16:scale=0.1"


def test_edge_config_simulation_returns_telemetry_events() -> None:
    config = {
        "gateway": {
            "gateway_id": "gateway-cnc-001",
            "factory": "factory-a",
            "workshop": "machining",
            "production_line": "line-1",
            "mqtt_topic": (
                "factory/factory-a/workshop/machining/line/line-1/"
                "machine/CNC-001/telemetry"
            ),
            "publish_mode": "mqtt",
        },
        "points": [
            {
                "device_code": "CNC-001",
                "point_code": "spindle_temperature",
                "point_name": "主轴温度",
                "unit": "C",
                "sampling_frequency": "1s",
                "protocol": "modbus",
                "source_address": "holding:40001:int16:scale=0.1",
                "feature_name": "spindle_temperature_mean",
                "quality_rule": "quality=0 when Modbus read fails",
                "min_value": 0,
                "max_value": 120,
                "enabled": True,
                "protocol_options": {"address": "holding:40001:int16:scale=0.1"},
            }
        ],
        "payload_schema": [
            "event_id",
            "device_code",
            "point_code",
            "value",
            "unit",
            "quality",
            "ts",
            "gateway_id",
            "source_topic",
        ],
        "runtime_contract": {
            "adapter_role": "read industrial protocol points and publish TelemetryEvent",
            "output_event": "app.ingestion.schemas.TelemetryEvent",
        },
    }

    response = TestClient(app).post("/api/v1/ingress/edge-configs/simulate", json=config)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "simulated"
    assert body["publish_result"]["mode"] == "dry-run"
    assert body["publish_result"]["accepted_events"] == 1
    assert body["events"][0]["device_code"] == "CNC-001"
    assert body["events"][0]["point_code"] == "spindle_temperature"
    assert body["events"][0]["gateway_id"] == "gateway-cnc-001"
    assert body["events"][0]["source_topic"] == config["gateway"]["mqtt_topic"]
    assert body["publish_result"]["event_ids"] == [body["events"][0]["event_id"]]
