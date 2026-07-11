from app.governance.dependencies import assess_sensor_point_change
from app.models.model_suite import AI4I_FEATURE_COLUMNS, Ai4iModelSuite, ModelMetric
from app.models.registry import model_feature_dependencies


def test_model_feature_dependencies_records_each_model_version_with_training_features() -> None:
    suite = Ai4iModelSuite(
        classifier=None,  # type: ignore[arg-type]
        anomaly_detector=None,  # type: ignore[arg-type]
        rul_regressor=None,  # type: ignore[arg-type]
        feature_importance=[],
        metrics=[
            ModelMetric("fault-classifier", "classifier", "2026.07.1", "f1", 0.8),
            ModelMetric("fault-classifier", "classifier", "2026.07.1", "recall", 0.7),
            ModelMetric("rul-regressor", "regression", "2026.07.1", "mae", 3.1),
        ],
    )

    dependencies = model_feature_dependencies(suite)

    assert dependencies == [
        {
            "model_name": "fault-classifier",
            "version": "2026.07.1",
            "features": list(AI4I_FEATURE_COLUMNS),
        },
        {
            "model_name": "rul-regressor",
            "version": "2026.07.1",
            "features": list(AI4I_FEATURE_COLUMNS),
        },
    ]


def test_feature_rename_blocks_approval_when_active_model_uses_old_feature() -> None:
    impact = assess_sensor_point_change(
        device_code="CNC-001",
        sensor_code="spindle_temperature",
        current_point={"feature_name": "spindle_temperature_mean"},
        proposed_point={"feature_name": "spindle_temp_mean_v2"},
        active_models=[
            {
                "model_name": "fault-classifier",
                "version": "2026.07.1",
                "features": ["spindle_temperature_mean", "vibration_rms"],
            }
        ],
        gateway_configs=[
            {
                "gateway_id": "gw-cnc-001",
                "config_version": "18",
                "device_code": "CNC-001",
                "point_code": "spindle_temperature",
                "feature_name": "spindle_temperature_mean",
            }
        ],
    )

    assert impact.publish_allowed is False
    assert impact.blockers == [
        "活跃模型 fault-classifier@2026.07.1 依赖旧特征 spindle_temperature_mean"
    ]
    assert impact.stale_gateway_ids == ["gw-cnc-001"]


def test_protocol_change_requires_gateway_rollout_but_does_not_block_unrelated_model() -> None:
    impact = assess_sensor_point_change(
        device_code="CNC-001",
        sensor_code="spindle_temperature",
        current_point={"protocol": "opcua", "source_address": "ns=2;s=Temp"},
        proposed_point={"protocol": "modbus", "source_address": "holding:40001:uint16"},
        active_models=[
            {"model_name": "fault-classifier", "version": "2026.07.1", "features": ["torque_mean"]}
        ],
        gateway_configs=[],
    )

    assert impact.publish_allowed is True
    assert impact.required_actions == ["重新导出并灰度发布边缘网关配置"]
