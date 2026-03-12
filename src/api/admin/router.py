from fastapi import APIRouter
from src.api.admin import auth, services, api_keys, check

router = APIRouter(prefix="/api/admin")
router.include_router(auth.router, tags=["admin-auth"])
router.include_router(services.router, tags=["admin-services"])
router.include_router(api_keys.router, tags=["admin-api-keys"])
router.include_router(check.router, tags=["admin-check"])
