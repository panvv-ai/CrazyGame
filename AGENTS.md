<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call.
- **Shell** (always works): `codegraph explore "<symbol names or question>"`.

If there is no `.codegraph/` directory, skip CodeGraph entirely.
<!-- CODEGRAPH_END -->

# Repository Guidelines

## Scope

PanWatchDIY v2 is a private long-term investing monitor. Preserve the narrow product loop:

```text
quotes -> watchlist -> weighted groups -> lightweight holdings -> alerts -> daily review
```

Do not reintroduce the retired multi-Agent, paper trading, strategy research, MCP, Skill, news, or K-line UI without an explicit product decision.

## Structure

- `src/panwatch/` — v2 FastAPI app, SQLAlchemy models, market adapter, alerts, notifications, scheduler, and daily review.
- `src/collectors/fund_collector.py` — off-exchange fund NAV and holdings.
- `src/collectors/fund_quotes.py` — off-exchange fund intraday estimates.
- `packages/marketdata/` — reusable listed-market data engine with provider fallback.
- `frontend/src/panwatch/` — React app, i18n resources, pages, and design components.
- `tests/v2/` — backend tests.
- `docs/v2-lean-implementation-plan.md` — product and implementation decisions.
- `docs/design-language.md` — visual system and interaction rules.

## Commands

```bash
make setup
make dev-api
make dev-web
make test
make build
make compose-up
```

Direct checks:

```bash
.venv/bin/python -m pytest tests/v2 -q
cd frontend && pnpm check:i18n
cd frontend && pnpm test
cd frontend && pnpm build
docker compose config
```

## Conventions

- Python: Python 3.11+, PEP 8, type hints, `snake_case`.
- TypeScript: React function components in PascalCase, utilities in camelCase.
- New behavior requires a failing test first.
- UI copy must go through `frontend/src/panwatch/i18n.ts`; `pnpm check:i18n` rejects CJK literals outside that file.
- Market values must carry `as_of`, `source`, and `freshness`; never label estimated fund values as official net asset value.
- Credentials are encrypted at rest and must never be returned in clear text.
- Keep market data access behind the provider adapter so licensed sources can be added later.

## Product Boundaries

- Single user and single lightweight portfolio.
- A-share ETFs only; no Hong Kong or US ETF support in v2.
- Off-exchange funds are not continuously traded; estimates and official NAV must be visually distinct.
- The default interface language is `zh-CN`.
- Dark theme only in v2.
- Keep the archived full-feature version at tag `archive/full-feature-2026-11`.
