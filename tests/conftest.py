import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import pool, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.db.base import Base
from src.db.session import get_async_session
from src.config import settings

# Import models to register them with metadata
from src.models import Service, ApiKey, AdminUser

TEST_DATABASE_URL = settings.database_url

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=pool.NullPool)
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_session():
    async with test_session_factory() as session:
        yield session


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    from src.utils.crypto import hash_password
    async with test_session_factory() as session:
        result = await session.execute(select(AdminUser).where(AdminUser.username == "admin"))
        if not result.scalar_one_or_none():
            session.add(AdminUser(username="admin", password_hash=hash_password("admin123")))
            await session.commit()
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    from src.main import app
    app.dependency_overrides[get_async_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_token(client: AsyncClient):
    resp = await client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
async def admin_headers(admin_token: str):
    return {"Authorization": f"Bearer {admin_token}"}
