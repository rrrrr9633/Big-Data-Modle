import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from app.api.v1 import ingestion
from app.ingestion.ai4i import transform_ai4i_row
from app.security.auth import CurrentUser


def test_transform_ai4i_row_maps_machine_to_device_and_sensor_readings() -> None:
    row = {
        "UDI": "1",
        "Product ID": "M14860",
        "Type": "M",
        "Air temperature [K]": "298.1",
        "Process temperature [K]": "308.6",
        "Rotational speed [rpm]": "1551",
        "Torque [Nm]": "42.8",
        "Tool wear [min]": "0",
        "Machine failure": "0",
    }

    imported = transform_ai4i_row(row, recorded_at=datetime(2026, 1, 1, tzinfo=UTC))

    assert imported.device_code == "M14860"
    assert imported.device_name == "AI4I-M14860"
    assert imported.device_type == "M"
    assert imported.failed is False
    assert [(item.sensor_code, item.value, item.unit) for item in imported.readings] == [
        ("air_temperature", 298.1, "K"),
        ("process_temperature", 308.6, "K"),
        ("rotational_speed", 1551.0, "rpm"),
        ("torque", 42.8, "Nm"),
        ("tool_wear", 0.0, "min"),
    ]


class FakeUploadFile:
    filename = "ai4i.csv"

    async def read(self) -> bytes:
        return b"".join(
            [
                b"UDI,Product ID,Type,Air temperature [K],Process temperature [K],",
                b"Rotational speed [rpm],Torque [Nm],Tool wear [min],Machine failure\n",
                b"1,M14860,M,298.1,308.6,1551,42.8,0,0\n",
            ]
        )


class FakeUploadFileWithTwoRows:
    filename = "ai4i.csv"

    async def read(self) -> bytes:
        return b"".join(
            [
                b"UDI,Product ID,Type,Air temperature [K],Process temperature [K],",
                b"Rotational speed [rpm],Torque [Nm],Tool wear [min],Machine failure\n",
                b"1,M14860,M,298.1,308.6,1551,42.8,0,0\n",
                b"2,H29424,H,303.9,313.4,1168,68.5,230,1\n",
            ]
        )


TEST_USER = CurrentUser(username="admin", role="admin")


def test_ai4i_import_trains_without_replaying_demo_data_by_default(monkeypatch) -> None:
    calls: list[str] = []
    suite = SimpleNamespace(
        metrics=[
            SimpleNamespace(
                model_name="lightgbm-fault-classifier",
                model_type="classification",
                version="1.0.0",
                metric_name="accuracy",
                metric_value=0.9,
            )
        ]
    )
    db = SimpleNamespace(commit=lambda: calls.append("commit"))

    monkeypatch.setattr(ingestion, "create_import_batch", lambda *_args: 12)
    monkeypatch.setattr(
        ingestion,
        "train_and_register_ai4i_model",
        lambda _db, rows: calls.append(f"train-service:{len(rows)}")
        or SimpleNamespace(suite=suite, trained_rows=len(rows)),
    )
    monkeypatch.setattr(ingestion, "insert_audit_log", lambda *_args, **_kwargs: None)

    response = asyncio.run(ingestion.import_ai4i_csv(FakeUploadFile(), db, TEST_USER))

    assert response["mode"] == "train_only"
    assert response["trained_rows"] == 1
    assert response["replay_enabled"] is False
    assert response["prediction_count"] == 0
    assert calls == ["train-service:1", "commit"]


def test_ai4i_import_can_replay_demo_data_when_enabled(monkeypatch) -> None:
    calls: list[object] = []
    suite = SimpleNamespace(metrics=[])
    db = SimpleNamespace(commit=lambda: calls.append("commit"))

    def fake_predict_ai4i_feature_row(*, device_id, feature_values, suite, forced_failure):
        calls.append((device_id, feature_values["Torque [Nm]"], forced_failure))
        return SimpleNamespace(
            device_id=device_id,
            failure_probability=0.2 if feature_values["Torque [Nm]"] < 50 else 0.91,
            health_score=86.0 if feature_values["Torque [Nm]"] < 50 else 30.0,
            risk_level="low" if feature_values["Torque [Nm]"] < 50 else "critical",
            anomaly_score=0.1 if feature_values["Torque [Nm]"] < 50 else 0.88,
            anomaly_reasons=["torque"] if feature_values["Torque [Nm]"] >= 50 else [],
            trend_factor=0.0,
            quality_score=1.0,
            rul_hours=120.0 if feature_values["Torque [Nm]"] < 50 else 2.0,
        )

    monkeypatch.setattr(ingestion, "create_import_batch", lambda *_args: 12)
    monkeypatch.setattr(
        ingestion,
        "train_and_register_ai4i_model",
        lambda _db, rows: SimpleNamespace(suite=suite, trained_rows=len(rows)),
    )
    monkeypatch.setattr(ingestion, "upsert_device", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingestion, "insert_sensor_reading", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingestion, "insert_feature_window", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingestion, "insert_prediction", lambda *_args, **_kwargs: 21)
    monkeypatch.setattr(ingestion, "insert_prediction_explanations", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ingestion,
        "insert_warning",
        lambda *_args, **_kwargs: calls.append("warning"),
    )
    monkeypatch.setattr(ingestion, "predict_ai4i_feature_row", fake_predict_ai4i_feature_row)
    monkeypatch.setattr(ingestion, "explain_ai4i_feature_row", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(ingestion, "insert_audit_log", lambda *_args, **_kwargs: None)

    response = asyncio.run(
        ingestion.import_ai4i_csv(FakeUploadFileWithTwoRows(), db, TEST_USER, replay_demo_data=True)
    )

    assert response["mode"] == "train_and_replay"
    assert response["replay_enabled"] is True
    assert response["prediction_count"] == 2
    assert response["warning_count"] == 1
    assert ("M14860", 42.8, False) in calls
    assert ("H29424", 68.5, True) in calls
    assert "warning" in calls
    assert calls[-1] == "commit"
