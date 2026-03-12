from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.models.admin_user import AdminUser
from src.utils.crypto import verify_password

async def authenticate_admin(session: AsyncSession, username: str, password: str) -> AdminUser | None:
    result = await session.execute(select(AdminUser).where(AdminUser.username == username, AdminUser.is_active == True))
    user = result.scalar_one_or_none()
    if user and verify_password(password, user.password_hash):
        return user
    return None

def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
