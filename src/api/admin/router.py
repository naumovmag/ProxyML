from fastapi import APIRouter

from src.api.admin import (
    ai,
    api_keys,
    auth,
    auth_roles,
    auth_systems,
    check,
    load_tests,
    maintenance,
    model_routes,
    playground,
    service_groups,
    services,
    settings,
    stats,
    users,
    verification_channels,
)

router = APIRouter(prefix="/api/admin")
router.include_router(auth.router, tags=["admin-auth"])
router.include_router(service_groups.router, tags=["admin-service-groups"])
router.include_router(services.router, tags=["admin-services"])
router.include_router(api_keys.router, tags=["admin-api-keys"])
router.include_router(check.router, tags=["admin-check"])
router.include_router(stats.router, tags=["admin-stats"])
router.include_router(users.router, tags=["admin-users"])
router.include_router(settings.router, tags=["admin-settings"])
router.include_router(ai.router, tags=["admin-ai"])
router.include_router(playground.router, tags=["admin-playground"])
router.include_router(load_tests.router, tags=["admin-load-tests"])
router.include_router(auth_systems.router, tags=["admin-auth-systems"])
router.include_router(verification_channels.router, tags=["admin-verification-channels"])
router.include_router(model_routes.router, tags=["admin-model-routes"])
router.include_router(auth_roles.router, tags=["admin-auth-roles"])
router.include_router(maintenance.router, tags=["admin-maintenance"])
