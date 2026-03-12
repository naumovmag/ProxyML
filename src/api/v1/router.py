from fastapi import APIRouter
from src.api.v1 import health, services

router = APIRouter(prefix="/api/v1")
router.include_router(health.router, tags=["health"])
router.include_router(services.router, tags=["catalog"])
