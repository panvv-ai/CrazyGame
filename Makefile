.PHONY: help setup dev-api dev-web test build compose-up compose-down

help:
	@echo "PanWatchDIY v2"
	@echo "  make setup       Install Python and frontend dependencies"
	@echo "  make dev-api     Run FastAPI on :8000"
	@echo "  make dev-web     Run Vite on :5183"
	@echo "  make test        Run backend and frontend tests"
	@echo "  make build       Build frontend and Docker image"
	@echo "  make compose-up  Build and start with Docker Compose"

setup:
	uv venv .venv --python 3.11
	uv pip install --python .venv/bin/python -r requirements.txt
	cd frontend && pnpm install --frozen-lockfile

dev-api:
	@if [ ! -x .venv/bin/python ]; then $(MAKE) setup; fi
	PANWATCH_RELOAD=1 .venv/bin/python server.py

dev-web:
	cd frontend && pnpm dev

test:
	.venv/bin/python -m pytest tests/v2 -q
	.venv/bin/python -m pytest packages/marketdata/tests -q
	cd frontend && pnpm test

build:
	cd frontend && pnpm build
	docker compose build

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down
