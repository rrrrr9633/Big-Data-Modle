from app.api.v1 import devices
from app.core.database import get_db
from app.main import app
from fastapi.testclient import TestClient


class FakeDb:
    def commit(self) -> None:
        return None


def _override_db():
    return FakeDb()


def test_create_device_endpoint_upserts_device(monkeypatch) -> None:
    calls: dict[str, object] = {}

    monkeypatch.setattr(devices, "ensure_prediction_model_schema", lambda _db: None)
    monkeypatch.setattr(devices, "fetch_devices", lambda _db: [{"device_code": "CNC-001"}])

    def fake_upsert(_db, **payload):
        calls.update(payload)

    monkeypatch.setattr(devices, "upsert_device", fake_upsert)
    monkeypatch.setattr(devices, "insert_audit_log", lambda _db, **_payload: None)
    app.dependency_overrides[get_db] = _override_db
    try:
        response = TestClient(app).post(
            "/api/v1/devices",
            json={
                "device_code": "CNC-001",
                "device_name": "一号数控机床",
                "device_type": "CNC",
                "factory": "factory-a",
                "workshop": "machining",
                "production_line": "line-1",
                "status": "online",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["device_code"] == "CNC-001"
    assert calls["device_code"] == "CNC-001"
    assert calls["workshop"] == "machining"


def test_upsert_and_disable_sensor_point_endpoints(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(devices, "ensure_prediction_model_schema", lambda _db: None)
    monkeypatch.setattr(devices, "fetch_devices", lambda _db: [])
    monkeypatch.setattr(
        devices, "upsert_sensor_point", lambda _db, **payload: calls.append(("upsert", payload))
    )
    monkeypatch.setattr(
        devices, "disable_sensor_point", lambda _db, **payload: calls.append(("disable", payload))
    )
    monkeypatch.setattr(devices, "insert_audit_log", lambda _db, **_payload: None)
    app.dependency_overrides[get_db] = _override_db
    try:
        upsert_response = TestClient(app).put(
            "/api/v1/devices/CNC-001/points/spindle_temperature",
            json={
                "sensor_name": "主轴温度",
                "unit": "C",
                "sampling_frequency": "1s",
                "protocol": "opcua",
                "source_address": "ns=2;s=CNC001.Spindle.Temp",
                "protocol_options": {"endpoint": "opc.tcp://192.168.10.6:4840"},
                "feature_name": "spindle_temperature_mean",
                "quality_rule": "quality=0 when OPC UA status is bad",
                "min_value": 0,
                "max_value": 120,
                "enabled": True,
            },
        )
        disable_response = TestClient(app).delete(
            "/api/v1/devices/CNC-001/points/spindle_temperature"
        )
    finally:
        app.dependency_overrides.clear()

    assert upsert_response.status_code == 200
    assert disable_response.status_code == 200
    assert calls[0] == (
        "upsert",
        {
            "device_code": "CNC-001",
            "sensor_code": "spindle_temperature",
            "sensor_name": "主轴温度",
            "unit": "C",
            "sampling_frequency": "1s",
            "protocol": "opcua",
            "source_address": "ns=2;s=CNC001.Spindle.Temp",
            "protocol_options": {"endpoint": "opc.tcp://192.168.10.6:4840"},
            "feature_name": "spindle_temperature_mean",
            "quality_rule": "quality=0 when OPC UA status is bad",
            "min_value": 0.0,
            "max_value": 120.0,
            "enabled": True,
        },
    )
    assert calls[1] == (
        "disable",
        {"device_code": "CNC-001", "sensor_code": "spindle_temperature"},
    )


def test_submit_master_data_change_request_does_not_apply_immediately(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(devices, "ensure_prediction_model_schema", lambda _db: None)
    monkeypatch.setattr(
        devices,
        "insert_master_data_change_request",
        lambda _db, **payload: calls.append(("request", payload)) or 42,
    )
    monkeypatch.setattr(
        devices,
        "upsert_sensor_point",
        lambda _db, **payload: calls.append(("upsert", payload)),
    )
    monkeypatch.setattr(devices, "insert_audit_log", lambda _db, **_payload: None)
    app.dependency_overrides[get_db] = _override_db
    try:
        response = TestClient(app).post(
            "/api/v1/devices/change-requests",
            json={
                "entity_type": "sensor_point",
                "operation": "upsert",
                "device_code": "CNC-001",
                "sensor_code": "spindle_temperature",
                "payload": {
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
                },
                "reason": "新增真实 OPC UA 点位映射",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["change_request_id"] == 42
    assert response.json()["status"] == "pending"
    assert calls[0][0] == "request"
    assert all(name != "upsert" for name, _payload in calls)
    assert "模型特征映射变更" in response.json()["impact"]["risk_items"]


def test_approve_master_data_change_request_applies_payload(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    change_request = {
        "id": 42,
        "status": "pending",
        "entity_type": "sensor_point",
        "operation": "upsert",
        "device_code": "CNC-001",
        "sensor_code": "spindle_temperature",
        "payload": {
            "sensor_name": "主轴温度",
            "unit": "C",
            "sampling_frequency": "1s",
            "protocol": "opcua",
            "source_address": "ns=2;s=CNC001.Spindle.Temp",
            "protocol_options": {"endpoint": "opc.tcp://192.168.10.6:4840"},
            "feature_name": "spindle_temperature_mean",
            "quality_rule": "quality=0 when OPC UA status is bad",
            "min_value": 0,
            "max_value": 120,
            "enabled": True,
        },
        "impact": {"risk_items": ["模型特征映射变更"]},
    }

    monkeypatch.setattr(devices, "ensure_prediction_model_schema", lambda _db: None)
    monkeypatch.setattr(
        devices,
        "fetch_master_data_change_request",
        lambda _db, _id: change_request,
    )
    monkeypatch.setattr(
        devices, "upsert_sensor_point", lambda _db, **payload: calls.append(("upsert", payload))
    )
    monkeypatch.setattr(
        devices,
        "mark_master_data_change_request_decision",
        lambda _db, **payload: calls.append(("decision", payload)),
    )
    monkeypatch.setattr(
        devices,
        "insert_master_data_version",
        lambda _db, **payload: calls.append(("version", payload)) or 7,
    )
    monkeypatch.setattr(devices, "insert_audit_log", lambda _db, **_payload: None)
    app.dependency_overrides[get_db] = _override_db
    try:
        response = TestClient(app).post(
            "/api/v1/devices/change-requests/42/decision",
            json={"decision": "approve", "comment": "确认上线"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "approved", "change_request_id": 42, "version_id": 7}
    assert calls[0] == (
        "upsert",
        {
            "device_code": "CNC-001",
            "sensor_code": "spindle_temperature",
            "sensor_name": "主轴温度",
            "unit": "C",
            "sampling_frequency": "1s",
            "protocol": "opcua",
            "source_address": "ns=2;s=CNC001.Spindle.Temp",
            "protocol_options": {"endpoint": "opc.tcp://192.168.10.6:4840"},
            "feature_name": "spindle_temperature_mean",
            "quality_rule": "quality=0 when OPC UA status is bad",
            "min_value": 0,
            "max_value": 120,
            "enabled": True,
        },
    )
    assert calls[1][0] == "version"
    assert calls[2][0] == "decision"
