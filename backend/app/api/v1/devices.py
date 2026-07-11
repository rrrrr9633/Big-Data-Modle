from __future__ import annotations

from typing import Annotated, Any, Literal

from app.core.database import get_db
from app.governance.dependencies import assess_sensor_point_change
from app.repositories.maintenance_repository import (
    disable_sensor_point,
    ensure_prediction_model_schema,
    fetch_active_model_feature_dependencies,
    fetch_devices,
    fetch_master_data_change_request,
    fetch_master_data_change_requests,
    fetch_sensor_point,
    insert_audit_log,
    insert_master_data_change_request,
    insert_master_data_version,
    mark_master_data_change_request_decision,
    upsert_device,
    upsert_sensor_point,
)
from app.security.auth import CurrentUser
from app.security.policies import require_permission
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
DeviceChangeUser = Annotated[CurrentUser, Depends(require_permission("device.change.submit"))]
DeviceApprovalUser = Annotated[CurrentUser, Depends(require_permission("device.change.approve"))]
DeviceReadUser = Annotated[CurrentUser, Depends(require_permission("device.read"))]


class DeviceUpsertIn(BaseModel):
    device_code: str = Field(min_length=1, max_length=64)
    device_name: str = Field(min_length=1, max_length=128)
    device_type: str = Field(default="industrial-machine", max_length=64)
    factory: str = Field(default="默认工厂", max_length=128)
    workshop: str = Field(default="默认车间", max_length=128)
    production_line: str = Field(default="默认产线", max_length=128)
    status: str = Field(default="online", max_length=32)


class SensorPointUpsertIn(BaseModel):
    sensor_name: str | None = Field(default=None, max_length=128)
    unit: str | None = Field(default=None, max_length=32)
    sampling_frequency: str = Field(default="realtime", max_length=64)
    protocol: str | None = Field(default=None, max_length=64)
    source_address: str | None = Field(default=None, max_length=255)
    protocol_options: dict[str, Any] = Field(default_factory=dict)
    feature_name: str | None = Field(default=None, max_length=128)
    quality_rule: str | None = Field(default=None, max_length=255)
    min_value: float | None = None
    max_value: float | None = None
    enabled: bool = True


class MasterDataChangeRequestIn(BaseModel):
    entity_type: Literal["device", "sensor_point"]
    operation: Literal["upsert", "disable"]
    device_code: str = Field(min_length=1, max_length=64)
    sensor_code: str | None = Field(default=None, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)


class MasterDataDecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=500)


@router.get("/change-requests")
def list_master_data_change_requests(
    db: DbSession,
    _user: DeviceReadUser,
    limit: int = 100,
) -> list[dict[str, Any]]:
    ensure_prediction_model_schema(db)
    return fetch_master_data_change_requests(db, limit=min(max(limit, 1), 500))


@router.post("/change-requests")
def submit_master_data_change_request(
    payload: MasterDataChangeRequestIn,
    db: DbSession,
    user: DeviceChangeUser,
) -> dict[str, object]:
    ensure_prediction_model_schema(db)
    _validate_master_data_change(payload)
    impact = _build_master_data_change_impact(payload)
    change_request_id = insert_master_data_change_request(
        db,
        entity_type=payload.entity_type,
        operation=payload.operation,
        device_code=payload.device_code,
        sensor_code=payload.sensor_code,
        payload=payload.payload,
        impact=impact,
        reason=payload.reason,
        requested_by=user.username,
        requested_role=user.role,
    )
    insert_audit_log(
        db,
        actor=user.username,
        role=user.role,
        action="submit_master_data_change_request",
        resource=_master_data_resource(
            payload.entity_type,
            payload.device_code,
            payload.sensor_code,
        ),
        detail={"change_request_id": change_request_id, "impact": impact},
    )
    db.commit()
    return {"status": "pending", "change_request_id": change_request_id, "impact": impact}


