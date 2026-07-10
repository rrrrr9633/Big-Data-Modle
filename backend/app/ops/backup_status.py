from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings


def get_backup_status() -> dict[str, Any]:
    status_file = Path(settings.backup_status_file)
    if not settings.backup_status_file:
        return _warning("BACKUP_STATUS_FILE 未配置")
    if not status_file.is_file():
        return _warning(f"备份状态文件不存在：{status_file}")
    try:
        payload = json.loads(status_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _warning(f"无法读取备份状态：{exc}")
    if not isinstance(payload, dict):
        return _warning("备份状态文件必须是 JSON 对象")
    required = {"mysql", "timescaledb", "restore_drill"}
    missing = sorted(required - payload.keys())
    return {
        "status": "warning" if missing else str(payload.get("status") or "ok"),
        "source": str(status_file),
        "missing_sections": missing,
        "backups": payload,
    }


def _warning(detail: str) -> dict[str, Any]:
    return {"status": "warning", "detail": detail, "backups": {}, "missing_sections": []}
