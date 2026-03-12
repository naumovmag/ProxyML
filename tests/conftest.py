import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import pool, select, delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.db.base import Base
from src.db.session import get_async_session
from src.config import settings

from src.models import Service, ApiKey, AdminUser, RequestLog

TEST_DATABASE_URL = settings.database_url

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=pool.NullPool)
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

# Track IDs created during tests so we only clean those up
_test_service_ids: list = []
_test_key_ids: list = []


async def override_get_session():
    async with test_session_factory() as session:
        yield session


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from src.utils.crypto import hash_password
    async with test_session_factory() as session:
        result = await session.execute(select(AdminUser).where(AdminUser.username == "admin"))
        if not result.scalar_one_or_none():
            session.add(AdminUser(username="admin", password_hash=await hash_password("admin123")))
            await session.commit()
    yield
    # Clean up ONLY test-created data
    async with test_session_factory() as session:
        if _test_service_ids:
            await session.execute(delete(Service).where(Service.id.in_(_test_service_ids)))
        if _test_key_ids:
            await session.execute(delete(ApiKey).where(ApiKey.id.in_(_test_key_ids)))
        await session.commit()


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
