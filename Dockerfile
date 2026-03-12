# ---- Stage 1: Build frontend ----
FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY admin-ui/package.json admin-ui/package-lock.json ./
RUN npm ci
COPY admin-ui/ .
RUN npm run build

# ---- Stage 2: Backend + static ----
FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv pip install --system -e .

COPY alembic.ini .
COPY alembic/ alembic/
COPY src/ src/

# Copy built frontend
COPY --from=frontend-build /app/dist /app/static

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m src.main"]
