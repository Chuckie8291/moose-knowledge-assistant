"""
Dependency injection — provides database sessions, clients, and services.
"""

from typing import AsyncGenerator, Optional

from app.config import settings

# ── Database Engine (lazy import — may not be available in dev) ─

try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.orm import DeclarativeBase

    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        echo=settings.debug,
    )

    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    class Base(DeclarativeBase):
        """Declarative base for all ORM models."""
        pass

    _db_available = True

except ImportError:
    engine = None
    async_session_factory = None

    class Base:
        pass

    _db_available = False


async def init_db() -> None:
    """Create tables on startup (dev only; use Alembic in production)."""
    if not _db_available or engine is None:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose engine on shutdown."""
    if engine:
        await engine.dispose()


async def get_db():
    """FastAPI dependency: yields a database session."""
    if not _db_available or not async_session_factory:
        raise RuntimeError("Database is not available")
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