@router.post("/change-requests/{change_request_id}/decision")
def decide_master_data_change_request(
    change_request_id: int,
    payload: MasterDataDecisionIn,
    db: DbSession,
    user: DeviceApprovalUser,
) -> dict[str, object]:
    ensure_prediction_model_schema(db)
    change_request = fetch_master_data_change_request(db, change_request_id)
    if not change_request:
        raise HTTPException(status_code=404, detail="主数据变更单不存在")
    if change_request.get("status") != "pending":
        raise HTTPException(status_code=409, detail="主数据变更单已处理")

    version_id: int | None = None
    status = "rejected"
    if payload.decision == "approve":
        dependency_impact = _approval_dependency_impact(db, change_request)
        if not dependency_impact.publish_allowed:
            raise HTTPException(status_code=409, detail="；".join(dependency_impact.blockers))
        _apply_master_data_change(db, change_request)
        version_id = insert_master_data_version(
            db,
            change_request_id=change_request_id,
            entity_type=str(change_request["entity_type"]),
            device_code=str(change_request["device_code"]),
            sensor_code=change_request.get("sensor_code"),
            snapshot=_master_data_version_snapshot(change_request),
            published_by=user.username,
            published_role=user.role,
        )
        status = "approved"

    mark_master_data_change_request_decision(
        db,
        change_request_id=change_request_id,
        status=status,
        approved_by=user.username,
        approved_role=user.role,
        decision_comment=payload.comment,
    )
    insert_audit_log(
        db,
        actor=user.username,
        role=user.role,
        action=f"{status}_master_data_change_request",
        resource=_master_data_resource(
            str(change_request["entity_type"]),
            str(change_request["device_code"]),
            change_request.get("sensor_code"),
        ),
        detail={"change_request_id": change_request_id, "version_id": version_id},
    )
    db.commit()
    return {"status": status, "change_request_id": change_request_id, "version_id": version_id}


@router.get("")
def list_devices(db: DbSession) -> list[dict[str, Any]]:
    ensure_prediction_model_schema(db)
    return fetch_devices(db)


@router.post("")
def create_or_update_device(
    payload: DeviceUpsertIn,
    db: DbSession,
    user: DeviceChangeUser,
) -> dict[str, object]:
    ensure_prediction_model_schema(db)
    upsert_device(db, **payload.model_dump())
    insert_audit_log(
        db,
        actor=user.username,
        role=user.role,
        action="upsert_device",
        resource=f"device:{payload.device_code}",
        detail=payload.model_dump(),
    )
    db.commit()
    return {"status": "saved", "device_code": payload.device_code}


@router.put("/{device_code}/points/{sensor_code}")
def create_or_update_sensor_point(
    device_code: str,
    sensor_code: str,
    payload: SensorPointUpsertIn,
    db: DbSession,
    user: DeviceChangeUser,
) -> dict[str, object]:
    ensure_prediction_model_schema(db)
    upsert_sensor_point(
        db,
        device_code=device_code,
        sensor_code=sensor_code,
        **payload.model_dump(),
    )
    insert_audit_log(
        db,
        actor=user.username,
        role=user.role,
        action="upsert_sensor_point",
        resource=f"device:{device_code}:point:{sensor_code}",
        detail=payload.model_dump(),
    )
    db.commit()
    return {"status": "saved", "device_code": device_code, "sensor_code": sensor_code}


@router.delete("/{device_code}/points/{sensor_code}")
def disable_device_sensor_point(
    device_code: str,
    sensor_code: str,
    db: DbSession,
    user: DeviceChangeUser,
) -> dict[str, object]:
    ensure_prediction_model_schema(db)
    disable_sensor_point(db, device_code=device_code, sensor_code=sensor_code)
    insert_audit_log(
        db,
        actor=user.username,
        role=user.role,
        action="disable_sensor_point",
        resource=f"device:{device_code}:point:{sensor_code}",
        detail={"device_code": device_code, "sensor_code": sensor_code},
    )
    db.commit()
    return {"status": "disabled", "device_code": device_code, "sensor_code": sensor_code}


def _validate_master_data_change(payload: MasterDataChangeRequestIn) -> None:
    if payload.entity_type == "device":
        if payload.sensor_code:
            raise HTTPException(status_code=422, detail="设备变更不应包含 sensor_code")
        if payload.operation == "disable":
            raise HTTPException(status_code=422, detail="暂不支持禁用设备主数据")
        DeviceUpsertIn.model_validate(payload.payload)
        return

    if not payload.sensor_code:
        raise HTTPException(status_code=422, detail="点位变更必须包含 sensor_code")
    if payload.operation == "upsert":
        SensorPointUpsertIn.model_validate(payload.payload)


