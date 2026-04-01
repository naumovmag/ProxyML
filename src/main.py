import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.utils.logging import setup_logging
from src.proxy.client import close_http_client
from src.cache.redis_client import close_redis
from src.api.v1.router import router as v1_router
from src.api.v1.proxy import router as proxy_router
from src.api.v1.auth_public import router as auth_public_router
from src.api.admin.router import router as admin_router
from src.middleware.logging import LoggingMiddleware

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ProxyML...")
    # Seed admin
    try:
        from src.db.engine import async_session_factory
        from src.models.admin_user import AdminUser
        from src.models.service import Service
        from src.models.service_group import ServiceGroup
        from src.models.api_key import ApiKey
        from src.models.request_log import RequestLog
        from src.models.auth_system import AuthSystem
        from src.models.auth_user import AuthUser
        from src.models.auth_refresh_token import AuthRefreshToken
        from src.models.email_verification_token import EmailVerificationToken
        from src.utils.crypto import hash_password
        from sqlalchemy import select, update

        async with async_session_factory() as session:
            result = await session.execute(select(AdminUser).where(AdminUser.username == settings.admin_username))
            admin = result.scalar_one_or_none()
            if not admin:
                admin = AdminUser(
                    username=settings.admin_username,
                    password_hash=await hash_password(settings.admin_password),
                    is_superadmin=True,
                    is_approved=True,
                )
                session.add(admin)
                await session.commit()
                await session.refresh(admin)
                logger.info(f"Admin user '{settings.admin_username}' seeded.")
            else:
                changed = False
                from src.utils.crypto import verify_password
                if not await verify_password(settings.admin_password, admin.password_hash):
                    admin.password_hash = await hash_password(settings.admin_password)
                    changed = True
                    logger.info(f"Admin user '{settings.admin_username}' password updated from settings.")
                if not admin.is_superadmin:
                    admin.is_superadmin = True
                    changed = True
                if not admin.is_approved:
                    admin.is_approved = True
                    changed = True
                if changed:
                    await session.commit()

            # Backfill owner_id for existing records that have no owner
            admin_id = admin.id
            for model in [Service, ServiceGroup, ApiKey, RequestLog]:
                await session.execute(
                    update(model).where(model.owner_id.is_(None)).values(owner_id=admin_id)
                )
            await session.commit()
    except Exception as e:
        logger.warning(f"Could not seed admin user: {e}")

    from src.services.load_test_scheduler import scheduler as load_test_scheduler
    await load_test_scheduler.start()

    yield

    await load_test_scheduler.stop()
    await close_http_client()
    await close_redis()
    logger.info("ProxyML stopped.")

app = FastAPI(title="ProxyML", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)

# Routers
app.include_router(v1_router)
app.include_router(proxy_router, prefix="/proxy", tags=["proxy"])
app.include_router(auth_public_router, prefix="/api/auth", tags=["auth-public"])
app.include_router(admin_router)

# Serve frontend static files if built
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")

    @app.get("/{path:path}")
    async def serve_spa(request: Request, path: str):
        file_path = STATIC_DIR / path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
