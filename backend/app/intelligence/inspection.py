from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.intelligence.rag import ingest_inspection_run_to_knowledge
from app.intelligence.tools import gather_operational_facts
from app.models.registry import get_active_model_state
from app.repositories import intelligence_repository as repo

logger = logging.getLogger(__name__)


class InspectionScheduler:
    """Stoppable hourly inspection worker with re-entry protection.

    Runtime schedule is configurable in-process (PUT schedule). Env values are
    defaults; database schedule is loaded best-effort on start.
    """

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._running_job = False
        self._last_hour_slot: str | None = None
        self._last_error: str | None = None
        self._started = False
        # Env defaults; may be overridden by configure() / DB load.
        self._enabled = bool(settings.inspection_enabled)
        self._minute = int(settings.inspection_minute) % 60
        self._device_limit = max(int(settings.inspection_device_limit), 1)

    def configure(
        self,
        *,
        enabled: bool,
        minute_of_hour: int,
        device_limit: int,
    ) -> dict[str, Any]:
        with self._lock:
            self._enabled = bool(enabled)
            self._minute = int(minute_of_hour) % 60
            self._device_limit = max(int(device_limit), 1)
            # Changing schedule should allow the next matching hour slot to fire.
            self._last_hour_slot = None
            return self._runtime_schedule_unlocked()

    def load_from_database_best_effort(self) -> bool:
        """Load persisted schedule if DB is available. Never raises."""
        try:
            from app.core.database import ensure_mysql_database

            ensure_mysql_database()
            db = SessionLocal()
            try:
                schedule = repo.get_inspection_schedule(
                    db,
                    default_enabled=settings.inspection_enabled,
                    default_minute=settings.inspection_minute,
                    default_device_limit=settings.inspection_device_limit,
                )
                self.configure(
                    enabled=bool(schedule.get("enabled")),
                    minute_of_hour=int(schedule.get("minute_of_hour") or 0),
                    device_limit=int(
                        schedule.get("device_limit") or settings.inspection_device_limit
                    ),
                )
                logger.info(
                    "Inspection schedule loaded from DB: enabled=%s minute=%s limit=%s",
                    self._enabled,
                    self._minute,
                    self._device_limit,
                )
                return True
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Inspection schedule DB load skipped (using env defaults): %s",
                exc,
            )
            return False

    def start(self) -> None:
        self.load_from_database_best_effort()
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="inspection-scheduler",
                daemon=True,
            )
            self._thread.start()
            self._started = True
            logger.info(
                "Inspection scheduler started (enabled=%s minute=%s limit=%s)",
                self._enabled,
                self._minute,
                self._device_limit,
            )

    def stop(self, *, timeout: float = 2.0) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        with self._lock:
            self._thread = None
            self._started = False
        logger.info("Inspection scheduler stopped")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "started": self._started,
                "thread_alive": bool(self._thread and self._thread.is_alive()),
                "running_job": self._running_job,
                "enabled": self._enabled,
                "minute_of_hour": self._minute,
                "device_limit": self._device_limit,
                "last_hour_slot": self._last_hour_slot,
                "last_error": self._last_error,
                "schedule": self._runtime_schedule_unlocked(),
            }

    def _runtime_schedule_unlocked(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "minute_of_hour": self._minute,
            "device_limit": self._device_limit,
        }

    def run_once(self, *, trigger_type: str = "manual") -> dict[str, Any]:
        with self._lock:
            if self._running_job:
                return {
                    "accepted": False,
                    "reason": "inspection already running",
                    "status": "busy",
                }
            self._running_job = True
            device_limit = self._device_limit

        try:
            return self._execute_run(trigger_type=trigger_type, device_limit=device_limit)
        finally:
            with self._lock:
                self._running_job = False

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._maybe_trigger_scheduled()
            except Exception as exc:  # noqa: BLE001
                self._last_error = str(exc)
                logger.exception("Inspection scheduler tick failed")
            self._stop_event.wait(max(settings.inspection_poll_seconds, 1.0))

    def _maybe_trigger_scheduled(self) -> None:
        with self._lock:
            enabled = self._enabled
            minute = self._minute
        if not enabled:
            return
        now = datetime.now(timezone.utc).astimezone()
        if now.minute != (int(minute) % 60):
            return
        slot = now.strftime("%Y-%m-%dT%H")
        with self._lock:
            if self._last_hour_slot == slot:
                return
            if self._running_job:
                return
            self._last_hour_slot = slot
        result = self.run_once(trigger_type="scheduled")
        if not result.get("accepted", True) and result.get("status") == "busy":
            with self._lock:
                if self._last_hour_slot == slot:
                    self._last_hour_slot = None

    def _execute_run(self, *, trigger_type: str, device_limit: int) -> dict[str, Any]:
        db = SessionLocal()
        run_id: int | None = None
        try:
            run_id = repo.create_inspection_run(db, trigger_type=trigger_type, status="running")
            db.commit()

            model_state = get_active_model_state()
            if not model_state.available:
                message = "active 模型不可用，巡检失败"
                repo.finish_inspection_run(
                    db,
                    run_id=run_id,
                    status="failed",
                    summary=message,
                    device_total=0,
                    issue_total=0,
                    error_message=message,
                )
                db.commit()
                self._last_error = message
                return {
                    "accepted": True,
                    "run_id": run_id,
                    "status": "failed",
                    "error_message": message,
                }

            facts = gather_operational_facts(db)
            realtime = facts.get("realtime.overview") or {}
            devices = realtime.get("devices") if isinstance(realtime, dict) else []
            if not isinstance(devices, list):
                devices = []
            devices = devices[: max(device_limit, 1)]

            issue_total = 0
            for device in devices:
                if not isinstance(device, dict):
                    continue
                findings = _inspect_device(device)
                if not findings:
                    continue
                severity = findings[0]["severity"]
                title = findings[0]["title"]
                detail = findings[0]["detail"]
                repo.insert_inspection_report(
                    db,
                    run_id=run_id,
                    device_code=str(device.get("device_code") or ""),
                    severity=severity,
                    title=title,
                    detail=detail,
                    findings=findings,
                )
                issue_total += 1

            summary = (
                f"巡检完成：扫描 {len(devices)} 台设备，发现 {issue_total} 项问题。"
            )
            repo.finish_inspection_run(
                db,
                run_id=run_id,
                status="completed",
                summary=summary,
                device_total=len(devices),
                issue_total=issue_total,
                error_message=None,
            )
            repo.touch_inspection_schedule(db, last_run_id=run_id)
            knowledge = ingest_inspection_run_to_knowledge(db, run_id=run_id)
            db.commit()
            self._last_error = None
            return {
                "accepted": True,
                "run_id": run_id,
                "status": "completed",
                "device_total": len(devices),
                "issue_total": issue_total,
                "summary": summary,
                "knowledge": knowledge,
            }
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            self._last_error = str(exc)
            if run_id is not None:
                try:
                    repo.finish_inspection_run(
                        db,
                        run_id=run_id,
                        status="failed",
                        summary="巡检执行异常",
                        device_total=0,
                        issue_total=0,
                        error_message=str(exc),
                    )
                    db.commit()
                except Exception:  # noqa: BLE001
                    db.rollback()
            logger.exception("Inspection run failed")
            return {
                "accepted": True,
                "run_id": run_id,
                "status": "failed",
                "error_message": str(exc),
            }
        finally:
            db.close()


