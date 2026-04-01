from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 5432
    db_database: str = "proxyml"
    db_username: str = "proxyml"
    db_password: str = "proxyml"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24h
    admin_username: str = "admin"
    admin_password: str = "adata_admin_zxcv1234"
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    cache_ttl_seconds: int = 86400  # 24h
    server_base_url: str | None = None  # e.g. https://proxy-ml.example.com
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_database}"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