def _build_master_data_change_impact(payload: MasterDataChangeRequestIn) -> dict[str, Any]:
    risk_items: list[str] = []
    review_items: list[str] = []
    changed_fields = sorted(payload.payload.keys())

    if payload.entity_type == "sensor_point":
        review_items.append("点位目录变更会影响 raw 遥测校验和边缘配置导出")
        if "feature_name" in payload.payload:
            risk_items.append("模型特征映射变更")
            review_items.append("需要确认已训练模型是否仍使用旧 feature_name")
        if "quality_rule" in payload.payload:
            risk_items.append("质量规则变更")
            review_items.append("需要确认异常隔离和点位质量看板口径")
        if {"protocol", "source_address", "protocol_options"} & set(payload.payload):
            risk_items.append("现场采集地址变更")
            review_items.append("需要重新导出边缘配置并做现场连通验证")
        if {"min_value", "max_value"} & set(payload.payload):
            risk_items.append("值域变更")
            review_items.append("需要确认历史异常阈值和质量告警口径")
    else:
        review_items.append("设备台账变更会影响工作台展示、topic 命名和审计归属")
        if {"factory", "workshop", "production_line"} & set(payload.payload):
            risk_items.append("组织层级变更")
            review_items.append("需要确认 MQTT topic 和边缘网关分组")

    return {
        "changed_fields": changed_fields,
        "risk_items": risk_items or ["低风险主数据变更"],
        "review_items": review_items,
    }


def _approval_dependency_impact(db: Session, change_request: dict[str, Any]):
    if (
        change_request.get("entity_type") != "sensor_point"
        or change_request.get("operation") != "upsert"
        or not change_request.get("sensor_code")
    ):
        return assess_sensor_point_change(
            device_code=str(change_request["device_code"]),
            sensor_code="",
            current_point={},
            proposed_point={},
            active_models=[],
            gateway_configs=[],
        )

    device_code = str(change_request["device_code"])
    sensor_code = str(change_request["sensor_code"])
    current_point = fetch_sensor_point(
        db,
        device_code=device_code,
        sensor_code=sensor_code,
    ) or {}
    gateways = [
        {
            "gateway_id": f"gateway-{device.get('device_code', '').lower()}",
            "config_version": "current",
            "device_code": device.get("device_code"),
            "point_code": point.get("sensor_code"),
            "feature_name": point.get("feature_name"),
        }
        for device in fetch_devices(db)
        for point in device.get("sensor_points") or []
    ]
    return assess_sensor_point_change(
        device_code=device_code,
        sensor_code=sensor_code,
        current_point=current_point,
        proposed_point=change_request.get("payload") or {},
        active_models=fetch_active_model_feature_dependencies(db),
        gateway_configs=gateways,
    )


def _apply_master_data_change(db: Session, change_request: dict[str, Any]) -> None:
    entity_type = str(change_request["entity_type"])
    operation = str(change_request["operation"])
    device_code = str(change_request["device_code"])
    sensor_code = change_request.get("sensor_code")
    payload = change_request.get("payload") or {}

    if entity_type == "device" and operation == "upsert":
        model = DeviceUpsertIn.model_validate(payload)
        upsert_device(db, **model.model_dump())
        return

    if entity_type == "sensor_point" and operation == "upsert":
        if not sensor_code:
            raise HTTPException(status_code=422, detail="点位变更缺少 sensor_code")
        model = SensorPointUpsertIn.model_validate(payload)
        upsert_sensor_point(
            db,
            device_code=device_code,
            sensor_code=str(sensor_code),
            **model.model_dump(),
        )
        return

    if entity_type == "sensor_point" and operation == "disable":
        if not sensor_code:
            raise HTTPException(status_code=422, detail="点位变更缺少 sensor_code")
        disable_sensor_point(db, device_code=device_code, sensor_code=str(sensor_code))
        return

    raise HTTPException(status_code=422, detail="不支持的主数据变更类型")


def _master_data_version_snapshot(change_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_type": change_request.get("entity_type"),
        "operation": change_request.get("operation"),
        "device_code": change_request.get("device_code"),
        "sensor_code": change_request.get("sensor_code"),
        "payload": change_request.get("payload") or {},
        "impact": change_request.get("impact") or {},
    }


def _master_data_resource(entity_type: str, device_code: str, sensor_code: str | None) -> str:
    if entity_type == "sensor_point":
        return f"device:{device_code}:point:{sensor_code}"
    return f"device:{device_code}"
