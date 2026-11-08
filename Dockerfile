FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend
RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build


FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    TZ=Asia/Shanghai \
    CRAZYGAME_HOST=0.0.0.0 \
    DOCKER=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/
COPY marketdata/pyproject.toml ./marketdata/
COPY marketdata/src/ ./marketdata/src/
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/src/ ./backend/src/
COPY backend/main.py ./backend/
RUN mkdir -p /app/data

COPY --from=frontend-builder /app/frontend/dist ./backend/static/

WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=6s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

CMD ["python", "main.py"]
