from abc import ABC, abstractmethod
from typing import Any
from fastapi import Request
from fastapi.responses import StreamingResponse, Response
from src.models.service import Service

class AbstractProxyHandler(ABC):
    @abstractmethod
    async def handle(self, request: Request, service: Service, path: str) -> Response:
        ...

class HandlerRegistry:
    def __init__(self):
        self._handlers: dict[str, AbstractProxyHandler] = {}
        self._default: AbstractProxyHandler | None = None

    def register(self, service_type: str, handler: AbstractProxyHandler):
        self._handlers[service_type] = handler

    def set_default(self, handler: AbstractProxyHandler):
        self._default = handler

    def get(self, service_type: str) -> AbstractProxyHandler:
        return self._handlers.get(service_type, self._default)

registry = HandlerRegistry()
