import asyncio
from sqlalchemy import select
from src.db.engine import engine, async_session_factory
from src.models.admin_user import AdminUser
from src.db.base import Base
from src.config import settings
from src.utils.crypto import hash_password

async def seed():
    async with async_session_factory() as session:
        result = await session.execute(select(AdminUser).where(AdminUser.username == settings.admin_username))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"Admin user '{settings.admin_username}' already exists.")
            return
        admin = AdminUser(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
        )
        session.add(admin)
        await session.commit()
        print(f"Admin user '{settings.admin_username}' created.")

if __name__ == "__main__":
    asyncio.run(seed())
