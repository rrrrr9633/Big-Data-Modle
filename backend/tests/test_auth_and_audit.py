from app.api.v1 import devices, models, warnings
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from fastapi.testclient import TestClient


class FakeDb:
    def commit(self) -> None:
        return None


def _override_db():
    return FakeDb()


def test_login_returns_token_and_me_returns_current_user(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_admin_username", "admin")
    monkeypatch.setattr(settings, "auth_admin_password", "secret")
    monkeypatch.setattr(settings, "auth_token_secret", "test-secret")

    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"})

    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["username"] == "admin"
    assert me.json()["role"] == "admin"


def test_protected_device_write_requires_admin_token_when_auth_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)

    response = TestClient(app).post(
        "/api/v1/devices",
        json={"device_code": "CNC-001", "device_name": "一号数控机床"},
    )

    assert response.status_code == 401


def test_device_write_with_admin_token_records_audit(monkeypatch) -> None:
    calls: dict[str, object] = {}
    audit_events: list[dict[str, object]] = []
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_admin_username", "admin")
    monkeypatch.setattr(settings, "auth_admin_password", "secret")
    monkeypatch.setattr(settings, "auth_token_secret", "test-secret")
    monkeypatch.setattr(devices, "ensure_prediction_model_schema", lambda _db: None)

    def fake_upsert(_db, **payload):
        calls.update(payload)

    monkeypatch.setattr(devices, "upsert_device", fake_upsert)
    monkeypatch.setattr(
        devices, "insert_audit_log", lambda _db, **payload: audit_events.append(payload)
    )
    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    try:
        token = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret"},
        ).json()["access_token"]
        response = client.post(
            "/api/v1/devices",
            headers={"Authorization": f"Bearer {token}"},
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
    assert calls["device_code"] == "CNC-001"
    assert audit_events[0]["actor"] == "admin"
    assert audit_events[0]["action"] == "upsert_device"
    assert audit_events[0]["resource"] == "device:CNC-001"


def test_warning_status_update_requires_admin_token_when_auth_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)

    response = TestClient(app).post(
        "/api/v1/warnings/1/status",
        json={"status": "acknowledged", "operator": "ops"},
    )

    assert response.status_code == 401


def test_model_reset_requires_admin_token_when_auth_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)

    response = TestClient(app).delete("/api/v1/models/active")

    assert response.status_code == 401


def test_warning_status_update_with_admin_token_records_audit(monkeypatch) -> None:
    audit_events: list[dict[str, object]] = []
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_admin_username", "admin")
    monkeypatch.setattr(settings, "auth_admin_password", "secret")
    monkeypatch.setattr(settings, "auth_token_secret", "test-secret")
    monkeypatch.setattr(warnings, "ensure_prediction_model_schema", lambda _db: None)
    monkeypatch.setattr(
        warnings, "fetch_warning_by_id", lambda _db, _id: {"id": _id, "status": "new"}
    )
    monkeypatch.setattr(warnings, "transition_warning_status", lambda _db, **_payload: None)
    monkeypatch.setattr(
        warnings, "insert_audit_log", lambda _db, **payload: audit_events.append(payload)
    )
    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    try:
        token = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret"},
        ).json()["access_token"]
        response = client.post(
            "/api/v1/warnings/1/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "acknowledged", "operator": "ops"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert audit_events[0]["action"] == "transition_warning"
    assert audit_events[0]["resource"] == "warning:1"


def test_model_reset_with_admin_token_records_audit(monkeypatch) -> None:
    audit_events: list[dict[str, object]] = []
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_admin_username", "admin")
    monkeypatch.setattr(settings, "auth_admin_password", "secret")
    monkeypatch.setattr(settings, "auth_token_secret", "test-secret")
    monkeypatch.setattr(models, "reset_training_records", lambda _db: {"prediction_logs": 2})
    monkeypatch.setattr(models, "delete_active_model_artifacts", lambda: {"artifact_deleted": True})
    monkeypatch.setattr(
        models, "insert_audit_log", lambda _db, **payload: audit_events.append(payload)
    )
    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    try:
        token = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret"},
        ).json()["access_token"]
        response = client.delete(
            "/api/v1/models/active",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert audit_events[0]["action"] == "reset_active_model"
    assert audit_events[0]["resource"] == "model:active"


def test_audit_log_endpoint_requires_admin_and_returns_records(monkeypatch) -> None:
    from app.api.v1 import auth

    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_admin_username", "admin")
    monkeypatch.setattr(settings, "auth_admin_password", "secret")
    monkeypatch.setattr(settings, "auth_token_secret", "test-secret")
    monkeypatch.setattr(
        auth,
        "fetch_audit_logs",
        lambda _db, limit: [
            {"actor": "admin", "action": "upsert_device", "resource": "device:CNC-001"}
        ],
    )
    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    try:
        denied = client.get("/api/v1/auth/audit")
        token = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret"},
        ).json()["access_token"]
        allowed = client.get("/api/v1/auth/audit", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.clear()

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()[0]["action"] == "upsert_device"
