# Contributing

PanWatchDIY is a private-use project and keeps a deliberately narrow scope.

## Before changing code

1. Read `AGENTS.md`.
2. Read `docs/v2-lean-implementation-plan.md`.
3. Check whether the requested feature belongs to quotes, watchlists, groups, holdings, alerts, daily review, i18n, or deployment.
4. Write a failing test for behavior changes.

## Required checks

```bash
make test
cd frontend && pnpm check:i18n && pnpm build
docker compose config
```

## Commit style

Use `<type>: <subject>`, where type is one of `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.

Do not commit secrets, SQLite files, generated `dist/`, `static/`, or `node_modules`.
