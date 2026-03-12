FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv pip install --system -e ".[dev]"

COPY alembic.ini .
COPY alembic/ alembic/
COPY src/ src/

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m src.main"]
