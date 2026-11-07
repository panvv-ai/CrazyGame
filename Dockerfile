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
    DOCKER=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY packages/marketdata/pyproject.toml ./packages/marketdata/
COPY packages/marketdata/src/ ./packages/marketdata/src/
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY server.py ./
COPY VERSION ./
RUN mkdir -p /app/data

COPY --from=frontend-builder /app/frontend/dist ./static/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=6s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

CMD ["python", "server.py"]
