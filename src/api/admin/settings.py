from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin, get_current_superadmin
from src.models.admin_user import AdminUser
from src.models.system_settings import SystemSettings
from src.schemas.settings import SystemSettingsRead, SystemSettingsUpdate

router = APIRouter()


@router.get("/settings", response_model=SystemSettingsRead)
async def get_settings(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(SystemSettings).where(SystemSettings.id == 1))
    settings = result.scalar_one_or_none()
    if not settings:
        return SystemSettingsRead(ai_enabled=False, llm_service_slug=None, llm_model=None)
    return SystemSettingsRead.model_validate(settings)


@router.put("/settings", response_model=SystemSettingsRead)
async def update_settings(
    data: SystemSettingsUpdate,
    admin: AdminUser = Depends(get_current_superadmin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(SystemSettings).where(SystemSettings.id == 1))
    settings = result.scalar_one_or_none()
    if not settings:
        settings = SystemSettings(id=1)
        session.add(settings)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)

    await session.commit()
    await session.refresh(settings)
    return SystemSettingsRead.model_validate(settings)
