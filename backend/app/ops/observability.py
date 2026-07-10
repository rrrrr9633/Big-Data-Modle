from __future__ import annotations

from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.core.config import settings


def get_observability_status() -> dict[str, Any]:
    targets = {
        "prometheus": settings.prometheus_url,
        "grafana": settings.grafana_url,
    }
    checks = {name: _check_endpoint(url) for name, url in targets.items()}
    return {
        "status": "ok"
        if checks and all(item["status"] == "ok" for item in checks.values())
        else "warning",
        "endpoints": checks,
        "exporter_note": "业务服务只提供状态摘要；指标采集与告警规则由部署层维护。",
    }


def _check_endpoint(url: str) -> dict[str, str]:
    if not url:
        return {"status": "warning", "detail": "未配置"}
    try:
        request = Request(url, method="GET")
        with urlopen(request, timeout=settings.ops_http_timeout_seconds) as response:  # noqa: S310
            return {"status": "ok" if response.status < 400 else "warning", "url": url}
    except (URLError, TimeoutError, OSError) as exc:
        return {"status": "warning", "url": url, "detail": str(exc)}
