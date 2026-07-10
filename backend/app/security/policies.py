from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException

from app.security.auth import CurrentUser, get_current_user

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({"*"}),
    "engineer": frozenset(
        {
            "device.read",
            "device.change.submit",
            "edge.config.export",
            "model.train",
            "warning.handle",
        }
    ),
    "approver": frozenset(
        {"device.read", "device.change.approve", "model.approve", "model.activate"}
    ),
    "operator": frozenset({"device.read", "warning.handle"}),
    "ops": frozenset({"device.read", "edge.config.export", "ops.read", "audit.read"}),
    "viewer": frozenset({"device.read"}),
}


def has_permission(user: CurrentUser, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(user.role, frozenset())
    return "*" in permissions or permission in permissions


def require_permission(permission: str) -> Callable[..., CurrentUser]:
    def dependency(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if not has_permission(user, permission):
            raise HTTPException(status_code=403, detail=f"缺少权限点：{permission}")
        return user

    return dependency
