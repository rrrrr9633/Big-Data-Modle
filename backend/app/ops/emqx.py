from __future__ import annotations

import base64
import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.core.config import settings


def get_emqx_status() -> dict[str, Any]:
    base_url = settings.emqx_management_url.rstrip("/")
    if not base_url:
        return _warning("EMQX_MANAGEMENT_URL 未配置")
    try:
        stats = _get_json(f"{base_url}/api/v5/stats")
        clients = _get_json(f"{base_url}/api/v5/clients?limit=5")
        return {
            "status": "ok",
            "management_url": base_url,
            "stats": stats,
            "clients": clients.get("data", clients),
        }
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        return _warning(str(exc), management_url=base_url)


def _get_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    if settings.emqx_management_username:
        credentials = (
            f"{settings.emqx_management_username}:{settings.emqx_management_password}".encode()
        )
        request.add_header("Authorization", f"Basic {base64.b64encode(credentials).decode()}")
    with urlopen(request, timeout=settings.ops_http_timeout_seconds) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {"data": payload}


def _warning(detail: str, **context: str) -> dict[str, Any]:
    return {"status": "warning", "detail": detail, **context, "stats": {}, "clients": []}
