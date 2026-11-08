# Architecture

## Product boundary

CrazyGame is a local, single-operator market observation tool. It intentionally supports one workflow:

```text
public market data
  -> instruments and watchlists
  -> category-scoped weighted groups
  -> lightweight holdings
  -> price and daily-change alerts
  -> Feishu / Aliyun SMS delivery
  -> daily AI portfolio review
```

There is no account system, login page, registration flow, multi-user permission model, paper trading, strategy engine, or AI research workspace.

## Backend layout

```text
backend/
├── main.py
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── src/crazygame/
│   ├── api/
│   │   ├── app.py
│   │   ├── dependencies.py
│   │   ├── serializers.py
│   │   └── routes/
│   ├── core/
│   │   ├── calendar.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── secrets.py
│   │   └── timeutils.py
│   ├── domain/
│   │   ├── alerts.py
│   │   ├── groups.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── providers/
│   │   ├── fund_collector.py
│   │   └── fund_quotes.py
│   └── services/
│       ├── ai.py
│       ├── alert_service.py
│       ├── catalog.py
│       ├── daily_review.py
│       ├── market.py
│       ├── marketdata.py
│       ├── notifications.py
│       ├── scheduler.py
│       └── senders.py
└── tests/
```

## Data model

- `Instrument` is the normalized identity for stocks, listed ETFs, and open-end funds.
- `WatchlistItem` keeps stock and fund watchlists separate; the UI further separates A-share, Hong Kong, US, listed-fund, and open-end-fund views.
- `AssetGroup` and `GroupMember` store relative target weights; calculations normalize them and reject members from different scopes.
- `Holding` stores the single lightweight portfolio.
- `AlertRule`, `AlertHit`, and `NotificationDelivery` implement alert evaluation and durable delivery.
- `DailyReview` stores the once-per-day AI portfolio review.
- `AppSetting` stores language, AI, and report settings.

SQLite lives at `DATA_DIR/crazygame.sqlite3`.

## Market data

`marketdata/` is a separate package responsible for listed instruments:

```text
Tencent -> Eastmoney -> Sina/Stooq
```

The fallback engine handles quotes and daily lines. Open-end fund estimates and NAV history remain in backend providers because they use fund-specific public endpoints.

All public market values carry an `as_of` time and freshness marker:

- `live`
- `delayed`
- `stale`
- `estimated`
- `official_nav`

These endpoints are not licensed exchange feeds. The UI must never remove or hide this distinction.

## Group calculation

- Groups are scoped to exactly one of: A-share stock, Hong Kong stock, US stock, listed ETF, or open-end fund.
- Creating or updating a group with mixed scopes returns HTTP 422.
- User weights are relative and must be non-negative.
- Weights are normalized at read time.
- A group’s daily return is the normalized weighted sum of available member changes.
- Missing member data reduces coverage and re-normalizes over available members.
- Historical curves start at 100 and apply target-weight returns per aligned date.

## Background work

One APScheduler instance runs:

- Alert scan and delivery drain every 30 seconds.
- Portfolio review at 15:20 Asia/Shanghai on A-share trading days.
- One review retry at 15:28.

Successful review results are immutable for that trade date. A retry never re-calls the AI.

## Frontend layout

```text
frontend/src/crazygame/
├── App.tsx
├── api.ts
├── i18n.ts
├── scopes.ts
├── components/
├── pages/
├── lib.ts
├── styles.css
└── types.ts
```

The frontend is a five-page application:

- Overview
- Watchlist
- Groups
- Holdings
- Alerts

Settings is available from the header. The interface is dark-only and supports `zh-CN` and `en-US`.

## Runtime

- Local Python development: `127.0.0.1:8000`.
- Local frontend development: `127.0.0.1:5183`, proxying `/api` to the backend.
- Docker Compose publishes only to `127.0.0.1:8000`.
- Runtime data is stored in `data/` locally or the `crazygame_data` Docker volume.

