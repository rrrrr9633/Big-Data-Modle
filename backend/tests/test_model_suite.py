from app.compute.features import build_feature_window
from app.governance.pipeline import standardize_readings
from app.ingestion.ai4i import transform_ai4i_row
from app.models.model_suite import (
    _window_vector,
    explain_prediction,
    predict_with_model_suite,
    train_ai4i_model_suite,
)


def _row(
    udi: int,
    product_id: str,
    machine_type: str,
    air_temp: float,
    process_temp: float,
    speed: float,
    torque: float,
    wear: float,
    failed: int,
) -> dict[str, str]:
    return {
        "UDI": str(udi),
        "Product ID": product_id,
        "Type": machine_type,
        "Air temperature [K]": str(air_temp),
        "Process temperature [K]": str(process_temp),
        "Rotational speed [rpm]": str(speed),
        "Torque [Nm]": str(torque),
        "Tool wear [min]": str(wear),
        "Machine failure": str(failed),
    }


def test_realtime_window_uses_named_ai4i_sensor_values_for_model_input() -> None:
    row = _row(1, "M10001", "M", 298.1, 308.6, 1551, 42.8, 17, 0)
    sample = transform_ai4i_row(row)
    window = build_feature_window(standardize_readings(sample.readings))

    assert window is not None
    assert _window_vector(window) == [298.1, 308.6, 1551.0, 42.8, 17.0]


def test_ai4i_model_suite_outputs_probability_anomaly_rul_and_explanations() -> None:
    rows = [
        _row(1, "M10001", "M", 298.1, 308.6, 1551, 42.8, 0, 0),
        _row(2, "M10002", "M", 298.2, 308.7, 1408, 46.3, 3, 0),
        _row(3, "M10003", "M", 298.1, 308.5, 1498, 49.4, 5, 0),
        _row(4, "M10004", "M", 298.2, 308.6, 1433, 39.5, 7, 0),
        _row(5, "M10005", "M", 298.2, 308.7, 1408, 40.0, 9, 0),
        _row(6, "M10006", "M", 298.1, 308.6, 1425, 41.9, 11, 0),
        _row(7, "H20001", "H", 303.8, 313.9, 1168, 68.5, 230, 1),
        _row(8, "H20002", "H", 304.1, 314.2, 1182, 72.4, 236, 1),
        _row(9, "H20003", "H", 302.6, 312.4, 1281, 62.8, 205, 1),
        _row(10, "H20004", "H", 302.1, 311.9, 1302, 59.6, 198, 1),
    ]
    suite = train_ai4i_model_suite(rows)
    sample = transform_ai4i_row(rows[-1])
    window = build_feature_window(standardize_readings(sample.readings))

    assert window is not None
    prediction = predict_with_model_suite(window, suite)
    explanations = explain_prediction(window, suite)

    assert 0 <= prediction.failure_probability <= 1
    assert 0 <= prediction.anomaly_score <= 1
    assert 0 <= prediction.health_score <= 100
    assert suite.classifier is not None
    assert suite.anomaly_detector is not None
    assert suite.rul_regressor is not None
    assert explanations
    assert {metric.model_name for metric in suite.metrics} >= {
        "lightgbm-fault-classifier",
        "isolation-forest-anomaly",
        "lightgbm-rul-regressor",
        "shap-risk-explainer",
    }
