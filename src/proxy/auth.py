from abc import ABC, abstractmethod
import httpx
from src.models.service import Service

class BackendAuthStrategy(ABC):
    @abstractmethod
    def apply(self, request: httpx.Request, service: Service) -> httpx.Request:
        ...

class NoAuthStrategy(BackendAuthStrategy):
    def apply(self, request: httpx.Request, service: Service) -> httpx.Request:
        return request

class BearerTokenStrategy(BackendAuthStrategy):
    def apply(self, request: httpx.Request, service: Service) -> httpx.Request:
        request.headers["Authorization"] = f"Bearer {service.auth_token}"
        return request

class CustomHeaderStrategy(BackendAuthStrategy):
    def apply(self, request: httpx.Request, service: Service) -> httpx.Request:
        header_name = service.auth_header_name or "Authorization"
        request.headers[header_name] = service.auth_token or ""
        return request

class QueryParamStrategy(BackendAuthStrategy):
    def apply(self, request: httpx.Request, service: Service) -> httpx.Request:
        # Append token as query parameter
        url = request.url.copy_merge_params({"api_key": service.auth_token or ""})
        request.url = url
        return request

def get_auth_strategy(auth_type: str) -> BackendAuthStrategy:
    strategies = {
        "none": NoAuthStrategy(),
        "bearer": BearerTokenStrategy(),
        "header": CustomHeaderStrategy(),
        "query_param": QueryParamStrategy(),
    }
    return strategies.get(auth_type, NoAuthStrategy())
