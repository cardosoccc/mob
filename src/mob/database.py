"""Database session management."""

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mob.config import get_settings
from mob.models.base import Base

_engine = None
_session_factory = None


def get_engine(database_url: str | None = None):
    global _engine
    if _engine is None or database_url is not None:
        url = database_url or get_settings().database_url
        _engine = create_async_engine(url, echo=False)
    return _engine


def get_session_factory(database_url: str | None = None) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None or database_url is not None:
        engine = get_engine(database_url)
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db(database_url: str | None = None) -> None:
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


def _add_missing_columns(conn) -> None:
    """Add columns that create_all won't add to existing tables.

    SQLite cannot add NOT NULL columns without a default to tables with
    existing rows, so new non-nullable columns are added as nullable first,
    backfilled, and then left as-is (SQLite cannot alter column constraints).
    """
    inspector = inspect(conn)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing:
                col_type = column.type.compile(conn.dialect)
                # Always add as nullable to avoid errors on existing rows
                conn.execute(text(
                    f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"
                ))
                # Backfill NULLs with a generated value based on the row id
                if not column.nullable:
                    conn.execute(text(
                        f"UPDATE {table.name} SET {column.name} = "
                        f"'{table.name}-' || substr(id, 1, 8) "
                        f"WHERE {column.name} IS NULL"
                    ))


async def close_db() -> None:
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
