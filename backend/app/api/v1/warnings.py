from typing import Annotated, Any, Literal

from app.core.database import get_db
from app.repositories.maintenance_repository import (
    ensure_prediction_model_schema,
    fetch_warning_by_id,
    fetch_warnings,
    insert_audit_log,
    transition_warning_status,
)
from app.security.auth import CurrentUser, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
AdminUser = Annotated[CurrentUser, Depends(require_admin)]
WarningLimit = Annotated[int, Query(ge=1, le=500)]
WarningStatus = Literal["new", "acknowledged", "processing", "resolved", "ignored"]

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new": {"acknowledged", "ignored"},
    "acknowledged": {"processing", "resolved", "ignored"},
    "processing": {"resolved", "ignored"},
    "resolved": set(),
    "ignored": set(),
}


class WarningStatusUpdate(BaseModel):
    status: WarningStatus
    operator: str = Field(default="系统操作员", min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=500)


@router.get("")
def list_warnings(db: DbSession, limit: WarningLimit = 100) -> list[dict[str, Any]]:
    ensure_prediction_model_schema(db)
    return fetch_warnings(db, limit=limit)


@router.post("/{warning_id}/status")
def update_warning_status(
    warning_id: int,
    payload: WarningStatusUpdate,
    db: DbSession,
    user: AdminUser,
) -> dict[str, Any]:
    ensure_prediction_model_schema(db)
    warning = fetch_warning_by_id(db, warning_id)
    if warning is None:
        raise HTTPException(status_code=404, detail="预警不存在")

    from_status = str(warning["status"])
    to_status = payload.status
    if to_status == from_status:
        return fetch_warning_by_id(db, warning_id) or warning

    if to_status not in ALLOWED_TRANSITIONS.get(from_status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"非法状态迁移：{from_status} -> {to_status}",
        )

    transition_warning_status(
        db,
        warning_id=warning_id,
        from_status=from_status,
        to_status=to_status,
        operator=payload.operator.strip(),
        note=payload.note.strip() if payload.note else None,
    )
    insert_audit_log(
        db,
        actor=user.username,
        role=user.role,
        action="transition_warning",
        resource=f"warning:{warning_id}",
        detail={
            "from_status": from_status,
            "to_status": to_status,
            "operator": payload.operator.strip(),
            "note": payload.note.strip() if payload.note else None,
        },
    )
    db.commit()
    return fetch_warning_by_id(db, warning_id) or warning
