"""Database-session dependencies for FastAPI request processing."""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_database_session() -> Generator[Session, None, None]:
    """
    Provide one SQLAlchemy session for a single API request.

    The session is committed by application services when a write operation
    succeeds. Any unhandled error rolls back pending work, and the session is
    always closed when request processing finishes.
    """

    database_session = SessionLocal()

    try:
        yield database_session
    except Exception:
        database_session.rollback()
        raise
    finally:
        database_session.close()


DatabaseSession = Annotated[
    Session,
    Depends(get_database_session),
]