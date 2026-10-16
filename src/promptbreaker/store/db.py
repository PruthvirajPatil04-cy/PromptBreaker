"""Async DB session/engine helpers. DATABASE_URL decides sqlite vs postgres —
no code changes required to move between them."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from promptbreaker.config import settings
from promptbreaker.store.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(settings.database_url, echo=False, future=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


async def init_db() -> None:
    """Create tables (dev/bootstrap). Production uses Alembic expand-contract."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_expand_existing_tables)


def _expand_existing_tables(sync_conn) -> None:  # noqa: ANN001 — SQLAlchemy sync conn
    """Expand-contract migration: add any model columns missing from existing
    tables. create_all() only creates ABSENT tables, so upgrading an existing
    deployment needs the new columns added explicitly. New columns are all
    nullable/defaulted, so this is backward-compatible by construction."""
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(sync_conn)
    existing = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            continue  # create_all already made it whole
        have = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue
            nullable = col.nullable or col.default is not None or col.server_default is not None
            if not nullable:
                continue  # never add a NOT NULL column to a live table
            col_type = col.type.compile(sync_conn.dialect)
            sync_conn.exec_driver_sql(
                f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}'
            )


async def session_scope() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