def _inspect_device(device: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    device_code = str(device.get("device_code") or "unknown")
    online = bool(device.get("online"))
    prediction = device.get("latest_prediction")
    warning = device.get("latest_warning")

    if not online:
        findings.append(
            {
                "severity": "medium",
                "title": f"{device_code} 离线",
                "detail": "实时快照显示设备当前不在线。",
            }
        )

    risk = None
    health = None
    if isinstance(prediction, dict):
        risk = prediction.get("risk_level")
        health = prediction.get("health_score")
        if str(risk) in {"high", "critical"}:
            findings.append(
                {
                    "severity": str(risk),
                    "title": f"{device_code} 高风险预测",
                    "detail": (
                        f"风险={risk} 健康分={health} "
                        f"故障概率={prediction.get('failure_probability')}"
                    ),
                }
            )
        elif health is not None:
            try:
                if float(health) < 60:
                    findings.append(
                        {
                            "severity": "medium",
                            "title": f"{device_code} 健康分偏低",
                            "detail": f"健康分={health}",
                        }
                    )
            except (TypeError, ValueError):
                pass

    if isinstance(warning, dict) and str(warning.get("status")) in {"new", "pending", "processing"}:
        findings.append(
            {
                "severity": str(warning.get("risk_level") or "medium"),
                "title": f"{device_code} 存在未关闭预警",
                "detail": str(warning.get("title") or warning.get("detail") or ""),
            }
        )

    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
    findings.sort(key=lambda item: -severity_rank.get(str(item.get("severity")), 0))
    return findings


inspection_scheduler = InspectionScheduler()
