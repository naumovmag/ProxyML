import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.db.base import Base
from src.db.session import get_async_session
from src.models import AdminUser  # noqa: F401

# Import every model module so SQLAlchemy registers all tables on
# Base.metadata before create_all runs. src.models.__init__ does not
# re-export every model (auth_system, auth_user, etc.), which breaks
# FK resolution in create_all.
import src.models.admin_user  # noqa: F401
import src.models.api_key  # noqa: F401
import src.models.auth_permission  # noqa: F401
import src.models.auth_refresh_token  # noqa: F401
import src.models.auth_role  # noqa: F401
import src.models.auth_system  # noqa: F401
import src.models.auth_user  # noqa: F401
import src.models.email_verification_token  # noqa: F401
import src.models.load_test  # noqa: F401
import src.models.model_route  # noqa: F401
import src.models.playground  # noqa: F401
import src.models.request_log  # noqa: F401
import src.models.service  # noqa: F401
import src.models.service_group  # noqa: F401
import src.models.service_share  # noqa: F401
import src.models.system_settings  # noqa: F401
import src.models.verification_channel  # noqa: F401
import src.models.verification_code  # noqa: F401

# Dedicated test database — NEVER reuse the dev/prod database.
# Tests create, mutate, and wipe data; doing that on the shared DB has
# already destroyed real user data twice. See
# ~/.claude/projects/.../memory/feedback_tests_separate_db.md
TEST_DB_NAME = f"{settings.db_database}_test"
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{settings.db_username}:{settings.db_password}"
    f"@{settings.db_host}:{settings.db_port}/{TEST_DB_NAME}"
)

# Kept for backwards compatibility: existing tests import these lists to
# register their created rows. With the isolated test DB they are no longer
# required for cleanup (drop_all wipes everything on next run).
_test_service_ids: list = []
_test_key_ids: list = []

test_engine = None
test_session_factory = None


async def _ensure_test_database() -> None:
    conn = await asyncpg.connect(
        user=settings.db_username,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


async def override_get_session():
    async with test_session_factory() as session:
        yield session


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    global test_engine, test_session_factory

    await _ensure_test_database()

    test_engine = create_async_engine(
        TEST_DATABASE_URL, echo=False, poolclass=pool.NullPool
    )
    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    from src.utils.crypto import hash_password

    async with test_session_factory() as session:
        session.add(
            AdminUser(
                username="admin",
                password_hash=await hash_password("admin123"),
                is_superadmin=True,
                is_approved=True,
                is_active=True,
            )
        )
        await session.commit()

    yield

    await test_engine.dispose()


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
