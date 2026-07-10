from __future__ import annotations

from typing import Any

from app.core.config import settings


def get_supervision_status() -> dict[str, Any]:
    mode = settings.supervision_mode.lower().strip()
    if mode not in {"docker", "systemd", "supervisor"}:
        return {
            "status": "warning",
            "mode": mode or None,
            "detail": "SUPERVISION_MODE 必须指定 docker、systemd 或 supervisor。",
            "processes": _processes("unmanaged"),
        }
    return {
        "status": "warning",
        "mode": mode,
        "detail": "已声明守护方式；需由部署控制面持续采集进程健康与重启次数。",
        "processes": _processes("configured"),
    }


def _processes(state: str) -> list[dict[str, Any]]:
    return [
        {"name": "fastapi", "state": state},
        {"name": "mqtt-to-kafka", "state": state},
        {"name": "raw-telemetry", "state": state},
        {"name": "cleaned-telemetry", "state": state},
        {"name": "feature-window", "state": state},
        {"name": "async-inference", "state": state},
        {"name": "edge-adapter", "state": state},
    ]
