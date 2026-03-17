from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.models.admin_user import AdminUser
from src.services.ai_service import (
    ai_parse_curl, ai_analyze_error, ai_diagnose_health,
    ai_summarize_dashboard, ai_generate_description,
    AINotConfiguredError, AICallError,
)

router = APIRouter()


def _handle_ai_error(e: Exception):
    if isinstance(e, AINotConfiguredError):
        raise HTTPException(status_code=422, detail=str(e))
    if isinstance(e, AICallError):
        raise HTTPException(status_code=502, detail=str(e))
    raise HTTPException(status_code=500, detail=f"AI error: {str(e)}")


class ParseCurlRequest(BaseModel):
    curl_command: str


class AnalyzeErrorRequest(BaseModel):
    service_slug: str
    method: str
    path: str
    status_code: int
    duration_ms: float
    error: str | None = None
    is_streaming: bool = False
    is_fallback: bool = False


class DiagnoseHealthRequest(BaseModel):
    name: str
    service_type: str
    base_url: str
    health_check_path: str | None = None
    health_check_method: str = "GET"
    status: str
    detail: str | None = None
    response_time_ms: float | None = None


class SummarizeDashboardRequest(BaseModel):
    period_hours: int
    total_requests: int
    total_errors: int
    error_rate: float
    avg_duration_ms: float
    total_request_bytes: int
    total_response_bytes: int
    by_service: list[dict] = []
    by_key: list[dict] = []


class GenerateDescriptionRequest(BaseModel):
    name: str
    service_type: str
    base_url: str
    default_model: str | None = None
    supports_streaming: bool = False


class AITextResponse(BaseModel):
    text: str


@router.post("/ai/parse-curl")
async def parse_curl(
    data: ParseCurlRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        result = await ai_parse_curl(session, data.curl_command)
        return result
    except (AINotConfiguredError, AICallError) as e:
        _handle_ai_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse cURL: {str(e)}")


@router.post("/ai/analyze-error", response_model=AITextResponse)
async def analyze_error(
    data: AnalyzeErrorRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        text = await ai_analyze_error(session, data.model_dump())
        return AITextResponse(text=text)
    except (AINotConfiguredError, AICallError) as e:
        _handle_ai_error(e)


@router.post("/ai/diagnose-health", response_model=AITextResponse)
async def diagnose_health(
    data: DiagnoseHealthRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        service_info = {
            "name": data.name,
            "service_type": data.service_type,
            "base_url": data.base_url,
            "health_check_path": data.health_check_path,
            "health_check_method": data.health_check_method,
        }
        health_result = {
            "status": data.status,
            "detail": data.detail,
            "response_time_ms": data.response_time_ms,
        }
        text = await ai_diagnose_health(session, service_info, health_result)
        return AITextResponse(text=text)
    except (AINotConfiguredError, AICallError) as e:
        _handle_ai_error(e)


@router.post("/ai/summarize-dashboard", response_model=AITextResponse)
async def summarize_dashboard(
    data: SummarizeDashboardRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        text = await ai_summarize_dashboard(session, data.model_dump())
        return AITextResponse(text=text)
    except (AINotConfiguredError, AICallError) as e:
        _handle_ai_error(e)


@router.post("/ai/generate-description", response_model=AITextResponse)
async def generate_description(
    data: GenerateDescriptionRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        text = await ai_generate_description(session, data.model_dump())
        return AITextResponse(text=text)
    except (AINotConfiguredError, AICallError) as e:
        _handle_ai_error(e)
