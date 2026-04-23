# Alpha-Whale Simplification — Design Spec

**Date:** 2026-04-22
**Status:** Design approved, pending implementation plan
**Authored by:** Humberto Lomeu with Claude Code brainstorming

---

## Goal

Transform the current `ai-engineering-monorepo` (Nx + uv workspace + pnpm + 3 planned projects) into a single, portfolio-clear repo named `alpha-whale` that showcases production-shaped AI engineering skills to hiring managers.

The frameworks (LangGraph, LlamaIndex, BigQuery, Pinecone, Instructor, FastAPI, Next.js) remain — they are the demonstrable skills. The orchestration machinery around them (Nx, workspaces, monorepo tooling) is removed.

## Why

Current repo reads as a "staff engineer learned Nx + workspaces" project rather than "AI engineer ships production agents." Three planned projects (AlphaWhale, MediGuard, RailSense) = one mature + two specs-only, which tells a weaker story than one deep project. Hiring managers scan a repo in 30 seconds — the structure must speak before the code does.

## Non-goals

Out of scope, explicitly:

- Keeping `libs/py-core`, `libs/schemas`, Nx, pnpm workspace, uv workspace, MkDocs site
- Keeping MediGuard + RailSense specs in the new repo (archive preserves them)
- `git filter-repo` history preservation (Mode X = clean slate)
- Airflow, Databricks, CrewAI, Kafka (were in CLAUDE.md, dropped entirely)
- WhatsApp integration (future WP, not part of simplification)
- Auth, multi-tenancy, multi-user state
- Frontend testing beyond `next build` in CI
- Coverage threshold enforcement
- Live-API tests in CI
- Bandit security scanner in CI
- Making `alpha-whale`, `tfl-monitor`, and personal site into one monorepo (separate repos, shared Lightsail host)

---

## Decisions Locked

1. **Single project focus.** Drop MediGuard + RailSense. New repo = alpha-whale only.
2. **Repo strategy: new repo + archive.** Create fresh `alpha-whale` repo. Rename current to `ai-engineering-monorepo-archive` and set read-only. Link from archive README to new repo.
3. **Frontend: Next.js 15 + React 19 + Tailwind v4 + Radix + Framer Motion** (already shipped in `apps/alpha-whale/web/`). Deploy to Vercel.
4. **Backend: Python-only, FastAPI + LangGraph + LlamaIndex.** WhatsApp deferred as future WP.
5. **`libs/py-core` collapses into `core/`** inside the new repo. One consumer = no abstraction.
6. **Deployment: Vercel (frontend) + AWS Lightsail (backend).** $5/mo Lightsail instance shared with future `tfl-monitor` and personal website via Caddy reverse proxy + subdomain routing.
7. **Migration mode X: clean slate.** Copy files (not `git filter-repo`), single "initial import" commit, fresh history.
8. **CI: one `ci.yml`** with Python (ruff + mypy + pytest) and Web (lint + build) jobs. Separate `deploy.yml` for SSH push to Lightsail on main branch.
9. **No scheduler, no queue, no cache layer in v1.** Ingestion = CLI scripts. Agent = in-process call from FastAPI.

---

## Section 1 — New repo structure

**Name:** `alpha-whale` (`github.com/hcslomeu/alpha-whale`, public).

**Top-level tree:**

