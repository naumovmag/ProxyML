from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.schemas.auth import LoginRequest, TokenResponse
from src.services.auth_service import authenticate_admin, create_access_token

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, session: AsyncSession = Depends(get_async_session)):
    user = await authenticate_admin(session, data.username, data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)
