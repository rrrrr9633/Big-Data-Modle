from collections.abc import Generator
from pathlib import Path
from threading import Lock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine: Engine = create_engine(settings.mysql_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
_database_ready = False
_schema_ready = False
_database_ready_lock = Lock()


def ensure_mysql_database() -> None:
    global _database_ready, _schema_ready
    if _database_ready and _schema_ready:
        return
    with _database_ready_lock:
        if not _database_ready:
            _create_mysql_database()
            _database_ready = True
        if not _schema_ready:
            _bootstrap_mysql_schema()
            _schema_ready = True


def _create_mysql_database() -> None:
    url = make_url(settings.mysql_url)
    database = url.database
    if url.get_backend_name() != "mysql" or not database:
        return
    server_engine = create_engine(_mysql_server_url(settings.mysql_url), pool_pre_ping=True)
    try:
        escaped_database = database.replace("`", "``")
        with server_engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE DATABASE IF NOT EXISTS "
                    f"`{escaped_database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
    finally:
        server_engine.dispose()


def _bootstrap_mysql_schema() -> None:
    schema_path = Path(__file__).resolve().parents[3] / "infra" / "mysql" / "init.sql"
    statements = schema_path.read_text(encoding="utf-8").split(";")
    with engine.begin() as connection:
        for statement in statements:
            normalized = statement.strip()
            if not normalized or normalized.upper().startswith(("CREATE DATABASE", "USE ")):
                continue
            connection.exec_driver_sql(normalized)


def _mysql_server_url(database_url: str):
    return make_url(database_url)._replace(database=None)


def get_db() -> Generator[Session, None, None]:
    ensure_mysql_database()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
