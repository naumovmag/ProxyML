from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.services.auth_service import decode_access_token
from src.services.api_key_service import validate_api_key

security = HTTPBearer()

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload

async def get_api_key_or_fail(
    x_api_key: str = Header(..., alias="X-Api-Key"),
    session: AsyncSession = Depends(get_async_session),
):
    api_key = await validate_api_key(session, x_api_key)
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired API key")
    return api_key
