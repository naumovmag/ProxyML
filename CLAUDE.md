# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is ProxyML

ProxyML — прокси-сервис для ML-моделей и любых HTTP-сервисов. Принимает запросы, авторизует по API-ключу (`X-Api-Key`), прозрачно проксирует к бэкенду. Поддерживает SSE-стриминг, кеширование в Redis, fallback на резервный сервис, multi-tenancy (owner_id), аналитику запросов. Админ-панель (React SPA) встроена в один Docker-образ с бэкендом.

## Commands

```bash
# Backend
make install          # pip install -e ".[dev]"
make dev              # uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
make migrate          # alembic upgrade head
make lint             # ruff check src/ tests/
make test             # pytest tests/ -v
pytest tests/test_api/test_auth.py -v              # один файл
pytest tests/test_api/test_auth.py::test_login -v  # один тест

# Миграции
alembic revision --autogenerate -m "описание"
alembic upgrade head

# Frontend (admin-ui/)
cd admin-ui && npm install && npm run dev   # http://localhost:5173
cd admin-ui && npm run build                # production build → admin-ui/dist/

# Docker
make up       # docker-compose up -d (db + redis + app)
make down     # docker-compose down
docker-compose up -d db redis   # только БД и Redis для локальной разработки
```

## Architecture

### Request flow (proxy)

```
Client → POST /proxy/{slug}/{path}
  → get_api_key_or_fail (X-Api-Key или Authorization header)
  → validate access (allowed_services, multi-tenancy через owner_id + ServiceShare)
  → HandlerRegistry.get(service_type) → GenericProxyHandler.handle()
    → cache check (Redis, если cache_enabled)
    → forward request via httpx async client (HTTP/2)
    → if stream=true in body → StreamingResponse (SSE)
    → else → regular Response + cache write
    → fire-and-forget log to RequestLog (asyncio.create_task)
  → on failure → fallback to service.fallback_service_id (if configured)
```

### Two auth layers

1. **Admin API** (`/api/admin/*`): JWT tokens. `get_current_admin` / `get_current_superadmin` в `src/api/deps.py`. Login через `/api/admin/login`.
2. **Proxy API** (`/proxy/*`): API-ключи (`X-Api-Key` header, prefix `pml_`). Ключи хранятся как SHA-256 hash. Валидация в `src/services/api_key_service.py`.

Backend auth (к целевому сервису) — strategy pattern: `src/proxy/auth.py` (none/bearer/header/query_param), применяется в `GenericProxyHandler` по `service.auth_type`.

### Key patterns

- **Pure ASGI middleware** (`src/middleware/logging.py`): НЕ использовать `BaseHTTPMiddleware` — он буферизует ответы и ломает SSE streaming.
- **bcrypt через `asyncio.to_thread`**: `src/utils/crypto.py` — `hash_password` и `verify_password` обёрнуты, т.к. bcrypt блокирующий. Используется прямой `bcrypt` (не passlib).
- **Fire-and-forget logging**: `log_request_fire_and_forget` создаёт `asyncio.create_task` для записи в БД, не блокируя ответ клиенту.
- **Handler registry**: `src/proxy/base.py` — `HandlerRegistry` позволяет регистрировать обработчики по `service_type`. По умолчанию — `GenericProxyHandler`.
- **Multi-tenancy**: все основные модели имеют `owner_id` (FK → `admin_users.id`). При старте приложения backfill заполняет `owner_id=NULL` записи ID админа.
- **All timestamps**: `TIMESTAMP(timezone=True)` — always timezone-aware.

### Project layout

- `src/api/v1/` — публичный API (каталог сервисов, health, proxy endpoint)
- `src/api/admin/` — админ API (CRUD сервисов, ключей, групп, статистика, auth systems, load tests, playground)
- `src/proxy/` — ядро проксирования (handler, streaming, auth strategies, httpx client)
- `src/services/` — бизнес-логика (CRUD, auth, health checker, email, load test scheduler)
- `src/models/` — SQLAlchemy ORM модели
- `src/schemas/` — Pydantic-схемы
- `src/cache/` — Redis клиент и кеширование ответов
- `src/middleware/` — ASGI middleware (logging)
- `admin-ui/` — React 19 + TypeScript + Vite + Tailwind + shadcn/ui + Zustand
- `alembic/` — миграции БД

### Frontend

SPA на React 19 с Zustand для state management. В production собирается Vite → `admin-ui/dist/`, затем копируется в `/app/static` внутри Docker-образа. FastAPI раздаёт статику и fallback на `index.html` для SPA-роутинга.

### Database

PostgreSQL 16, async через asyncpg + SQLAlchemy async. Все PK — UUID. Session factory: `src/db/engine.py`. Dependency: `src/db/session.py` → `get_async_session`.

### Testing

pytest + pytest-asyncio (`asyncio_mode = "auto"`). Тесты используют ту же БД (не отдельную!). `conftest.py` трекает ID созданных в тестах записей (`_test_service_ids`, `_test_key_ids`) и удаляет ТОЛЬКО их в teardown. **Никогда не делать `DELETE FROM` / `TRUNCATE` без условия по конкретным ID.**

### Docker

Multi-stage: Node.js 20 → frontend build, Python 3.12 → backend. `CMD` запускает `alembic upgrade head && python -m src.main`. Один образ, один порт (8000).

## Статус SDLC-цикла
- [ ] PLAN готов → docs/PLAN.md
- [ ] Реализация завершена
- [ ] Review завершён → docs/REVIEW.md
- [ ] Правки применены
