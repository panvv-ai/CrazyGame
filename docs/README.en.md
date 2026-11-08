# CrazyGame

**A local-first observatory for long-term multi-market investing.**

<p align="center">
  <img alt="Python 3.11" src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white">
  <img alt="Node.js 22+" src="https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white">
  <img alt="MIT License" src="https://img.shields.io/badge/License-MIT-yellow.svg">
</p>

<p align="center">
  <a href="../README.md">简体中文</a> | <a href="README.en.md">English</a>
</p>

CrazyGame brings stocks, ETFs, and open-end funds into one local workspace for watchlists, weighted groups, lightweight holdings, alerts, and a daily AI portfolio review.

There is no account, login, registration, or permission system. SQLite stores application state, while AI and notification credentials are encrypted at rest.

> [!IMPORTANT]
> Quotes come from public website endpoints, not licensed exchange feeds. They may be delayed, rate-limited, or changed. Intraday open-end fund values are estimates; official NAV governs returns. This project is for personal research and is not investment advice.

## Features

<p align="center">
  <img src="images/dashboard.png" alt="CrazyGame dashboard with weighted groups, watchlist quotes, and daily portfolio review" width="100%">
</p>

- Separate stock tabs for A-shares, Hong Kong, and US markets.
- Separate fund tabs for mainland-listed ETFs and open-end funds.
- Open-end fund estimates, current NAV, and NAV history.
- Category-scoped groups with automatic normalization and coverage reporting.
- Monthly, quarterly, yearly, multi-year, and full-history line charts.
- One lightweight portfolio with native-currency totals.
- Price and daily-change alerts with cooldown and market-hours gating.
- Feishu bot and Alibaba Cloud SMS delivery with retry tracking.
- Daily portfolio review after the A-share close.
- Chinese and English interfaces, with reports and alerts following the UI language.
- Local and Docker Compose deployment.

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.11, FastAPI, Pydantic, SQLAlchemy |
| Scheduling | APScheduler |
| Storage | SQLite |
| Market data | Tencent, Sina, Eastmoney, Stooq |
| Frontend | React 18, TypeScript, Vite, i18next |
| Charts | lightweight-charts |
| Tests | pytest, Vitest |

## Quick start

Requirements: Docker Desktop for the recommended setup, or Python 3.11, Node.js 22+, and pnpm 10+ for local development.

### Docker Compose (recommended)

```bash
git clone https://github.com/panvv-ai/CrazyGame.git
cd CrazyGame
cp config/env.example .env
docker compose up -d --build
docker compose ps
```

Open <http://127.0.0.1:8000>. View logs with `docker compose logs -f crazygame` and stop with `docker compose down`.

The default image is `crazygame:latest`. Override the tag with `CRAZYGAME_TAG=v1 docker compose up -d --build`.

### Local development

```bash
make setup
make dev-api
```

In another terminal:

```bash
make dev-web
```

Open <http://127.0.0.1:5183>.

### Build the image manually

```bash
cp config/env.example .env
docker build --build-arg CRAZYGAME_TAG=v1 -t crazygame:v1 .
docker run -d \
  --name crazygame \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -v crazygame_data:/app/data \
  --env-file .env \
  crazygame:v1
```

Open <http://127.0.0.1:8000>.

The service binds to loopback by default. `.env` is ignored by Git; keep real API keys out of `config/env.example`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATA_DIR` | `project/data` | SQLite and local key storage |
| `TZ` | `Asia/Shanghai` | Application and scheduler timezone |
| `CRAZYGAME_TAG` | `latest` | Compose image tag |
| `CRAZYGAME_HOST` | `127.0.0.1` | Local bind address |
| `CRAZYGAME_PORT` | `8000` | Local port |
| `APP_SECRET_KEY` | generated locally | Encrypt AI and notification credentials |
| `AI_BASE_URL` | OpenAI-compatible URL | AI endpoint |
| `AI_API_KEY` | empty | AI key; can also be set in the UI |
| `AI_MODEL` | `gpt-4.1-mini` | Model identifier |

## Project layout

```text
backend/       FastAPI app, domain, services, providers, tests
frontend/      React UI, i18n, visual system
marketdata/    reusable quote and daily-line package
config/        environment example
docs/          architecture, design language, English README
scripts/       build helper
```

See [architecture.md](architecture.md) and [design-language.md](design-language.md).

## Data and privacy

- Database: `DATA_DIR/crazygame.sqlite3`.
- Local encryption key: `DATA_DIR/.app-secret` with `0600` permissions.
- Credentials are encrypted and masked in API responses.
- Do not expose the unauthenticated service directly to the public internet.

## Development

```bash
make test

cd frontend
pnpm check:i18n
pnpm test
pnpm build
```

## Limitations

- Mainland-listed ETFs only.
- Open-end funds do not have continuous trading prices.
- Public quote endpoints have no SLA.
- Dark theme only.
- AI output never executes trades.

## License

MIT. See [LICENSE](../LICENSE).

