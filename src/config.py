from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://proxyml:proxyml@localhost:5432/proxyml"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24h
    admin_username: str = "admin"
    admin_password: str = "admin123"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
