"""Async database engine and session factory for HiveMind.

Usage:
    from hivemind.db.session import get_session

    async with get_session() as session:
        result = await session.execute(select(KnowledgeItem))

IMPORTANT: Each request/operation must get its own session from the factory.
AsyncSession is NOT safe to share across concurrent coroutines or requests.
The get_session() context manager ensures each caller gets a fresh session
that is properly closed and returned to the pool on exit.
"""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from hivemind.config import settings

# Module-level async engine — shared across the process lifetime
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

# Session factory — call AsyncSessionFactory() to get a new session
# expire_on_commit=False keeps ORM objects accessible after commit
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Async context manager that yields a database session.

    Yields a fresh AsyncSession for each call.  The session is closed and
    its connection returned to the pool when the context exits, whether
    normally or via exception.

    Example:
        async with get_session() as session:
            await session.execute(...)
            await session.commit()
    """
    async with AsyncSessionFactory() as session:
        yield session
