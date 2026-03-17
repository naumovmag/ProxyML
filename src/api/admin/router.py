from fastapi import APIRouter
from src.api.admin import auth, services, service_groups, api_keys, check, stats, users

router = APIRouter(prefix="/api/admin")
router.include_router(auth.router, tags=["admin-auth"])
router.include_router(service_groups.router, tags=["admin-service-groups"])
router.include_router(services.router, tags=["admin-services"])
router.include_router(api_keys.router, tags=["admin-api-keys"])
router.include_router(check.router, tags=["admin-check"])
router.include_router(stats.router, tags=["admin-stats"])
router.include_router(users.router, tags=["admin-users"])