```
alpha-whale/
├── README.md                  # Portfolio-grade, value prop up front
├── pyproject.toml             # Single uv project, no workspace
├── uv.lock
├── .env.example
├── .gitignore
├── Dockerfile                 # Single backend image
├── docker-compose.yml         # Local dev + server deploy
├── Caddyfile.example          # Reference only; live copy on server
├── .github/workflows/
│   ├── ci.yml
│   └── deploy.yml
│
├── api/                       # FastAPI app
│   ├── __init__.py
│   ├── main.py
│   ├── routes.py
│   ├── dependencies.py
│   └── models.py
│
├── agent/                     # LangGraph agent
│   ├── __init__.py
│   ├── graph.py
│   ├── tools.py
│   ├── state.py
│   ├── models.py
│   └── chain.py
│
├── ingestion/                 # Data pipelines (CLI scripts)
│   ├── __init__.py
│   ├── __main__.py
│   ├── bronze.py              # Alpha Vantage → BigQuery Bronze
│   ├── pipeline.py            # Bronze → Silver → Gold
│   ├── massive.py
│   ├── stochastic.py
│   ├── supabase_client.py
│   └── rag/
│       ├── chunking.py
│       └── indexing.py
│
├── core/                      # Merged py-core (settings, logging, exceptions, otel)
│   ├── __init__.py
│   ├── config.py
│   ├── logging.py
│   ├── exceptions.py
│   └── observability.py
│
├── migrations/                # DB migrations (kept from current alpha-whale)
│
├── tests/                     # Flat tests dir (no __init__.py, avoid monorepo collision)
│   ├── conftest.py
│   ├── test_api_routes.py
│   ├── test_agent_graph.py
│   ├── test_agent_tools.py
│   ├── test_ingestion_bronze.py
│   ├── test_rag_chunking.py
│   ├── test_rag_indexing.py
│   ├── test_core_config.py
│   ├── test_core_observability.py
│   └── fixtures/
│
├── web/                       # Next.js 15 frontend (moved from apps/alpha-whale/web)
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   └── eslint.config.mjs
│
├── docs/
│   ├── architecture.md        # Diagram + module responsibilities
│   ├── deploy.md              # Lightsail bootstrap runbook
│   └── screenshots/
│
└── .claude/                   # Retained Claude Code config (trimmed)
    ├── hooks/ruff-format-on-save.sh
    └── skills/ (keep: review-pr, generate-linkedin-post, claude-code-practices)
```

**Deletions from current repo:**

- `nx.json`, root `package.json` (Nx/pnpm workspace)
- `libs/py-core/`, `libs/schemas/`, all of `libs/`
- `apps/` wrapper (contents hoisted)
- `infra/docker/` multi-stage (replaced by single Dockerfile)
- `mkdocs.yml` + MkDocs docs site
- `PROGRESS.md`, `.claude/learning-progress.md`, `.claude/learning-context.md`
- `apps/alpha-whale/poetry.lock`, `apps/alpha-whale/project.json`
- `pnpm-lock.yaml`, `pnpm-workspace.yaml`
- `uploaded-files/` (scratch)
- MediGuard + RailSense spec files

---

## Section 2 — Migration strategy

**Migration mode: X — Clean slate copy.**

**Sequence:**

1. Push or abandon all in-flight branches on current repo.
2. Rename GitHub repo `ai-engineering-monorepo` → `ai-engineering-monorepo-archive`.
3. Update archive README with a one-paragraph "Why this is archived" + link to new `alpha-whale`.
4. Archive the GitHub repo (Settings → Archive). Read-only from that point.
5. `gh repo create hcslomeu/alpha-whale --public --description "..."`.
6. Fresh local clone of new repo, empty main.
7. Copy files from archive clone per migration table below.
8. Merge `libs/py-core` source into `core/`.
9. Rewrite imports: `from py_core.` → `from core.`; drop any `apps.alpha_whale.` prefixes.
10. Consolidate `pyproject.toml`: merge deps from `apps/alpha-whale/pyproject.toml` + `libs/py-core/pyproject.toml` into single root `pyproject.toml`. Drop `poetry.lock`; generate `uv.lock`.
11. Flatten tests: merge `libs/py-core/tests/` into root `tests/` with renamed files (`test_observability.py` → `test_core_observability.py` etc.).
12. Drop all Nx-related files (`project.json`, `nx.json`).
13. Run `uv sync` + `uv run pytest` + `uv run mypy .` + `uv run ruff check .` until green.
14. `cd web && npm install && npm run build` until green.
15. First commit: `chore: initial import from ai-engineering-monorepo`.
16. Push to GitHub, set up Vercel project pointing at `web/`.
17. Provision Lightsail, configure DNS, run server bootstrap (Section 4).
18. Second commit if needed: `chore: deployment wiring`.
19. Iterate.

