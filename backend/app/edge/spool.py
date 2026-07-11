from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from app.ingestion.schemas import TelemetryEvent, parse_telemetry_event


class EdgeSpool:
    """Durable, ordered outbox for an edge gateway's outbound telemetry."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_events (
              sequence INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT NOT NULL UNIQUE,
              payload TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def enqueue(self, events: list[TelemetryEvent]) -> None:
        self._connection.executemany(
            "INSERT OR IGNORE INTO pending_events (event_id, payload) VALUES (?, ?)",
            [(event.event_id, event.model_dump_json()) for event in events],
        )
        self._connection.commit()

    def flush(self, publish: Callable[[TelemetryEvent], None]) -> int:
        delivered = 0
        while row := self._connection.execute(
            "SELECT sequence, payload FROM pending_events ORDER BY sequence LIMIT 1"
        ).fetchone():
            sequence, payload = row
            event = parse_telemetry_event(payload)
            publish(event)
            self._connection.execute("DELETE FROM pending_events WHERE sequence = ?", (sequence,))
            self._connection.commit()
            delivered += 1
        return delivered

    def pending_count(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) FROM pending_events").fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        self._connection.close()
