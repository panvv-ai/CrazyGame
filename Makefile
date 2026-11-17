.PHONY: help setup dev-api dev-web test build android-debug android-release compose-up compose-start compose-down

TAG ?= latest
JAVA_HOME ?= $(shell if [ -x /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java ]; then echo /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home; fi)
ANDROID_HOME ?= $(shell if [ -d /opt/homebrew/share/android-commandlinetools ]; then echo /opt/homebrew/share/android-commandlinetools; fi)

help:
	@echo "CrazyGame"
	@echo "  make setup       Install Python and frontend dependencies"
	@echo "  make dev-api     Run FastAPI on :8000"
	@echo "  make dev-web     Run Vite on :5183"
	@echo "  make test        Run backend and frontend tests"
	@echo "  make build       Build the production frontend"
	@echo "  make android-debug   Build the debug Android APK"
	@echo "  make android-release Build the signed release APK"
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

test:
	cd backend && ../.venv/bin/python -m pytest tests -q
	cd frontend && pnpm test

build:
	cd frontend && pnpm build

android-debug:
	cd android && JAVA_HOME="$(JAVA_HOME)" ANDROID_HOME="$(ANDROID_HOME)" ANDROID_SDK_ROOT="$(ANDROID_HOME)" ./gradlew :app:assembleDebug

android-release:
	cd android && JAVA_HOME="$(JAVA_HOME)" ANDROID_HOME="$(ANDROID_HOME)" ANDROID_SDK_ROOT="$(ANDROID_HOME)" ./gradlew :app:assembleRelease

compose-up:
	CRAZYGAME_TAG=$(TAG) docker compose up -d --build

compose-start:
	CRAZYGAME_TAG=$(TAG) docker compose up -d --no-build --force-recreate

compose-down:
	docker compose down
