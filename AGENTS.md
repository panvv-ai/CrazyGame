<!-- CODEGRAPH_START -->
## CodeGraph

This repository is indexed by CodeGraph. Before grep/find or reading code manually, use:

- MCP: `codegraph_explore`
- Shell: `codegraph explore "<symbols or question>"`

Read CodeGraph results as current, line-numbered source.
<!-- CODEGRAPH_END -->

# Repository Guidelines

## Product

PanWatch is a local, single-operator long-term market observatory.

Keep this product loop narrow:

```text
quotes -> watchlist -> weighted groups -> lightweight holdings -> alerts -> daily review
```

There is no user, login, registration, permission, paper-trading, strategy-research, or MCP subsystem. Do not add those back without an explicit product decision.

## Layout

- `backend/main.py` — executable entrypoint.
- `backend/src/panwatch/api/` — FastAPI app, dependencies, serializers, route modules.
- `backend/src/panwatch/core/` — configuration, database, cryptographic secrets, calendars, time utilities.
- `backend/src/panwatch/domain/` — ORM models, Pydantic schemas, and deterministic group/alert rules.
- `backend/src/panwatch/services/` — market data, alert scanning, notifications, AI review, scheduling.
- `backend/src/panwatch/providers/` — open-end fund data providers.
- `backend/tests/` — backend tests.
- `marketdata/` — standalone listed-market quote and daily-line package.
- `frontend/src/panwatch/` — React app, components, pages, i18n, visual system.
- `docs/` — architecture, design language, and English README.
- `config/env.example` — environment example; copy to root `.env` when needed.

## Commands

```bash
make setup
make dev-api
make dev-web
make test
make build
make compose-up
```

Direct verification:

```bash
cd backend && ../.venv/bin/python -m pytest tests -q
.venv/bin/python -m pytest marketdata/tests -q
cd frontend && pnpm check:i18n && pnpm test && pnpm build
docker compose config
```

## Engineering Rules

- Write a failing test before changing behavior.
- Keep modules inside the layers listed above; never reintroduce a root-level `src/` or `server.py`.
- Put every user-facing string in `frontend/src/panwatch/i18n.ts`.
- Keep `pnpm check:i18n` clean.
- Market values require `as_of`, `source`, and `freshness`.
- Never label estimated fund values as official NAV.
- Never return decrypted notification or AI credentials from an API.
- Bind local services to `127.0.0.1` unless the user explicitly requests otherwise.
- Keep runtime data under `DATA_DIR`; do not commit SQLite files or generated frontend output.

## Product Constraints

- Default UI language is Chinese.
- Dark theme only.
- A-share listed ETFs only; no Hong Kong or US ETFs.
- Open-end funds do not have continuous trading prices.
- The daily review runs at 15:20 Asia/Shanghai on A-share trading days, with one retry.
