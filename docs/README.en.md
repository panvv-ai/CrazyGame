# CrazyGame

**A local-first portfolio observatory with AI decision support.**

<p align="center">
  <img alt="Python 3.11" src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white">
  <img alt="Node.js 22+" src="https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white">
  <img alt="MIT License" src="https://img.shields.io/badge/License-MIT-yellow.svg">
</p>

<p align="center">
  <a href="../README.md">简体中文</a> | <a href="README.en.md">English</a>
</p>

CrazyGame helps you follow only the stocks and funds you truly believe in, understand your real allocation and risk, and use AI to organize possible next steps. Data, alerts, and configuration stay local.

The interface uses an "Aurora Workbench" visual system: the ambient light field responds to scrolling, functional pages use compact control rails, and primary actions stay available in the first viewport. AI diagnosis runs in a single-screen workbench with its composer always in view.

There is no account, login, registration, or permission system. SQLite stores application state, while AI and notification credentials are encrypted at rest.

> [!IMPORTANT]
> Quotes come from public website endpoints, not licensed exchange feeds. They may be delayed, rate-limited, or changed. Intraday open-end fund values are estimates; official NAV governs returns. This project is for personal research and is not investment advice.

## Features

<p align="center">
  <img src="images/dashboard.png" alt="CrazyGame dashboard with weighted groups, watchlist quotes, and daily portfolio review" width="100%">
  <br>
  <sub>Aurora Workbench overview: real holdings, weighted curve, watchlist quotes, and daily review</sub>
</p>

<p align="center">
  <img src="images/ai-workspace.png" alt="CrazyGame AI workbench with session navigation and an always-visible composer" width="100%">
  <br>
  <sub>AI workbench: sessions, instrument context, and the illuminated composer share one screen</sub>
</p>

- Separate stock tabs for A-shares, Hong Kong, and US markets.
- Separate fund tabs for mainland-listed ETFs and open-end funds.
- A holdings-first overview with market-value-weighted performance and an optional group view.
- Open-end fund estimates, current NAV, and NAV history.
- Category-scoped groups with automatic normalization and coverage reporting.
- Monthly, quarterly, yearly, multi-year, and full-history line charts.
- One lightweight portfolio with native-currency totals.
- Price and daily-change alerts with daily, 30-minute, hourly, or 6-hour frequency, optional immediate checking, and market-hours gating.
- Test notification credentials before saving them, without persisting the draft.
- Feishu bot and Alibaba Cloud SMS delivery with retry tracking.
- Daily portfolio review after the A-share close, rendered as Markdown.
- On-demand AI diagnosis with trend, score, support/resistance, risks, catalysts, and position-specific observations.
- Multi-turn ask-stock with streamed answers, tool progress, session recovery, and one server-bound active instrument.
- Screenshot recognition for stocks and mainland-listed ETFs with explicit user confirmation.
- Ranked hotspots from free Eastmoney news and announcements, with optional Tavily or Bocha enhancement.
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

## Quick start

Requirements: Docker Desktop for the recommended setup, or Python 3.11, Node.js 22+, and pnpm 10+ for local development.

### One-command script (recommended)

```bash
git clone https://github.com/panvv-ai/CrazyGame.git
cd CrazyGame
./docker-start.sh v2
```

The script pulls missing base images with retries, builds `crazygame:v2`, recreates the container, and waits for the health check.

Open <http://127.0.0.1:8000>.

Other modes:

```bash
./docker-start.sh v3               # build and deploy a new tag
./docker-start.sh --no-build v2    # deploy an existing image
./docker-start.sh --no-cache v2    # build without cache
./docker-start.sh --dry-run v2     # print commands only
```

If Docker Hub metadata requests fail with `EOF` or timeouts, configure Docker Desktop Proxies or use reachable base-image mirrors:

```bash
CRAZYGAME_NODE_IMAGE=docker.m.daocloud.io/library/node:22-alpine \
CRAZYGAME_PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim \
  ./docker-start.sh v2
```

Traditional Compose remains available:

```bash
docker compose up -d --build
# Existing image:
CRAZYGAME_TAG=v2 docker compose up -d --no-build --force-recreate
```

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
docker build --build-arg CRAZYGAME_TAG=v2 -t crazygame:v2 .
CRAZYGAME_TAG=v2 docker compose up -d --no-build --force-recreate
```

To run without Compose:

```bash
docker run -d \
  --name crazygame \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -v crazygame_data:/app/data \
  crazygame:v2
