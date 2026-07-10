from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from app.core.config import settings


@contextmanager
def tsdb_connection() -> Iterator[object]:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is not installed") from exc

    conn = psycopg.connect(settings.tsdb_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()