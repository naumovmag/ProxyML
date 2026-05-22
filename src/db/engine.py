from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=10,
    pool_pre_ping=True,
    pool_timeout=5,
    pool_recycle=1800,
    pool_reset_on_return="rollback",
)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Separate engine for background / long-running work (request logging, maintenance cleanup).
# Uses NullPool so each operation opens and closes its own connection — won't compete with
# the request-path pool and won't pin PG connections between calls.
background_engine = create_async_engine(
    settings.database_url,
    echo=False,
    poolclass=NullPool,
)
background_session_factory = async_sessionmaker(
    background_engine, class_=AsyncSession, expire_on_commit=False
)
