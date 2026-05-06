from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=30,
    max_overflow=20,
    pool_pre_ping=True,
    pool_timeout=5,
    pool_recycle=1800,
    pool_reset_on_return="rollback",
)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
