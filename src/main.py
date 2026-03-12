import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.utils.logging import setup_logging
from src.proxy.client import close_http_client
from src.api.v1.router import router as v1_router
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
        from src.utils.crypto import hash_password
        from sqlalchemy import select

        async with async_session_factory() as session:
            result = await session.execute(select(AdminUser).where(AdminUser.username == settings.admin_username))
            if not result.scalar_one_or_none():
                admin = AdminUser(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                )
                session.add(admin)
                await session.commit()
                logger.info(f"Admin user '{settings.admin_username}' seeded.")
    except Exception as e:
        logger.warning(f"Could not seed admin user: {e}")
    yield
    await close_http_client()
    logger.info("ProxyML stopped.")

app = FastAPI(title="ProxyML", version="0.1.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)

# Routers
app.include_router(v1_router)
app.include_router(admin_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
