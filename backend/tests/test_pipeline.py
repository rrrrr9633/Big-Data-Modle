from datetime import UTC, datetime

from app.compute.features import build_feature_window
from app.governance.pipeline import standardize_readings
from app.ingestion.pipeline import parse_historical_rows
from app.models.inference import predict_device_risk
from app.services.maintenance import generate_maintenance_advice


def test_timeseries_pipeline_generates_advice() -> None:
    rows = [
        {
            "device_id": "D001",
            "sensor_code": "temperature",
            "timestamp": datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            "value": 80.0,
            "unit": "℃",
        },
        {
            "device_id": "D001",
            "sensor_code": "temperature",
            "timestamp": datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            "value": 82.0,
            "unit": "℃",
        },
    ]

    readings = parse_historical_rows(rows)
    governed = standardize_readings(readings)
    window = build_feature_window(governed)

    assert window is not None
    result = predict_device_risk(window)
    advice = generate_maintenance_advice(result)

    assert advice.device_id == "D001"
    assert advice.suggested_action


def test_predictions_endpoint_ensures_schema_before_reading(monkeypatch) -> None:
    from app.api.v1 import predictions

    calls: list[str] = []

    monkeypatch.setattr(
        predictions,
        "ensure_prediction_model_schema",
        lambda _db: calls.append("schema"),
    )
    monkeypatch.setattr(
        predictions,
        "fetch_predictions",
        lambda _db, *, limit: calls.append(f"fetch:{limit}") or [],
    )

    assert predictions.list_predictions(object(), limit=25) == []
    assert calls == ["schema", "fetch:25"]
