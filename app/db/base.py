"""Shared SQLAlchemy base classes and model mixins."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, MetaData
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": (
        "fk_%(table_name)s_%(column_0_N_name)s_"
        "%(referred_table_name)s"
    ),
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for every BritMart database model."""

    metadata = metadata


class TimestampMixin:
    """Add standard UTC creation and update timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        index=True,
    )


class VersionMixin:
    """Add an optimistic-concurrency version number."""

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )


class AuditMixin(TimestampMixin, VersionMixin):
    """Combine timestamps and versioning for operational tables."""

    pass