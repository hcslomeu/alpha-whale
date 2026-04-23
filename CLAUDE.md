# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repo.

## Project

alpha-whale — AI-powered finance agent. Conversational trading assistant with LangGraph agent + LlamaIndex RAG over SEC filings and financial news.

See [README.md](README.md) for stack + quickstart, [docs/architecture.md](docs/architecture.md) for layer breakdown, [docs/deploy.md](docs/deploy.md) for deploy runbook.

## Conventions

- **Python 3.12**, managed with `uv` (lockfile `uv.lock`).
- **Frontend** in `web/`, managed with `pnpm`.
- **Flat repo**: no `libs/` or `apps/` — modules live at root (`agent/`, `api/`, `core/`, `ingestion/`, `tests/`, `web/`).
- **Packaging**: single `pyproject.toml`, hatchling wheel builds `agent api core ingestion`.
- **Tests** under `tests/` (Python) and `api/tests/` (API integration). No `__init__.py` in test dirs.
- **Type checking**: `uv run mypy agent api core ingestion` — strict mode, 42 source files clean.
- **Linting**: `uv run ruff check .` + `uv run ruff format --check .`.
- **All 358 tests pass**; `uv run pytest`.

## Quality gates (run before committing)

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy agent api core ingestion
uv run pytest --tb=short
```

CI runs identical commands on push/PR — keep them green.

## Git

- Conventional commits: `feat(scope): ...`, `fix(scope): ...`, `chore(scope): ...`.
- No `Co-Authored-By:` lines — developer is sole author.
- Provide commit commands as text for the user to run; do not execute unless explicitly asked.

## Deployment

- **Frontend** → Vercel (auto on push to `main`).
- **Backend** → AWS Lightsail, Docker Compose behind Caddy. Deploys via `.github/workflows/deploy.yml` (SSH + `git pull` + `docker compose up -d --build`).
- See `docs/deploy.md` for provisioning runbook (one-time manual setup).

## Secrets + env

- Never hardcode API keys. Use Pydantic `SecretStr` + `.env`.
- `.env.example` documents required vars; real `.env` is gitignored.
- Frontend env vars live in Vercel project settings.

## Engineering principles

DRY · KISS · YAGNI · SoC. Don't refactor beyond the task. Don't add features hypothetical future requirements might need.

## Notes for future sessions

- Specs from the simplification migration live in `.claude/specs/` (kept for reference).
- Archive: https://github.com/hcslomeu/ai-engineering-monorepo @ tag `pre-simplification-snapshot` holds the pre-migration monorepo state.
