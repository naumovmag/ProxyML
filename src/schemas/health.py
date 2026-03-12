from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"

class ServiceHealthCheck(BaseModel):
    service_id: str
    service_name: str
    status: str  # "ok" | "error"
    detail: str | None = None
    response_time_ms: float | None = None
