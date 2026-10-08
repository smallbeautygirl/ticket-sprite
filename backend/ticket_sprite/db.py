from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(url: str) -> AsyncEngine:
    global _engine, _sessionmaker
    _engine = create_async_engine(url)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def _add_missing_columns(conn: Connection) -> None:
    """Additive schema changes on an existing database: new nullable columns only.

    create_all() makes missing tables but never alters existing ones; anything beyond
    adding a nullable column needs a real migration.
    """
    inspector = inspect(conn)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        have = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in have:
                continue
            if not column.nullable:
                raise RuntimeError(f"{table.name}.{column.name} is NOT NULL; add it with a migration")
            ddl = column.type.compile(dialect=conn.dialect)
            conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl}')


def _move_game_scores(conn: Connection) -> None:
    """game_scores (firefly only, keyed by email) became game_bests, keyed by game and email."""
    if not inspect(conn).has_table("game_scores"):
        return
    conn.exec_driver_sql(
        "INSERT INTO game_bests (game, email, best, achieved_at) "
        "SELECT 'firefly', email, best, achieved_at FROM game_scores"
    )
    conn.exec_driver_sql("DROP TABLE game_scores")


async def create_all() -> None:
    assert _engine is not None
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
        await conn.run_sync(_move_game_scores)


def sessionmaker() -> async_sessionmaker[AsyncSession]:
    assert _sessionmaker is not None, "init_engine() not called"
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with sessionmaker()() as session:
        yield session
