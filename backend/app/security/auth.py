from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class CurrentUser:
    username: str
    role: str
    scope: tuple[str, ...] = ()
    auth_disabled: bool = False


def create_access_token(username: str, role: str = "admin", scope: tuple[str, ...] = ()) -> str:
    payload = {
        "sub": username,
        "role": role,
        "scope": list(scope),
        "exp": int(time.time()) + settings.auth_token_ttl_seconds,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_part = _b64encode(payload_bytes)
    signature = _sign(payload_part)
    return f"{payload_part}.{signature}"


def verify_access_token(token: str) -> CurrentUser:
    try:
        payload_part, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="无效认证令牌") from exc

    if not hmac.compare_digest(signature, _sign(payload_part)):
        raise HTTPException(status_code=401, detail="无效认证令牌")

    try:
        payload = json.loads(_b64decode(payload_part))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="无效认证令牌") from exc

    if int(payload.get("exp") or 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="认证令牌已过期")

    username = str(payload.get("sub") or "")
    role = str(payload.get("role") or "")
    scope = tuple(str(item) for item in payload.get("scope", []) if isinstance(item, str))
    if not username or not role:
        raise HTTPException(status_code=401, detail="无效认证令牌")
    return CurrentUser(username=username, role=role, scope=scope)


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    if not settings.auth_enabled:
        return CurrentUser(username="auth-disabled", role="admin", auth_disabled=True)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少认证令牌")
    return verify_access_token(authorization.removeprefix("Bearer ").strip())


def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def _sign(payload_part: str) -> str:
    digest = hmac.new(
        settings.auth_token_secret.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64encode(digest)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")
