from app.models.baseline import train_ai4i_baseline


def test_train_ai4i_baseline_returns_metrics_and_feature_importance() -> None:
    rows = [
        {
            "Air temperature [K]": "298.1",
            "Process temperature [K]": "308.6",
            "Rotational speed [rpm]": "1551",
            "Torque [Nm]": "42.8",
            "Tool wear [min]": "0",
            "Machine failure": "0",
        },
        {
            "Air temperature [K]": "310.0",
            "Process temperature [K]": "320.0",
            "Rotational speed [rpm]": "1200",
            "Torque [Nm]": "70.0",
            "Tool wear [min]": "220",
            "Machine failure": "1",
        },
        {
            "Air temperature [K]": "299.0",
            "Process temperature [K]": "309.0",
            "Rotational speed [rpm]": "1500",
            "Torque [Nm]": "40.0",
            "Tool wear [min]": "5",
            "Machine failure": "0",
        },
        {
            "Air temperature [K]": "312.0",
            "Process temperature [K]": "322.0",
            "Rotational speed [rpm]": "1180",
            "Torque [Nm]": "75.0",
            "Tool wear [min]": "230",
            "Machine failure": "1",
        },
    ]

    result = train_ai4i_baseline(rows)

    assert result.model_name == "ai4i-random-forest-baseline"
    assert set(result.metrics) >= {"accuracy", "positive_rate", "sample_count"}
    assert result.metrics["sample_count"] == 4
    assert result.feature_importance[0][1] >= result.feature_importance[-1][1]