**Migration table (what to copy where):**

| From (archive) | To (alpha-whale) | Notes |
|---|---|---|
| `apps/alpha-whale/api/` | `api/` | Direct copy, update imports |
| `apps/alpha-whale/agent/` | `agent/` | Direct copy, update imports |
| `apps/alpha-whale/ingestion/` | `ingestion/` | Direct copy, update imports |
| `apps/alpha-whale/web/` | `web/` | Direct copy (sans node_modules) |
| `apps/alpha-whale/tests/` | `tests/` | Flatten, drop `__init__.py` files |
| `apps/alpha-whale/migrations/` | `migrations/` | Direct copy |
| `apps/alpha-whale/pyproject.toml` | `pyproject.toml` | Merge with py-core deps |
| `libs/py-core/src/py_core/config.py` | `core/config.py` | Update imports |
| `libs/py-core/src/py_core/logging.py` | `core/logging.py` | Update imports |
| `libs/py-core/src/py_core/exceptions.py` | `core/exceptions.py` | Update imports |
| `libs/py-core/src/py_core/observability.py` | `core/observability.py` | Update imports |
| `libs/py-core/tests/*` | `tests/test_core_*.py` | Flatten + rename |
| `.claude/hooks/ruff-format-on-save.sh` | `.claude/hooks/ruff-format-on-save.sh` | Keep |
| `.claude/skills/` (selected) | `.claude/skills/` | Keep: review-pr, generate-linkedin-post, claude-code-practices. Drop: scaffold-py-lib (no libs), wp-research (no more WP workflow) |

**Not copied:**

- `libs/schemas/`
- `nx.json`, root `package.json`, `pnpm-*.yaml`
- `infra/docker/` multi-stage (replaced with single Dockerfile at root)
- `mkdocs.yml`, site docs folder
- `PROGRESS.md`, learning files
- `apps/alpha-whale/poetry.lock`, `project.json`
- `uploaded-files/`
- MediGuard / RailSense specs + issues

**Import rewrites (one-time sed pass):**

```bash
grep -rl "from py_core" --include="*.py" . | xargs sed -i '' 's/from py_core/from core/g'
grep -rl "import py_core" --include="*.py" . | xargs sed -i '' 's/import py_core/import core/g'
```

---

## Section 3 — CI/CD

**Current:** 4 parallel Nx-orchestrated jobs (ruff, pytest, bandit, mypy) + MkDocs deploy.

**New:** Two workflows total.

### `.github/workflows/ci.yml`

```yaml
name: CI
on: [push, pull_request]

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy .
      - run: uv run pytest

  web:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: web
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: web/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run build
```

### `.github/workflows/deploy.yml`

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: SSH deploy to Lightsail
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.LIGHTSAIL_HOST }}
          username: ubuntu
          key: ${{ secrets.LIGHTSAIL_SSH_KEY }}
          script: |
            cd ~/alpha-whale
            git pull
            docker compose pull
            docker compose up -d --build
            docker image prune -f
```

**Vercel frontend deploy:** auto via Vercel GitHub integration. Project root = `web/`. No workflow needed.

**Dropped vs current:**

- Nx orchestration layer
- `bandit` CI step
- Parallel matrix strategy
- MkDocs deploy workflow

**Local dev commands (documented in README):**

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy .
uv run uvicorn api.main:app --reload

cd web && npm install
npm run dev
```

---

## Section 4 — Deployment wiring

### Topology

