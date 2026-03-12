from fastapi import APIRouter
from src.schemas.health import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()
