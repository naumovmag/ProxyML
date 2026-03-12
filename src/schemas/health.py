from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"

class ServiceHealthCheck(BaseModel):
    service_id: str
    service_name: str
    status: str  # "ok" | "error" | "unknown"
    detail: str | None = None
    response_time_ms: float | None = None

class HealthReportItem(BaseModel):
    service_id: str
    service_name: str
    slug: str
    is_active: bool
    status: str  # "ok" | "error" | "unknown"
    detail: str | None = None
    response_time_ms: float | None = None

class HealthReportResponse(BaseModel):
    items: list[HealthReportItem]
    total: int
    healthy: int
    unhealthy: int
    unconfigured: int
