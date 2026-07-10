from __future__ import annotations

from typing import Any
from urllib.parse import quote

from app.edge.contracts import EdgeAdapterConfig, EdgeGatewayConfig, EdgePointBinding, EdgeProtocol

PAYLOAD_SCHEMA = [
    "event_id",
    "device_code",
    "point_code",
    "value",
    "unit",
    "quality",
    "ts",
    "gateway_id",
    "source_topic",
]

RUNTIME_CONTRACT = {
    "adapter_role": "read industrial protocol points and publish TelemetryEvent",
    "output_event": "app.ingestion.schemas.TelemetryEvent",
    "publish_targets": ["mqtt", "kafka", "dry-run"],
    "protocols": ["modbus", "opcua", "s7", "cnc"],
    "quality_policy": (
        "adapter reports protocol status as quality; "
        "catalog validation remains in raw consumer"
    ),
}


def build_edge_adapter_configs(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    for device in devices:
        gateway = _gateway_from_device(device)
        points = [_point_binding(device, point) for point in device.get("sensor_points") or []]
        valid_points = [point for point in points if point is not None]
        configs.append(
            EdgeAdapterConfig(
                gateway=gateway,
                points=valid_points,
                payload_schema=PAYLOAD_SCHEMA,
                runtime_contract=RUNTIME_CONTRACT,
            ).model_dump(mode="json")
        )
    return configs


def _gateway_from_device(device: dict[str, Any]) -> EdgeGatewayConfig:
    device_code = str(device.get("device_code") or "unknown")
    factory = str(device.get("factory") or "default")
    workshop = str(device.get("workshop") or "default")
    line = str(device.get("production_line") or "default")
    return EdgeGatewayConfig(
        gateway_id=f"gateway-{device_code.lower()}",
        factory=factory,
        workshop=workshop,
        production_line=line,
        mqtt_topic=build_device_topic(
            factory=factory,
            workshop=workshop,
            production_line=line,
            device_code=device_code,
        ),
    )


def build_device_topic(
    *, factory: str, workshop: str, production_line: str, device_code: str
) -> str:
    return (
        f"factory/{quote(factory, safe='')}"
        f"/workshop/{quote(workshop, safe='')}"
        f"/line/{quote(production_line, safe='')}"
        f"/machine/{quote(device_code, safe='')}"
        "/telemetry"
    )


def _point_binding(
    device: dict[str, Any],
    point: dict[str, Any],
) -> EdgePointBinding | None:
    protocol = _normalize_protocol(point.get("protocol"))
    source_address = str(point.get("source_address") or "").strip()
    point_code = str(point.get("sensor_code") or "").strip()
    device_code = str(device.get("device_code") or "").strip()
    if not protocol or not source_address or not point_code or not device_code:
        return None
    return EdgePointBinding(
        device_code=device_code,
        point_code=point_code,
        point_name=point.get("sensor_name") or point_code,
        unit=point.get("unit"),
        sampling_frequency=str(point.get("sampling_frequency") or "realtime"),
        protocol=protocol,
        source_address=source_address,
        feature_name=point.get("feature_name"),
        quality_rule=point.get("quality_rule"),
        min_value=point.get("min_value"),
        max_value=point.get("max_value"),
        enabled=bool(point.get("enabled", True)),
        protocol_options=point.get("protocol_options")
        or _infer_protocol_options(protocol, source_address),
    )


def _normalize_protocol(value: Any) -> EdgeProtocol | None:
    normalized = str(value or "").strip().lower().replace(" ", "").replace("-", "")
    aliases: dict[str, EdgeProtocol] = {
        "modbus": "modbus",
        "modbustcp": "modbus",
        "modbusrtu": "modbus",
        "opcua": "opcua",
        "opc": "opcua",
        "s7": "s7",
        "siemenss7": "s7",
        "cnc": "cnc",
        "fanuc": "cnc",
        "mitsubishi": "cnc",
        "siemenscnc": "cnc",
    }
    return aliases.get(normalized)


def _infer_protocol_options(protocol: EdgeProtocol, source_address: str) -> dict[str, Any]:
    if protocol == "modbus":
        return {"address": source_address, "example": "holding:40001:int16:scale=0.1"}
    if protocol == "opcua":
        return {"node_id": source_address, "mode": "subscription-or-polling"}
    if protocol == "s7":
        return {"address": source_address, "example": "DB1.DBD0:float"}
    return {"address": source_address, "vendor_driver": "plugin-required"}