```
Vercel (free tier)
 ├─ alphawhale.<domain>   (Next.js app, web/)
 ├─ tflmonitor.<domain>   (future, separate repo)
 └─ <domain> root         (personal site, future, separate repo)
         │
         │  HTTPS JSON API calls
         ▼
AWS Lightsail ($5/mo, 1GB RAM, 2 vCPU burst, Ubuntu 24.04)
 Caddy (auto-SSL) + Docker Compose
 ├─ api.alphawhale.<domain>  → FastAPI :8000
 └─ api.tflmonitor.<domain>  → future :8001
         │
         │  outbound
         ▼
Managed services (free/hobby)
 ├─ BigQuery   (market data, Bronze/Silver/Gold)
 ├─ Pinecone   (vector store)
 ├─ Supabase   (Postgres, LangGraph checkpointer)
 └─ LangSmith  (agent traces)
```

### Lightsail instance

- Plan: $5/mo — 1GB RAM, 2 vCPU burst, 40GB SSD, 2TB transfer.
- Region: `eu-west-2` (London) for latency to tfl-monitor eventually.
- Blueprint: Ubuntu 24.04 LTS.
- Static IP attached (free while attached).
- Firewall: 22 (SSH, personal IP only), 80, 443 (all).

### One-time server bootstrap (goes in `docs/deploy.md`)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu

sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy

git clone https://github.com/hcslomeu/alpha-whale.git ~/alpha-whale
cd ~/alpha-whale
cp .env.example .env
# populate .env with BIGQUERY/PINECONE/SUPABASE/OPENAI/LANGSMITH keys

docker compose up -d
sudo nano /etc/caddy/Caddyfile  # install Caddyfile from repo
sudo systemctl reload caddy
```

### `Dockerfile` (backend, multi-stage)

```dockerfile
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY api/ ./api/
COPY agent/ ./agent/
COPY ingestion/ ./ingestion/
COPY core/ ./core/
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `docker-compose.yml`

```yaml
services:
  api:
    build: .
    restart: unless-stopped
    env_file: .env
    ports:
      - "127.0.0.1:8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
```

### Caddy config (on server, `/etc/caddy/Caddyfile`)

```
api.alphawhale.<domain> {
    reverse_proxy 127.0.0.1:8000
    encode gzip
    log {
        output file /var/log/caddy/alphawhale.log
    }
}
```

### DNS (registrar, domain TBD)

- `A  api.alphawhale     → <Lightsail static IP>`
- `CNAME  alphawhale     → cname.vercel-dns.com`
- Future: `A  api.tflmonitor → <Lightsail static IP>`, `CNAME  tflmonitor → cname.vercel-dns.com`

**Domain: TBD.** User hasn't picked one. Options: register at Cloudflare or Namecheap (~$10/yr) OR skip domain and use `alphawhale.vercel.app` + raw Lightsail IP with self-signed or Let's Encrypt on IP (not possible — LE requires domain). Recommend registering one domain and carving subdomains.

### Secrets

- GitHub Actions: `LIGHTSAIL_HOST`, `LIGHTSAIL_SSH_KEY` (and `VERCEL_TOKEN` if programmatic deploys ever needed).
- Server: `~/alpha-whale/.env`, `chmod 600`, not committed.
- Vercel: dashboard env vars (`NEXT_PUBLIC_API_URL=https://api.alphawhale.<domain>`).
- BigQuery: service account JSON on server, path in `.env` as `GOOGLE_APPLICATION_CREDENTIALS`.

### Cost

| Item | Monthly |
|---|---|
| Lightsail 1GB | $5 |
| Vercel hobby | $0 |
| Supabase free | $0 |
| BigQuery (1TB/mo free) | $0 |
| Pinecone starter | $0 |
| LangSmith hobby | $0 |
| Domain | $1 (~$12/yr amortized) |
| **Total** | **~$6/mo** |

---

## Section 5 — Architecture & data flow

### Runtime components

