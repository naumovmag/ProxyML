from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from src.services.auth_service import authenticate_admin, register_user, create_access_token
from src.api.deps import get_current_admin
from src.models.admin_user import AdminUser

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, session: AsyncSession = Depends(get_async_session)):
    user = await authenticate_admin(session, data.username, data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials or account not approved")
    token = create_access_token(str(user.id), is_superadmin=user.is_superadmin)
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.post("/register", response_model=UserRead, status_code=201)
async def register(data: RegisterRequest, session: AsyncSession = Depends(get_async_session)):
    # Check username uniqueness
    existing = await session.execute(
        select(AdminUser).where(AdminUser.username == data.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")
    user = await register_user(
        session,
        username=data.username,
        password=data.password,
        email=data.email,
        display_name=data.display_name,
    )
    return UserRead.model_validate(user)


@router.get("/me", response_model=UserRead)
async def me(admin: AdminUser = Depends(get_current_admin)):
    return UserRead.model_validate(admin)
