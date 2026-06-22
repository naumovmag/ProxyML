from pydantic_settings import BaseSettings


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
    request_logs_retention_days: int = 2
    request_logs_partition_ahead_days: int = 3
    # Доля успешных (status < 400) запросов, сохраняемых в request_logs.
    # Ошибки и fallback-запросы логируются всегда. 1.0 = писать всё.
    # 0.05 = писать ~5% успешных: при ~12M запросов/сутки это режет рост
    # таблицы в ~20 раз и удерживает её далеко под лимитом диска.
    request_logs_sample_rate: float = 0.05
    # Жёсткий потолок числа строк в request_logs. Maintenance дропает самые
    # старые партиции, пока оценка суммарного числа строк превышает лимит.
    # Гранулярность — целая партиция (день), поэтому фактический потолок
    # соблюдается до ±одной партиции (нельзя дропнуть активную партицию).
    request_logs_max_rows: int = 10_000_000
    load_test_results_retention_days: int = 3
    httpx_max_connections: int = 1000
    httpx_max_keepalive_connections: int = 200
    server_base_url: str | None = None  # e.g. https://proxy-ml.example.com
    graylog_host: str | None = None
    graylog_port: int = 12201
    graylog_app_env: str = "production"
    graylog_source: str = "proxyml"
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_database}"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
