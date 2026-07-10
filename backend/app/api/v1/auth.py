from __future__ import annotations

import hmac
from typing import Annotated

from app.core.config import settings
from app.core.database import get_db
from app.repositories.maintenance_repository import fetch_audit_logs
from app.security.auth import CurrentUser, create_access_token, get_current_user
from app.security.policies import require_permission
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
AuditUser = Annotated[CurrentUser, Depends(require_permission("audit.read"))]


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


@router.post("/login")
def login(payload: LoginIn) -> dict[str, object]:
    if not hmac.compare_digest(
        payload.username, settings.auth_admin_username
    ) or not hmac.compare_digest(
        payload.password,
        settings.auth_admin_password,
    ):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {
        "access_token": create_access_token(payload.username, role="admin"),
        "token_type": "bearer",
        "role": "admin",
        "expires_in": settings.auth_token_ttl_seconds,
    }


@router.get("/me")
def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict[str, object]:
    return {
        "username": user.username,
        "role": user.role,
        "auth_disabled": user.auth_disabled,
    }


@router.get("/audit")
def list_audit_logs(
    db: DbSession,
    _user: AuditUser,
    limit: int = 100,
) -> list[dict[str, object]]:
    return fetch_audit_logs(db, limit=min(max(limit, 1), 500))
