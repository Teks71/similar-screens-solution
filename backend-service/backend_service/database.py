import logging
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import BackendSettings, get_settings


logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_session_factory(settings: BackendSettings) -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory
    if _session_factory is None:
        if not settings.postgres_url:
            raise RuntimeError("POSTGRES_URL is required to initialize the database connection")
        _engine = create_async_engine(settings.postgres_url, future=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


async def get_db_session(
    settings: BackendSettings = Depends(get_settings),
) -> AsyncGenerator[AsyncSession, None]:
    session_factory = _ensure_session_factory(settings)
    async with session_factory() as session:
        yield session


async def ping_database(settings: BackendSettings | None = None) -> None:
    """Validate database connectivity on startup."""
    global _engine
    settings = settings or get_settings()
    _ensure_session_factory(settings)
    assert _engine is not None
    try:
        async with _engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        logger.info(
            "PostgreSQL connectivity check succeeded",
            extra={
                "event": "backend.db.ping_ok",
                "postgres_host": settings.postgres_host,
                "postgres_port": settings.postgres_port,
                "postgres_db": settings.postgres_db,
                "postgres_user": settings.postgres_user,
            },
        )
    except Exception:
        logger.exception(
            "PostgreSQL connectivity check failed",
            extra={
                "event": "backend.db.ping_failed",
                "postgres_host": settings.postgres_host,
                "postgres_port": settings.postgres_port,
                "postgres_db": settings.postgres_db,
                "postgres_user": settings.postgres_user,
            },
        )
        raise


async def close_database() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
