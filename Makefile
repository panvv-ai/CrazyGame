.PHONY: help setup dev-api dev-web build compose-up compose-start compose-down

TAG ?= latest

help:
	@echo "CrazyGame"
	@echo "  make setup       Install Python and frontend dependencies"
	@echo "  make dev-api     Run FastAPI on :8000"
	@echo "  make dev-web     Run Vite on :5183"
	@echo "  make build       Build crazygame:$(TAG)"
	@echo "  make compose-up  Build and start with Docker Compose ($(TAG))"
	@echo "  make compose-start Start an existing crazygame:$(TAG) without rebuilding"

setup:
	uv venv .venv --python 3.11
	uv pip install --python .venv/bin/python -r backend/requirements.txt
	cd frontend && pnpm install --frozen-lockfile

dev-api:
	@if [ ! -x .venv/bin/python ]; then $(MAKE) setup; fi
	cd backend && CRAZYGAME_RELOAD=1 ../.venv/bin/python main.py

dev-web:
	cd frontend && pnpm dev

build:
	./scripts/build.sh $(TAG)

compose-up:
	CRAZYGAME_TAG=$(TAG) docker compose up -d --build

compose-start:
	CRAZYGAME_TAG=$(TAG) docker compose up -d --no-build --force-recreate

compose-down:
	docker compose down
