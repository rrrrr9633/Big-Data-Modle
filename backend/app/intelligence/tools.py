from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.intelligence.types import ToolResult
from app.models.registry import get_active_model_state
from app.realtime.overview import fetch_realtime_overview
from app.repositories import maintenance_repository as maintenance
from app.services.simulation_runtime import runtime as simulation_runtime


def collect_realtime_facts(db: Session) -> ToolResult:
    try:
        overview = fetch_realtime_overview(db)
        devices = overview.get("devices") if isinstance(overview, dict) else []
        high_risk = []
        if isinstance(devices, list):
            for item in devices:
                if not isinstance(item, dict):
                    continue
                prediction = item.get("latest_prediction")
                risk = (
                    prediction.get("risk_level")
                    if isinstance(prediction, dict)
                    else item.get("risk_level")
                )
                if str(risk) in {"high", "critical"}:
                    high_risk.append(
                        {
                            "device_code": item.get("device_code"),
                            "risk_level": risk,
                            "health_score": (
                                prediction.get("health_score")
                                if isinstance(prediction, dict)
                                else None
                            ),
                        }
                    )
        data = {
            "device_total": overview.get("device_total", 0) if isinstance(overview, dict) else 0,
            "online_total": overview.get("online_total", 0) if isinstance(overview, dict) else 0,
            "warning_total": overview.get("warning_total", 0) if isinstance(overview, dict) else 0,
            "prediction_total": (
                overview.get("prediction_total", 0) if isinstance(overview, dict) else 0
            ),
            "high_risk_devices": high_risk[:20],
            "devices": devices if isinstance(devices, list) else [],
        }
        return ToolResult(name="realtime.overview", ok=True, data=data)
    except Exception as exc:  # noqa: BLE001 - tool boundary must stay soft
        return ToolResult(name="realtime.overview", ok=False, error=str(exc))


def collect_maintenance_facts(db: Session, *, limit: int = 20) -> ToolResult:
    try:
        summary = maintenance.fetch_dashboard_summary(db)
        warnings = maintenance.fetch_warnings(db, limit=limit)
        predictions = maintenance.fetch_predictions(db, limit=limit)
        data = {
            "summary": summary,
            "recent_warnings": _compact_warnings(warnings),
            "recent_predictions": _compact_predictions(predictions),
        }
        return ToolResult(name="maintenance.repository", ok=True, data=data)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(name="maintenance.repository", ok=False, error=str(exc))


def collect_simulation_facts() -> ToolResult:
    try:
        state = simulation_runtime.snapshot()
        data = {
            "running": state.running,
            "cycle": state.cycle,
            "mode": state.config.mode,
            "device_count": state.config.device_count,
            "transport": state.config.transport,
            "devices": list(state.device_codes),
            "last_error": state.last_error,
            "accepted_events": state.accepted_events,
            "failed_cycles": state.failed_cycles,
        }
        return ToolResult(name="simulation.runtime", ok=True, data=data)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(name="simulation.runtime", ok=False, error=str(exc))


def collect_model_facts() -> ToolResult:
    try:
        state = get_active_model_state()
        data = {
            "available": state.available,
            "path": state.path,
            "saved_at": state.saved_at,
            "model_names": state.model_names,
        }
        return ToolResult(name="model.registry", ok=True, data=data)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(name="model.registry", ok=False, error=str(exc))


def gather_operational_facts(db: Session) -> dict[str, Any]:
    tools = [
        collect_realtime_facts(db),
        collect_maintenance_facts(db),
        collect_simulation_facts(),
        collect_model_facts(),
    ]
    facts: dict[str, Any] = {
        "tools": [item.to_dict() for item in tools],
    }
    for item in tools:
        if item.ok:
            facts[item.name] = item.data
    return facts


def _compact_warnings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for row in rows[:20]:
        compact.append(
            {
                "id": row.get("id"),
                "device_code": row.get("device_code"),
                "risk_level": row.get("risk_level"),
                "title": row.get("title"),
                "status": row.get("status"),
                "created_at": str(row.get("created_at") or ""),
            }
        )
    return compact


def _compact_predictions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for row in rows[:20]:
        compact.append(
            {
                "id": row.get("id"),
                "device_code": row.get("device_code"),
                "risk_level": row.get("risk_level"),
                "health_score": row.get("health_score"),
                "failure_probability": row.get("failure_probability"),
                "created_at": str(row.get("created_at") or ""),
            }
        )
    return compact