```

Open <http://127.0.0.1:8000>.

The service binds to loopback by default.

## Usage

In the Watchlist page, choose Stocks or Funds, then select A-shares, Hong Kong, US stocks, mainland-listed ETFs, or open-end funds. Search by symbol or name to add an instrument. Drag a card by its handle to reorder the current category.

Holdings record actual quantities, average costs, and unrealized P/L. They are the only source used by the daily health review. Groups do not record real positions; they combine watched instruments with target weights so you can review a hypothetical basket and its long-term curve. If you only need to analyze real assets, you can ignore groups.

For alert setup, choose the instrument, metric, direction, threshold, and alert frequency. Feishu and Alibaba Cloud SMS credentials can be tested before saving; testing a draft does not persist it. The optional "check and execute once immediately after saving" setting is off by default and still respects frequency, market-hours, and cooldown constraints.

Open the AI workspace from the top bar to ask follow-up questions or generate a structured report. Instrument quote details also provide direct diagnosis and chat actions. AI diagnosis supports A-share, Hong Kong, and US stocks plus mainland-listed ETFs. Open-end funds remain on their existing NAV and daily-review paths.

### Configure DeepSeek or another OpenAI-compatible model

Open Settings and fill in:

- **Base URL**: use `https://api.deepseek.com` for DeepSeek. The full `https://api.deepseek.com/chat/completions` URL is also accepted and normalized automatically.
- **API key**: use a key generated in the provider console. It is masked in the UI and encrypted in SQLite.
- **Model ID**: `deepseek-flash` is the current DeepSeek recommendation and supports text, images, and tool calls. Use `deepseek-v4-pro` for the text-only Pro model.
- **Vision model**: leave it empty to inherit the main model. For DeepSeek Flash image recognition, use `deepseek-flash`.

The JSON, tools, streaming, and vision capability test uses the values currently entered in the form, even before saving. An authentication, rate-limit, network, or model configuration failure is reported explicitly. Save the configuration after the test succeeds.

An HTTP `401` means the provider rejected the API key. Regenerate the key in the provider console. Older versions could repeatedly encrypt a masked saved key; the current version automatically unwraps those legacy values and rewrites them as one encrypted layer, so clearing the database is not required.

## Configuration

CrazyGame does not ship an environment configuration file. It generates the encryption key under `DATA_DIR`, and all model, news, and notification settings are configured in the UI and stored encrypted in SQLite.

`docker-start.sh` receives the image tag as an argument. If Docker Hub access is restricted, pass `CRAZYGAME_NODE_IMAGE` and `CRAZYGAME_PYTHON_IMAGE` for the current command only; no config file is required.

Rebuilding or recreating the container does not remove configuration. The SQLite database and `.app-secret` remain in the `crazygame_data` volume, including across image tag changes and `--no-cache` builds.

## Project layout

```text
backend/       FastAPI app, domain, services, providers
frontend/      React UI, i18n, visual system
marketdata/    reusable quote and daily-line package
docs/          architecture, design language, English README
docker-start.sh one-command build and deployment
```

See [architecture.md](architecture.md) and [design-language.md](design-language.md).

## Data and privacy

- Database: `DATA_DIR/crazygame.sqlite3`.
- Local encryption key: `DATA_DIR/.app-secret` with `0600` permissions.
- Credentials are encrypted and masked in API responses.
- AI diagnosis sends the active instrument's quote, technical evidence, related news, and current holding cost to the configured AI service.
- Public news requests go to Eastmoney unless news is disabled.
- Screenshot bytes are sent to the configured vision model and are not persisted.
- Do not expose the unauthenticated service directly to the public internet.

## Development and build

```bash
make setup
cd frontend
pnpm check:i18n
pnpm build
```

## Limitations

- Mainland-listed ETFs only.
- Open-end funds do not have continuous trading prices.
- Public quote endpoints have no SLA.
- Public news endpoints have no SLA; unavailable hotspots are disclosed rather than invented.
- AI reports and ask-stock turns run on demand, not for the entire watchlist.
- The first version excludes open-end fund AI diagnosis and cross-stock comparison.
- Dark theme only.
- AI output never executes trades.

## License

MIT. See [LICENSE](../LICENSE).

