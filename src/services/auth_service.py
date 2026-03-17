import uuid
from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.models.admin_user import AdminUser
from src.utils.crypto import verify_password, hash_password


async def authenticate_admin(session: AsyncSession, username: str, password: str) -> AdminUser | None:
    result = await session.execute(
        select(AdminUser).where(AdminUser.username == username, AdminUser.is_active == True)
    )
    user = result.scalar_one_or_none()
    if user and await verify_password(password, user.password_hash):
        if not user.is_approved:
            return None
        return user
    return None


async def register_user(
    session: AsyncSession,
    username: str,
    password: str,
    email: str | None = None,
    display_name: str | None = None,
) -> AdminUser:
    user = AdminUser(
        username=username,
        password_hash=await hash_password(password),
        email=email,
        display_name=display_name,
        is_superadmin=False,
        is_approved=False,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> AdminUser | None:
    result = await session.execute(select(AdminUser).where(AdminUser.id == user_id))
    return result.scalar_one_or_none()


def create_access_token(user_id: str, is_superadmin: bool = False) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "is_superadmin": is_superadmin, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
