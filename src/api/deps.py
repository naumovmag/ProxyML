import uuid
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.services.auth_service import decode_access_token
from src.services.api_key_service import validate_api_key
from src.models.admin_user import AdminUser

security = HTTPBearer()

async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_async_session),
) -> AdminUser:
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await session.execute(select(AdminUser).where(AdminUser.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    if not user.is_approved:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account pending approval")
    return user

async def get_current_superadmin(
    admin: AdminUser = Depends(get_current_admin),
) -> AdminUser:
    if not admin.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return admin

async def get_api_key_or_fail(
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
    authorization: str | None = Header(None),
    session: AsyncSession = Depends(get_async_session),
):
    raw_key = x_api_key
    if not raw_key and authorization:
        if authorization.lower().startswith("bearer "):
            raw_key = authorization[7:].strip()
        else:
            raw_key = authorization.strip()
    if not raw_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required (X-Api-Key or Authorization header)")
    api_key = await validate_api_key(session, raw_key)
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired API key")
    return api_key