```
web/ (Next.js, Vercel)
 │ POST /agent/invoke
 ▼
api/ (FastAPI, Lightsail)
 ├─ routes: /agent/invoke, /agent/resume, /health
 ├─ deps: Settings (core/), structlog, OTel middleware
 ▼
agent/ (LangGraph StateGraph)
 ├─ llm_node       → ChatOpenAI.bind_tools(...)
 ├─ tools_node     → execute tool calls
 └─ risk_gate      → HITL interrupt on risky actions
Tools:
 ├─ get_price        Alpha Vantage
 ├─ rag_search       Pinecone query via LlamaIndex
 ├─ bigquery_query   BQ Silver/Gold
 └─ extract_signal   Instructor structured extraction

Pinecone ◄── ingestion/rag/indexing.py
BigQuery ◄── ingestion/bronze.py, pipeline.py
Supabase Postgres ◄── LangGraph checkpointer (HITL resume state)
```

### Module responsibilities

| Module | Purpose | Imports allowed |
|---|---|---|
| `api/` | HTTP surface, validation, session | `agent/`, `core/` |
| `agent/` | Reasoning, tool orchestration, HITL gating | `core/` only |
| `ingestion/` | Data-layer jobs, no HTTP | `core/` only |
| `core/` | Settings, logging, observability, exceptions | nothing internal |
| `web/` | User-facing chat + dashboard | external APIs via fetch |

No circular imports. Enforce via ruff + optional `import-linter` if drift appears.

### Request flow (chat)

1. User types in `web/`.
2. `POST /agent/invoke {"message": "...", "thread_id": "..."}`.
3. `api/routes.py` loads checkpointed state, calls `agent.graph.invoke(...)`.
4. `llm_node` decides to call tools → `tools_node` executes → `llm_node` produces final answer.
5. If `risk_gate` triggers → 202 with pending state, `/agent/resume` continues.
6. Streamed response tokens back to web UI.

### Ingestion flow (ad-hoc)

```bash
python -m ingestion.bronze --ticker AAPL --days 30      # Alpha Vantage → BQ Bronze
python -m ingestion.pipeline                            # Bronze → Silver → Gold
python -m ingestion.rag.indexing --source news          # fetch, chunk, embed, upsert Pinecone
```

No scheduler in v1. Cron on Lightsail if/when needed.

### Locked architectural decisions

- No message queue.
- No Redis/cache.
- No separate worker process.
- No auth in v1 (CORS whitelist for Vercel preview + prod domains).
- LangGraph checkpointer: in-memory locally; Postgres (Supabase) in prod.

---

## Section 6 — Testing & quality

### Test layout

```
tests/
├── conftest.py
├── test_api_routes.py
├── test_agent_graph.py
├── test_agent_tools.py
├── test_ingestion_bronze.py
├── test_rag_chunking.py
├── test_rag_indexing.py
├── test_core_config.py
├── test_core_observability.py
└── fixtures/
    ├── alpha_vantage_aapl.json
    └── sample_chunks.json
```

**Rules:**

- Flat `tests/`, no `__init__.py` (avoid monorepo pytest collision bug from MEMORY).
- One test file per module, `test_<module>.py`.
- Shared fixtures only in `conftest.py`.
- All external APIs mocked at boundary (OpenAI, Alpha Vantage, BigQuery, Pinecone).
- Live-API tests → `@pytest.mark.live`, excluded from default run, run locally pre-release.

### Frontend tests

v1 scope: `next build` in CI = enough. Playwright smoke test for chat happy path can be added later.

### Quality tools

| Tool | Config |
|---|---|
| ruff (lint + format) | `pyproject.toml` — line 100, `select = ["E","F","I","N","UP","B","SIM","RUF"]` |
| mypy | strict on `api/`, `agent/`, `core/`; lenient on `tests/`, `ingestion/` scripts |
| pytest | `--strict-markers`, `-m 'not live'` default |
| ESLint + eslint-config-next | `web/eslint.config.mjs` (as today) |
| TypeScript strict | `web/tsconfig.json` |

**Dropped:** bandit, import-linter (add later only if drift).

**Coverage target:** no CI threshold. Aim critical paths (graph routing, tool I/O, route handlers, ingestion happy path).

### `pyproject.toml` sketch (final in implementation plan)

