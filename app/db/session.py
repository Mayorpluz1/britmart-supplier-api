"""Database engine, session factory and transaction helpers."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from app.core.config import settings


def build_engine_options() -> dict[str, Any]:
    """Build database-specific SQLAlchemy engine options."""

    options: dict[str, Any] = {
        "echo": settings.database_echo,
        "pool_pre_ping": settings.database_pool_pre_ping,
    }

    if settings.is_sqlite:
        options["connect_args"] = {
            "check_same_thread": False,
        }
    else:
        options.update(
            {
                "pool_size": settings.database_pool_size,
                "max_overflow": settings.database_max_overflow,
                "pool_timeout": (
                    settings.database_pool_timeout_seconds
                ),
            }
        )

    return options


engine: Engine = create_engine(
    settings.database_url,
    **build_engine_options(),
)


if settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(
        dbapi_connection: SQLiteConnection,
        connection_record: ConnectionPoolEntry,
    ) -> None:
        """Enable foreign-key enforcement for every SQLite connection."""

        del connection_record

        cursor = dbapi_connection.cursor()

        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db_session() -> Generator[Session, None, None]:
    """
    Provide one database session for a FastAPI request.

    The endpoint or service controls transaction commits. Any unfinished
    transaction is rolled back when an exception occurs.
    """

    session = SessionLocal()

    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """
    Provide a transactional session for scripts and background jobs.

    The transaction is committed on success and rolled back on failure.
    """

    session = SessionLocal()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection() -> bool:
    """Execute a lightweight database connectivity check."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return True
    except Exception:
        return False


def check_foreign_key_enforcement() -> bool:
    """Confirm foreign-key enforcement is active where required."""

    if not settings.is_sqlite:
        return True

    with engine.connect() as connection:
        result = connection.execute(
            text("PRAGMA foreign_keys")
        ).scalar_one()

    return result == 1


def dispose_engine() -> None:
    """Release pooled database connections."""

    engine.dispose()