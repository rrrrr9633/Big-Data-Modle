from __future__ import annotations

from typing import Annotated, Any

from app.core.config import settings
from app.core.database import get_db
from app.edge.config import build_edge_adapter_configs
from app.edge.contracts import EdgeAdapterConfig
from app.edge.publisher import publish_events
from app.edge.runtime import collect_once
from app.repositories.maintenance_repository import (
    ensure_prediction_model_schema,
    fetch_devices,
)
from app.security.auth import CurrentUser
from app.security.policies import require_permission
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
EdgeExportUser = Annotated[CurrentUser, Depends(require_permission("edge.config.export"))]

TELEMETRY_EVENT_FIELDS = [
    "event_id",
    "device_code",
    "point_code",
    "value",
    "unit",
    "quality",
    "ts",
    "gateway_id",
]


@router.get("/catalog")
def get_ingress_catalog(db: DbSession) -> dict[str, Any]:
    ensure_prediction_model_schema(db)
    return build_ingress_catalog(db)


@router.get("/edge-configs")
def get_edge_adapter_configs(db: DbSession, _user: EdgeExportUser) -> dict[str, Any]:
    ensure_prediction_model_schema(db)
    devices = fetch_devices(db)
    configs = build_edge_adapter_configs(devices)
    return {
        "status": "ready" if configs else "empty",
        "config_format": "edge-adapter-config.v1",
        "publish_contract": {
            "primary": "mqtt",
            "fallback": "kafka",
            "dry_run_supported": True,
            "telemetry_event_fields": TELEMETRY_EVENT_FIELDS + ["source_topic"],
        },
        "configs": configs,
        "production_gaps": _catalog_gaps(devices),
    }


@router.post("/edge-configs/simulate")
def simulate_edge_adapter_config(
    config: EdgeAdapterConfig,
    _user: EdgeExportUser,
) -> dict[str, Any]:
    events = collect_once(config)
    publish_result = publish_events(events, gateway=config.gateway, mode="dry-run")
    return {
        "status": "simulated",
        "config_format": "edge-adapter-config.v1",
        "gateway_id": config.gateway.gateway_id,
        "publish_result": publish_result.model_dump(mode="json"),
        "events": [event.model_dump(mode="json") for event in events],
        "next_step": (
            "Set publish_mode to mqtt or kafka in an external edge runner "
            "after field verification."
        ),
    }


def build_ingress_catalog(db: Session) -> dict[str, Any]:
    devices = fetch_devices(db)
    return {
        "primary_ingress": "mqtt",
        "mqtt_topic": settings.mqtt_telemetry_topic,
        "mqtt_example_topic": (
            "factory/factory-a/workshop/machining/line/line-1/"
            "machine/CNC-001/telemetry"
        ),
        "payload_schema": TELEMETRY_EVENT_FIELDS,
        "edge_adapter_contract": {
            "publish_mode": "single-point-json",
            "required_protocol_adapter": "Modbus / OPC UA / S7 / CNC gateway",
            "timestamp_source": "gateway acquisition time",
            "idempotency_key": "event_id",
            "quality_rule": "0~1 quality score; bad or substituted values must be below 1",
        },
        "gateway_responsibility": [
            "读取 Modbus / OPC UA / S7 / EtherNet/IP 等现场协议",
            "统一设备编号、点位编码、单位、质量分数和采集时间",
            "生成 event_id 并发布 TelemetryEvent JSON 到 EMQX",
        ],
        "devices": devices,
        "edge_gateway_mappings": _edge_gateway_mappings(devices),
        "edge_adapter_configs": build_edge_adapter_configs(devices),
        "production_gaps": _catalog_gaps(devices),
    }


def _edge_gateway_mappings(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for device in devices:
        device_code = str(device.get("device_code") or "")
        if not device_code:
            continue
        factory = str(device.get("factory") or "default")
        workshop = str(device.get("workshop") or "default")
        line = str(device.get("production_line") or "default")
        topic = f"factory/{factory}/workshop/{workshop}/line/{line}/machine/{device_code}/telemetry"
        points = []
        for point in device.get("sensor_points") or []:
            point_code = str(point.get("sensor_code") or "")
            if not point_code:
                continue
            points.append(
                {
                    "point_code": point_code,
                    "point_name": point.get("sensor_name") or point_code,
                    "unit": point.get("unit"),
                    "sampling_frequency": point.get("sampling_frequency"),
                    "protocol": point.get("protocol"),
                    "source_address": point.get("source_address"),
                    "feature_name": point.get("feature_name"),
                    "quality_rule": point.get("quality_rule"),
                    "enabled": bool(point.get("enabled", True)),
                    "range": {
                        "min": point.get("min_value"),
                        "max": point.get("max_value"),
                    },
                    "target_payload": {
                        "event_id": f"<gateway_id>-{device_code}-{point_code}-<epoch_ms>",
                        "device_code": device_code,
                        "point_code": point_code,
                        "value": "<numeric_value>",
                        "unit": point.get("unit"),
                        "quality": "<0.0-1.0>",
                        "ts": "<gateway_acquisition_iso_time>",
                        "gateway_id": "<gateway_id>",
                    },
                }
            )
        mappings.append(
            {
                "device_code": device_code,
                "factory": factory,
                "workshop": workshop,
                "production_line": line,
                "mqtt_topic": topic,
                "points": points,
            }
        )
    return mappings


def _catalog_gaps(devices: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    if not devices:
        gaps.append("未配置设备台账")
    for device in devices:
        device_code = str(device.get("device_code") or "")
        points = device.get("sensor_points") or []
        if not points:
            gaps.append(f"{device_code} 未配置传感器点位")
            continue
        for point in points:
            if not point.get("unit"):
                gaps.append(f"{device_code}/{point.get('sensor_code')} 未配置单位")
            if not point.get("sampling_frequency"):
                gaps.append(f"{device_code}/{point.get('sensor_code')} 未配置采样频率")
            if not point.get("protocol"):
                gaps.append(f"{device_code}/{point.get('sensor_code')} 未配置现场协议")
            if not point.get("source_address"):
                gaps.append(f"{device_code}/{point.get('sensor_code')} 未配置协议源地址")
            if not point.get("feature_name"):
                gaps.append(f"{device_code}/{point.get('sensor_code')} 未配置模型特征映射")
            if not point.get("quality_rule"):
                gaps.append(f"{device_code}/{point.get('sensor_code')} 未配置质量规则")
            if point.get("min_value") is None or point.get("max_value") is None:
                gaps.append(f"{device_code}/{point.get('sensor_code')} 未配置合理值域")
    return gaps