```toml
[project]
name = "alpha-whale"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.10",
    "pydantic-settings>=2.6",
    "structlog>=24.4",
    "langchain>=0.3",
    "langchain-openai>=0.2",
    "langgraph>=1.0",
    "langsmith>=0.2",
    "instructor>=1.7",
    "llama-index>=0.12",
    "llama-index-vector-stores-pinecone>=0.4",
    "pinecone>=5.4",
    "google-cloud-bigquery>=3.27",
    "requests>=2.32",
    "opentelemetry-api>=1.29",
    "opentelemetry-sdk>=1.29",
    "opentelemetry-instrumentation-fastapi>=0.50b0",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.25",
    "pytest-mock>=3.14",
    "httpx>=0.28",
    "mypy>=1.13",
    "ruff>=0.8",
    "types-requests>=2.32",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.12"
strict = true
exclude = ["tests/", "migrations/"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
markers = ["live: requires live external APIs"]
addopts = "-v --strict-markers -m 'not live'"
```

### Claude Code hooks

Keep existing `ruff-format-on-save.sh` PostToolUse hook in `.claude/hooks/`.

---

## Section 7 — Success criteria

### Automated

- [ ] New repo `alpha-whale` exists on GitHub, public.
- [ ] Old repo renamed to `ai-engineering-monorepo-archive`, marked read-only.
- [ ] `git clone` + `uv sync` + `uv run pytest` passes on clean machine.
- [ ] `cd web && npm install && npm run build` succeeds.
- [ ] `docker build .` produces a working backend image.
- [ ] `docker compose up` locally serves `http://localhost:8000/health` → 200.
- [ ] `uv run ruff check .` → 0 errors.
- [ ] `uv run mypy .` → 0 errors on `api/`, `agent/`, `core/`.
- [ ] CI `ci.yml` passes (both jobs) on first push.
- [ ] Vercel deploys `web/` successfully.
- [ ] Lightsail deploy via `deploy.yml` reaches `api.<domain>/health` → 200 with valid HTTPS.
- [ ] Chat UI at Vercel URL round-trips to Lightsail backend.
- [ ] No lingering `py_core` imports anywhere.
- [ ] `find . -name "project.json" -o -name "nx.json" -o -name "pnpm-workspace.yaml"` → empty.

### Manual

- [ ] README opens with clear value prop, 60-second "what is this" for hiring managers.
- [ ] `docs/architecture.md` diagram matches actual code layout.
- [ ] Demo screenshot or GIF in README shows chat UI working.
- [ ] Repo top-level tree is self-explanatory without scrolling.
- [ ] Commit history in new repo reads cleanly (no Nx/monorepo leakage).
- [ ] Archive README points clearly to new `alpha-whale` repo.
- [ ] At least one peer does a 30-second scan and can explain back what the project does.
- [ ] Fresh-clone → browser chat round-trip in < 15 min of setup.

### Portfolio narrative

- [ ] README showcases LangGraph + LlamaIndex + BigQuery + Pinecone + Instructor + OTel + FastAPI + Next.js 15.
- [ ] No Nx, monorepo, or deleted-project remnants visible.
- [ ] Frontend live at public Vercel URL; backend live at Lightsail subdomain, HTTPS, both linked from README.
- [ ] 30-second scan answers: what it does, what stack, how to run it.

---

## Open items (resolve during implementation)

1. **Domain name.** Pick and register before deploy. Alternative: defer deploy and ship GitHub-only portfolio first.
2. **`.claude/` skills selection.** Confirm which skills carry over vs stay in archive.
3. **README content.** Draft in implementation plan phase.
4. **Existing `ingestion/massive.py` + `ingestion/supabase_client.py`.** Confirm they're in scope or removed — they were shipped but possibly cruft.
5. **`testing_utils.py`** at `apps/alpha-whale/`. Untracked per git status. Decide: keep, move to `tests/`, or delete.

---

## Next step

After user review of this spec → invoke `superpowers:writing-plans` to produce phased implementation plan with checkpoints.
