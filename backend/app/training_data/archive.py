"""Append-only journal + locked batch materialization for daily AI4I CSV archives."""

from __future__ import annotations

import csv
import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from app.core.config import settings
from app.ingestion.http_schemas import TelemetryPayloadIn
from app.training_data.schema import AI4I_CSV_HEADERS, project_telemetry_to_ai4i_row, validate_ai4i_row

logger = logging.getLogger(__name__)

_DEFAULT_ARCHIVE = "artifacts/datasets/daily"
_default_instance: Ai4iDailyArchive | None = None
_default_lock = threading.Lock()


@dataclass(frozen=True)
class MaterializeResult:
    day: str
    row_count: int
    csv_path: Path
    manifest_path: Path
    skipped_corrupt_lines: int


class Ai4iDailyArchive:
    """Daily AI4I archive: append journal lines, then materialize standard CSV + manifest."""

    def __init__(
        self,
        root: Path | str | None = None,
        *,
        materialize_every: int = 1,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else resolve_archive_dir()
        self.materialize_every = max(int(materialize_every), 1)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._appends_since_materialize = 0
        self._current_day: str | None = None
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "journal").mkdir(parents=True, exist_ok=True)

    def archive_payload(self, payload: TelemetryPayloadIn, *, mode: str = "normal") -> dict[str, str]:
        """Project payload, append journal, and maybe materialize. Safe for concurrent writers."""
        now = self._clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        day = now.date().isoformat()
        row = project_telemetry_to_ai4i_row(payload, mode=mode, recorded_at=payload.recorded_at or now)
        with self._lock:
            self._maybe_switch_day(day)
            self._append_journal(day, row, mode=mode, archived_at=now)
            self._appends_since_materialize += 1
            if self._appends_since_materialize >= self.materialize_every:
                self.materialize_day(day)
                self._appends_since_materialize = 0
        return row

    def materialize_day(self, day: str | date | None = None) -> MaterializeResult:
        """Rebuild standard CSV + manifest from journal with lock; training should only read CSV."""
        day_key = _day_key(day or self._clock().date())
        with self._lock:
            journal_path = self.journal_path(day_key)
            rows, skipped = self._read_journal_rows(journal_path)
            deduped = _dedupe_rows(rows)
            csv_path = self.csv_path(day_key)
            manifest_path = self.manifest_path(day_key)
            self._atomic_write_csv(csv_path, deduped)
            manifest = {
                "day": day_key,
                "row_count": len(deduped),
                "journal_path": str(journal_path),
                "csv_path": str(csv_path),
                "skipped_corrupt_lines": skipped,
                "materialized_at": self._clock().astimezone(timezone.utc).isoformat(),
                "headers": list(AI4I_CSV_HEADERS),
            }
            self._atomic_write_json(manifest_path, manifest)
            self._current_day = day_key
            return MaterializeResult(
                day=day_key,
                row_count=len(deduped),
                csv_path=csv_path,
                manifest_path=manifest_path,
                skipped_corrupt_lines=skipped,
            )

    def list_materialized_csv_files(self) -> list[Path]:
        """Training loaders only use materialized CSV files, never open journals."""
        if not self.root.exists():
            return []
        files = sorted(
            path
            for path in self.root.glob("*.csv")
            if path.is_file() and path.name[:1].isdigit()
        )
        return files

    def load_materialized_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for path in self.list_materialized_csv_files():
            rows.extend(_read_csv_rows(path))
        return _dedupe_rows(rows)

    def journal_path(self, day: str) -> Path:
        return self.root / "journal" / f"{day}.jsonl"

    def csv_path(self, day: str) -> Path:
        return self.root / f"{day}.csv"

    def manifest_path(self, day: str) -> Path:
        return self.root / f"{day}.manifest.json"

    def _maybe_switch_day(self, day: str) -> None:
        if self._current_day is None:
            self._current_day = day
            return
        if self._current_day != day:
            # Flush previous day before opening a new journal day.
            try:
                self.materialize_day(self._current_day)
            except Exception:
                logger.exception("Failed to materialize previous archive day %s", self._current_day)
            self._current_day = day
            self._appends_since_materialize = 0

    def _append_journal(
        self,
        day: str,
        row: dict[str, str],
        *,
        mode: str,
        archived_at: datetime,
    ) -> None:
        path = self.journal_path(day)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "archived_at": archived_at.astimezone(timezone.utc).isoformat(),
            "mode": mode,
            "row": row,
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _read_journal_rows(self, path: Path) -> tuple[list[dict[str, str]], int]:
        if not path.exists():
            return [], 0
        rows: list[dict[str, str]] = []
        skipped = 0
        raw = path.read_text(encoding="utf-8")
        if not raw:
            return [], 0
        lines = raw.splitlines()
        # If the file does not end with newline, the last line may be a torn write.
        torn_tail = not raw.endswith("\n") and bool(lines)
        for index, line in enumerate(lines):
            text = line.strip()
            if not text:
                continue
            is_last = index == len(lines) - 1
            try:
                payload = json.loads(text)
                row = payload.get("row") if isinstance(payload, dict) else None
                if not isinstance(row, dict):
                    raise ValueError("journal entry missing row object")
                as_str = {str(key): str(value) for key, value in row.items()}
                validate_ai4i_row(as_str)
                rows.append(as_str)
            except Exception:
                if is_last and torn_tail:
                    logger.warning("Skipping corrupt journal tail in %s", path)
                    skipped += 1
                    continue
                logger.warning("Skipping corrupt journal line in %s: %s", path, text[:120])
                skipped += 1
        return rows, skipped

    def _atomic_write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(AI4I_CSV_HEADERS), extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({header: row.get(header, "") for header in AI4I_CSV_HEADERS})
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)

    def _atomic_write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)


def resolve_archive_dir() -> Path:
    configured = getattr(settings, "ai4i_archive_dir", _DEFAULT_ARCHIVE)
    path = Path(str(configured)).expanduser()
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


def resolve_base_dataset_path() -> Path:
    configured = getattr(
        settings,
        "ai4i_base_dataset_path",
        getattr(settings, "simulation_model_dataset_path", "../ai4i2020.csv"),
    )
    path = Path(str(configured)).expanduser()
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


def get_default_archive() -> Ai4iDailyArchive:
    global _default_instance
    with _default_lock:
        if _default_instance is None:
            _default_instance = Ai4iDailyArchive()
        return _default_instance


def default_archive_observer(payload: TelemetryPayloadIn, *, mode: str = "normal") -> None:
    """Default device-stream archive hook; failures must be handled by the caller."""
    get_default_archive().archive_payload(payload, mode=mode)


def _day_key(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for row in rows:
        udi = str(row.get("UDI", "")).strip()
        key = udi or json.dumps(row, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [{str(k): str(v) for k, v in row.items() if k is not None} for row in csv.DictReader(handle)]
