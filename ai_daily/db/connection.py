"""Database connection and session management."""

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from ai_daily.config import config
from ai_daily.db.models import Base

# Sync engine and session
engine = create_engine(config.db.url, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# Async engine and session
async_engine = create_async_engine(config.db.async_url, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


async def init_db_async() -> None:
    """Initialize database tables asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a synchronous database session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an asynchronous database session."""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
