"""Database engine and session management.

Provides:
- Async engine for FastAPI request handling
- Sync engine for Alembic migrations and seed scripts
- A FastAPI dependency `get_session` that yields an async session
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, create_engine

from app.config import settings

# --- Async engine (used by FastAPI app) ---
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    Usage in routes:
        @router.post("/something")
        async def create_something(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# --- Sync engine (used by Alembic and seed script) ---
sync_engine = create_engine(settings.sync_database_url, echo=False)
