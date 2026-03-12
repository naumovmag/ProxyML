.PHONY: up down migrate seed dev install lint test

up:
	docker-compose up -d

down:
	docker-compose down

migrate:
	alembic upgrade head

seed:
	python -m src.seed

dev:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

install:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/

test:
	pytest tests/ -v
