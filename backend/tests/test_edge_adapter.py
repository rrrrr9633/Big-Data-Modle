from app.edge.config import build_edge_adapter_configs
from app.edge.contracts import EdgeAdapterConfig
from app.edge.runtime import collect_and_publish, collect_once


def test_edge_adapter_config_groups_supported_protocols() -> None:
    configs = build_edge_adapter_configs(
        [
            {
                "device_code": "CNC-001",
                "factory": "factory-a",
                "workshop": "machining",
                "production_line": "line-1",
                "sensor_points": [
                    _point("spindle_temperature", "modbus", "holding:40001:int16:scale=0.1"),
                    _point("spindle_load", "opcua", "ns=2;s=CNC001.Spindle.Load"),
                    _point("axis_x", "s7", "DB1.DBD0:float"),
                    _point("program_status", "cnc", "fanuc:macro:100"),
                ],
            }
        ]
    )

    config = EdgeAdapterConfig.model_validate(configs[0])

    assert config.gateway.gateway_id == "gateway-cnc-001"
    assert (
        config.gateway.mqtt_topic
        == "factory/factory-a/workshop/machining/line/line-1/machine/CNC-001/telemetry"
    )
    assert [point.protocol for point in config.points] == ["modbus", "opcua", "s7", "cnc"]
    assert config.payload_schema[:4] == ["event_id", "device_code", "point_code", "value"]


def test_edge_runtime_collects_standard_telemetry_events() -> None:
    config = EdgeAdapterConfig.model_validate(
        build_edge_adapter_configs(
            [
                {
                    "device_code": "CNC-001",
                    "factory": "factory-a",
                    "workshop": "machining",
                    "production_line": "line-1",
                    "sensor_points": [
                        _point("spindle_temperature", "modbus", "holding:40001:int16")
                    ],
                }
            ]
        )[0]
    )

    events = collect_once(config)
    result = collect_and_publish(config, mode="dry-run")

    assert len(events) == 1
    assert events[0].device_code == "CNC-001"
    assert events[0].point_code == "spindle_temperature"
    assert events[0].gateway_id == "gateway-cnc-001"
    assert events[0].source_topic == config.gateway.mqtt_topic
    assert result.status == "accepted"
    assert result.mode == "dry-run"
    assert result.accepted_events == 1


def _point(sensor_code: str, protocol: str, source_address: str) -> dict[str, object]:
    return {
        "sensor_code": sensor_code,
        "sensor_name": sensor_code.replace("_", " "),
        "unit": "C",
        "sampling_frequency": "1s",
        "protocol": protocol,
        "source_address": source_address,
        "feature_name": f"{sensor_code}_mean",
        "quality_rule": "quality=0 when protocol status is bad",
        "min_value": 0,
        "max_value": 100,
        "enabled": True,
    }
