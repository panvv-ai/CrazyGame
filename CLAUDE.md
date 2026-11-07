# Claude Guidance

Follow `AGENTS.md`.

This repository is intentionally lean. Extend `src/panwatch/` and `frontend/src/panwatch/`; do not restore retired modules from Git history unless the user explicitly asks for a feature.

Before claiming completion, run:

```bash
.venv/bin/python -m pytest tests/v2 -q
cd frontend && pnpm check:i18n && pnpm test && pnpm build
docker compose config
```
