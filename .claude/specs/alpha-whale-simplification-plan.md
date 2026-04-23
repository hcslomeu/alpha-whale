# Alpha-Whale Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `ai-engineering-monorepo` contents into a new `alpha-whale` repo with a flat, portfolio-ready structure — no Nx, no workspaces, single uv project, single Next.js app, all tests green.

**Architecture:** Copy-and-flatten migration. Hoist `apps/alpha-whale/*` → new-repo root. Merge `libs/py-core/src/py_core/*` → `core/`. Drop `libs/schemas/`, `infra/docker/`, `mkdocs.yml`, Nx/pnpm configs. Produce a single `pyproject.toml`, single `Dockerfile`, single `docker-compose.yml`, two GitHub Actions workflows. Plan A stops at "green CI, local docker-compose works." Plan B (deploy + archive) is a separate runbook.

**Tech Stack:** Python 3.12 + uv, FastAPI, LangGraph ≥ 1.0, LlamaIndex, Instructor, Pinecone, BigQuery, Next.js 15, React 19, Tailwind v4, Radix UI, Framer Motion, Docker, Caddy (config only in this plan), GitHub Actions.

**Spec reference:** `.claude/specs/alpha-whale-simplification-design.md`

**Convention for this plan:**
- Work happens in **two checkouts**: `~/ai-engineering-monorepo` (current, becomes archive) and `~/alpha-whale` (new). Each task marks which checkout it runs in.
- All commits happen in `~/alpha-whale` unless explicitly noted.
- After every code change, run tests before committing.
- Commit messages use Conventional Commits, no Co-Authored-By lines (per CLAUDE.md).

---

## Phase 0 — Pre-migration hygiene (current repo)

### Task 0.1: Commit design + plan docs to current repo

**Files (current repo):**
- `.claude/specs/alpha-whale-simplification-design.md` (exists)
- `.claude/specs/alpha-whale-simplification-plan.md` (exists)

- [ ] **Step 1: Verify both files exist**

Run (in `~/ai-engineering-monorepo`): `ls -la .claude/specs/alpha-whale-simplification-*.md`
Expected: both files listed.

- [ ] **Step 2: Commit design + plan**

```bash
git add .claude/specs/alpha-whale-simplification-design.md .claude/specs/alpha-whale-simplification-plan.md
git commit -m "docs(spec): alpha-whale simplification design and plan"
```

### Task 0.2: Decide fate of uncommitted WIP

Current `git status` shows modified + untracked files (e.g., `apps/alpha-whale/testing_utils.py`, `apps/alpha-whale/agent/graph.py` changes, etc.).

- [ ] **Step 1: List uncommitted changes**

Run: `git status --short`
Expected: list of M/??/UU files.

- [ ] **Step 2: Decide per-file (user decision)**

For each file, pick one:
- Commit to current repo's main branch (preserves in archive history).
- Stash (`git stash save "WIP pre-migration"`) if planning to port changes later.
- Discard via `git checkout -- <file>` if unwanted.

Document decisions in commit message.

- [ ] **Step 3: Commit kept WIP**

```bash
git add <files-to-keep>
git commit -m "chore(alpha-whale): preserve WIP before migration"
```

- [ ] **Step 4: Verify clean working tree**

Run: `git status`
Expected: "nothing to commit, working tree clean" OR explicit stashes noted.

### Task 0.3: Capture snapshot tag in archive

- [ ] **Step 1: Tag current HEAD for archival reference**

```bash
git tag -a pre-simplification-snapshot -m "Snapshot before simplification to alpha-whale repo"
git push --tags
```

- [ ] **Step 2: Verify tag pushed**

Run: `git ls-remote --tags origin | grep pre-simplification-snapshot`
Expected: tag ref present on remote.

---

## Phase 1 — Create empty `alpha-whale` repo

### Task 1.1: Create GitHub repo

**Files:** none yet.

- [ ] **Step 1: Create public repo via gh CLI**

```bash
gh repo create hcslomeu/alpha-whale \
  --public \
  --description "AI-powered finance agent: LangGraph + LlamaIndex + BigQuery + Pinecone + Next.js" \
  --disable-wiki
```

Expected: "Created repository hcslomeu/alpha-whale on GitHub".

- [ ] **Step 2: Clone locally, outside monorepo dir**

```bash
cd ~
gh repo clone hcslomeu/alpha-whale
cd ~/alpha-whale
```

- [ ] **Step 3: Configure git user (inherits global, verify)**

Run: `git config user.name && git config user.email`
Expected: "Humberto Lomeu" and `hcslomeu@gmail.com`.

### Task 1.2: Add root `.gitignore`

**Files (new repo):**
- Create: `.gitignore`

- [ ] **Step 1: Write .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.venv/
.env
.env.local
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
*.egg-info/
dist/
build/

# Node
node_modules/
.next/
out/
*.tsbuildinfo

# OS / editor
.DS_Store
.vscode/
.idea/
*.swp

# Claude
.claude/learning-progress.md
.claude/learning-context.md

# Secrets
*.pem
*-service-account*.json
gcloud-key.json
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore"
```

### Task 1.3: Add placeholder README

**Files (new repo):**
- Create: `README.md`

- [ ] **Step 1: Write minimal README placeholder**

```markdown
# alpha-whale

AI-powered finance agent. Under active migration from previous monorepo. Full README coming end of migration.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: placeholder README"
```

### Task 1.4: Push initial main branch

- [ ] **Step 1: Push**

```bash
git push -u origin main
```

- [ ] **Step 2: Verify on GitHub**

Run: `gh repo view hcslomeu/alpha-whale --web`
Expected: browser opens showing the placeholder README.

---

## Phase 2 — Copy Python backend code

### Task 2.1: Copy `apps/alpha-whale/api/`

**Files:**
- Source: `~/ai-engineering-monorepo/apps/alpha-whale/api/`
- Destination: `~/alpha-whale/api/`

- [ ] **Step 1: Copy directory**

```bash
cp -R ~/ai-engineering-monorepo/apps/alpha-whale/api ~/alpha-whale/api
```

- [ ] **Step 2: Remove stale caches**

```bash
find ~/alpha-whale/api -type d -name __pycache__ -exec rm -rf {} +
find ~/alpha-whale/api -type d -name .venv -exec rm -rf {} +
```

- [ ] **Step 3: Verify structure**

Run: `ls ~/alpha-whale/api/`
Expected: `__init__.py config.py dependencies.py main.py models.py routes.py py.typed tests`.

- [ ] **Step 4: Move `api/tests/` contents to root `tests/`**

```bash
mkdir -p ~/alpha-whale/tests
cp -R ~/alpha-whale/api/tests/. ~/alpha-whale/tests/
rm -rf ~/alpha-whale/api/tests
```

- [ ] **Step 5: Remove `__init__.py` from `tests/` (avoid pytest collision)**

```bash
rm -f ~/alpha-whale/tests/__init__.py
```

- [ ] **Step 6: Commit**

```bash
git add api/ tests/
git commit -m "feat: import api module"
```

### Task 2.2: Copy `apps/alpha-whale/agent/`

- [ ] **Step 1: Copy**

```bash
cp -R ~/ai-engineering-monorepo/apps/alpha-whale/agent ~/alpha-whale/agent
```

- [ ] **Step 2: Clean caches**

```bash
find ~/alpha-whale/agent -type d -name __pycache__ -exec rm -rf {} +
```

- [ ] **Step 3: Verify**

Run: `ls ~/alpha-whale/agent/`
Expected: `__init__.py chain.py config.py evaluate.py graph.py models.py state.py tools.py`.

- [ ] **Step 4: Commit**

```bash
git add agent/
git commit -m "feat: import agent module"
```

### Task 2.3: Copy `apps/alpha-whale/ingestion/`

- [ ] **Step 1: Copy**

```bash
cp -R ~/ai-engineering-monorepo/apps/alpha-whale/ingestion ~/alpha-whale/ingestion
```

- [ ] **Step 2: Clean caches**

```bash
find ~/alpha-whale/ingestion -type d -name __pycache__ -exec rm -rf {} +
```

- [ ] **Step 3: Verify**

Run: `ls ~/alpha-whale/ingestion/`
Expected: `__init__.py __main__.py bronze.py config.py massive.py pipeline.py rag schemas.py stochastic.py supabase_client.py`.

- [ ] **Step 4: Commit**

```bash
git add ingestion/
git commit -m "feat: import ingestion module"
```

### Task 2.4: Copy `apps/alpha-whale/migrations/`

- [ ] **Step 1: Copy**

```bash
cp -R ~/ai-engineering-monorepo/apps/alpha-whale/migrations ~/alpha-whale/migrations
```

- [ ] **Step 2: Commit**

```bash
git add migrations/
git commit -m "feat: import db migrations"
```

### Task 2.5: Copy tests from `apps/alpha-whale/tests/`

**Files:**
- Source: `~/ai-engineering-monorepo/apps/alpha-whale/tests/`
- Destination: `~/alpha-whale/tests/`

- [ ] **Step 1: Copy (merge with tests already moved from api/)**

```bash
cp -R ~/ai-engineering-monorepo/apps/alpha-whale/tests/. ~/alpha-whale/tests/
```

- [ ] **Step 2: Remove `__init__.py` anywhere under tests/**

```bash
find ~/alpha-whale/tests -name __init__.py -delete
```

- [ ] **Step 3: Clean caches**

```bash
find ~/alpha-whale/tests -type d -name __pycache__ -exec rm -rf {} +
```

- [ ] **Step 4: Verify no dunder init remains**

Run: `find ~/alpha-whale/tests -name __init__.py`
Expected: empty output.

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test: import app-level tests"
```

---

## Phase 3 — Merge `libs/py-core/` into `core/`

### Task 3.1: Create `core/` package

**Files (new repo):**
- Create: `core/__init__.py`

- [ ] **Step 1: Create directory and empty init**

```bash
mkdir -p core
touch core/__init__.py
```

### Task 3.2: Copy py-core source modules

**Files:**
- Source: `~/ai-engineering-monorepo/libs/py-core/src/py_core/`
- Destination: `~/alpha-whale/core/`

- [ ] **Step 1: Copy each module (config, logging, exceptions, observability)**

```bash
cp ~/ai-engineering-monorepo/libs/py-core/src/py_core/config.py ~/alpha-whale/core/
cp ~/ai-engineering-monorepo/libs/py-core/src/py_core/logging.py ~/alpha-whale/core/
cp ~/ai-engineering-monorepo/libs/py-core/src/py_core/exceptions.py ~/alpha-whale/core/
cp ~/ai-engineering-monorepo/libs/py-core/src/py_core/observability.py ~/alpha-whale/core/
```

- [ ] **Step 2: Copy py.typed marker if it exists**

```bash
[ -f ~/ai-engineering-monorepo/libs/py-core/src/py_core/py.typed ] && \
  cp ~/ai-engineering-monorepo/libs/py-core/src/py_core/py.typed ~/alpha-whale/core/ || true
```

- [ ] **Step 3: Copy the `__init__.py` content from py-core**

Inspect source first:

```bash
cat ~/ai-engineering-monorepo/libs/py-core/src/py_core/__init__.py
```

Then copy it verbatim into `~/alpha-whale/core/__init__.py` (overwrite the empty one).

```bash
cp ~/ai-engineering-monorepo/libs/py-core/src/py_core/__init__.py ~/alpha-whale/core/__init__.py
```

- [ ] **Step 4: Verify core contents**

Run: `ls ~/alpha-whale/core/`
Expected: `__init__.py config.py exceptions.py logging.py observability.py` (and optional `py.typed`).

- [ ] **Step 5: Commit**

```bash
git add core/
git commit -m "feat(core): import py-core modules"
```

### Task 3.3: Copy py-core tests into root `tests/` with renamed prefix

**Files:**
- Source: `~/ai-engineering-monorepo/libs/py-core/tests/`
- Destination: `~/alpha-whale/tests/` (renamed)

- [ ] **Step 1: List py-core tests**

Run: `ls ~/ai-engineering-monorepo/libs/py-core/tests/`

- [ ] **Step 2: Copy each test with `test_core_` prefix**

For every `test_<name>.py` in the source (e.g., `test_config.py`, `test_logging.py`, `test_observability.py`, `test_exceptions.py`), copy into new repo with renamed filename:

```bash
for f in ~/ai-engineering-monorepo/libs/py-core/tests/test_*.py; do
  base=$(basename "$f")
  # Skip if already prefixed
  if [[ "$base" == test_core_* ]]; then
    cp "$f" ~/alpha-whale/tests/"$base"
  else
    new="test_core_${base#test_}"
    cp "$f" ~/alpha-whale/tests/"$new"
  fi
done
```

- [ ] **Step 3: Verify**

Run: `ls ~/alpha-whale/tests/test_core_*.py`
Expected: `test_core_config.py test_core_logging.py test_core_observability.py` (and any others present in source).

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test(core): import py-core tests as test_core_*"
```

### Task 3.4: Rewrite all `py_core` imports to `core`

**Files:** every `.py` in new repo.

- [ ] **Step 1: Dry-run grep**

```bash
cd ~/alpha-whale
grep -rn "py_core" --include="*.py" .
```

Note the matches.

- [ ] **Step 2: sed rewrite imports**

```bash
cd ~/alpha-whale
grep -rl "py_core" --include="*.py" . | xargs sed -i '' \
  -e 's/from py_core\./from core./g' \
  -e 's/import py_core\./import core./g' \
  -e 's/from py_core /from core /g' \
  -e 's/import py_core$/import core/g' \
  -e 's/py_core\./core./g'
```

- [ ] **Step 3: Verify nothing remains**

```bash
grep -rn "py_core" --include="*.py" .
```

Expected: empty (or only legitimate string literals — inspect and leave if intentional).

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "refactor: rewrite py_core imports to core"
```

---

## Phase 4 — Single `pyproject.toml` + `uv sync`

### Task 4.1: Write root `pyproject.toml`

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Inspect source pyprojects to capture real deps**

```bash
cat ~/ai-engineering-monorepo/apps/alpha-whale/pyproject.toml
cat ~/ai-engineering-monorepo/libs/py-core/pyproject.toml
```

Note every package in `dependencies` and `[dependency-groups] dev` (or `[tool.poetry.dependencies]` in older format).

- [ ] **Step 2: Write merged pyproject.toml at `~/alpha-whale/pyproject.toml`**

Base content (adjust version pins to what the sources actually had — do NOT introduce new pins without reason):

```toml
[project]
name = "alpha-whale"
version = "0.1.0"
description = "AI-powered finance agent: LangGraph + LlamaIndex + BigQuery + Pinecone + Next.js"
requires-python = ">=3.12"
readme = "README.md"
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
    "supabase>=2.9",
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

[tool.ruff.format]
quote-style = "double"

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

**Important:** before locking the file, compare deps against the two source `pyproject.toml`s. Add any dep that appears in either source. Drop nothing silently.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add root pyproject.toml"
```

### Task 4.2: Install uv if missing, `uv sync`

- [ ] **Step 1: Check uv installed**

Run: `uv --version`
Expected: a version string. If not installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

- [ ] **Step 2: Run sync**

```bash
cd ~/alpha-whale
uv sync
```

Expected: "Resolved N packages" then "Installed N packages". Creates `.venv/` and `uv.lock`.

- [ ] **Step 3: Commit lockfile**

```bash
git add uv.lock
git commit -m "chore: add uv.lock"
```

### Task 4.3: Verify package imports work

- [ ] **Step 1: Smoke import core**

```bash
uv run python -c "from core import config, logging, exceptions, observability; print('core OK')"
```

Expected: "core OK".

- [ ] **Step 2: Smoke import api, agent, ingestion**

```bash
uv run python -c "import api.main, agent.graph, ingestion.bronze; print('app OK')"
```

Expected: "app OK". If ImportError on any module: fix its imports (`from py_core` leftovers, relative-vs-absolute), commit separately, re-run.

- [ ] **Step 3: If fixes needed, commit**

```bash
git add -u
git commit -m "fix: resolve import errors after flat-layout migration"
```

---

## Phase 5 — Get tests green

### Task 5.1: Run `ruff check` and fix

- [ ] **Step 1: Run ruff**

```bash
cd ~/alpha-whale
uv run ruff check .
```

Expected: either "All checks passed!" or a list of errors.

- [ ] **Step 2: Auto-fix what ruff can**

```bash
uv run ruff check . --fix
```

- [ ] **Step 3: Manually fix remaining errors**

For each remaining error, open the file and fix per ruff's suggestion. Common post-migration fixes:
- `I001` (import order) — let ruff --fix handle
- `F401` (unused import) — delete
- `UP017` (datetime.timezone.utc) — `datetime.UTC`
- `N818` (exception name should end in Error) — leave if it's an intentional name

- [ ] **Step 4: Re-run until clean**

```bash
uv run ruff check .
```

Expected: "All checks passed!".

- [ ] **Step 5: Run format check**

```bash
uv run ruff format --check .
```

If it reports diffs:

```bash
uv run ruff format .
```

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "style: apply ruff lint and format"
```

### Task 5.2: Run mypy and fix

- [ ] **Step 1: Run mypy**

```bash
uv run mypy .
```

Expected: success OR a list of type errors.

- [ ] **Step 2: Fix each error**

Common post-migration issues:
- Missing type stubs — `uv add --dev types-<pkg>`
- `Module "py_core" has no attribute X` — leftover rewrite, `sed` it.
- Cross-module import cycles — restructure or import locally inside functions.

After each fix:

```bash
git add -u && git commit -m "fix(types): <description>"
```

- [ ] **Step 3: Re-run until clean**

```bash
uv run mypy .
```

Expected: "Success: no issues found".

### Task 5.3: Run pytest and fix

- [ ] **Step 1: Run pytest**

```bash
uv run pytest
```

Expected: all tests pass (or a concrete failure list).

- [ ] **Step 2: Fix per-failure**

For each failing test:
- Check traceback — is it an import path issue? A fixture missing? A config env-var not set?
- Fix the root cause in either the test or the code (per TDD, prefer fixing code to match test behaviour; if test was wrong for the new layout, fix test).
- Re-run just that test: `uv run pytest tests/test_X.py::test_name -v`.
- Commit the fix.

Common issues:
- `ModuleNotFoundError: No module named 'py_core'` — missed in sed pass; rewrite and commit.
- `ModuleNotFoundError: No module named 'api'` — ensure `pythonpath = ["."]` in pytest config.
- Tests referencing `apps.alpha_whale.X` — rewrite to `X`.
- Fixture `conftest.py` path issues — ensure tests live in flat `tests/`, no nested `__init__.py`.

- [ ] **Step 3: Full green**

```bash
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "test: all tests passing on new layout"
```

---

## Phase 6 — Copy + verify Next.js frontend

### Task 6.1: Copy `web/` sans node_modules

**Files:**
- Source: `~/ai-engineering-monorepo/apps/alpha-whale/web/`
- Destination: `~/alpha-whale/web/`

- [ ] **Step 1: Copy with rsync excluding heavy dirs**

```bash
rsync -a \
  --exclude='node_modules' \
  --exclude='.next' \
  --exclude='tsconfig.tsbuildinfo' \
  ~/ai-engineering-monorepo/apps/alpha-whale/web/ \
  ~/alpha-whale/web/
```

- [ ] **Step 2: Remove any leftover `project.json` (Nx)**

```bash
rm -f ~/alpha-whale/web/project.json
```

- [ ] **Step 3: Verify**

Run: `ls ~/alpha-whale/web/`
Expected: `app components components.json eslint.config.mjs lib next-env.d.ts next.config.ts package.json postcss.config.mjs public tsconfig.json`.

- [ ] **Step 4: Commit (pre-install)**

```bash
git add web/
git commit -m "feat(web): import Next.js frontend"
```

### Task 6.2: Install deps + lock

- [ ] **Step 1: Install**

```bash
cd ~/alpha-whale/web
npm install
```

Expected: `package-lock.json` generated, `node_modules/` populated.

- [ ] **Step 2: Commit lockfile**

```bash
cd ~/alpha-whale
git add web/package-lock.json
git commit -m "chore(web): add package-lock.json"
```

### Task 6.3: Lint + build frontend

- [ ] **Step 1: Lint**

```bash
cd ~/alpha-whale/web
npm run lint
```

Expected: no errors.

- [ ] **Step 2: Build**

```bash
npm run build
```

Expected: successful build with `.next/` output.

- [ ] **Step 3: If errors, fix and commit per fix**

Common issues:
- Missing env var `NEXT_PUBLIC_API_URL` — add to `.env.local` and to `next.config.ts` if needed; do NOT commit `.env.local`.
- ESLint cfg referencing deprecated rules — update.

After fixes:

```bash
git add -u
git commit -m "fix(web): resolve lint/build errors"
```

---

## Phase 7 — Dockerize backend

### Task 7.1: Write `Dockerfile`

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Write Dockerfile**

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

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Write `.dockerignore`**

**Files:**
- Create: `.dockerignore`

```gitignore
.venv
__pycache__
*.pyc
.pytest_cache
.mypy_cache
.ruff_cache
tests/
web/
docs/
migrations/
.git/
.github/
.claude/
.env
.env.local
*.md
!README.md
node_modules
.next
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat(docker): add backend Dockerfile and dockerignore"
```

### Task 7.2: Build image locally

- [ ] **Step 1: Build**

```bash
cd ~/alpha-whale
docker build -t alpha-whale:dev .
```

Expected: build succeeds, final image listed.

- [ ] **Step 2: Check size**

Run: `docker images alpha-whale:dev`
Expected: size reasonable (< 700MB, ideally < 500MB).

### Task 7.3: Write `docker-compose.yml`

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Write compose file**

```yaml
services:
  api:
    build: .
    image: alpha-whale:dev
    container_name: alpha-whale-api
    restart: unless-stopped
    env_file: .env
    ports:
      - "127.0.0.1:8000:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
```

- [ ] **Step 2: Write `.env.example`**

**Files:**
- Create: `.env.example`

```env
# LLM
OPENAI_API_KEY=

# LangSmith tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=alpha-whale

# Market data
ALPHA_VANTAGE_API_KEY=

# Vector store
PINECONE_API_KEY=
PINECONE_INDEX_NAME=alpha-whale

# BigQuery
GOOGLE_APPLICATION_CREDENTIALS=/app/gcloud-key.json
BIGQUERY_PROJECT_ID=
BIGQUERY_DATASET=alpha_whale

# Supabase (LangGraph checkpointer)
SUPABASE_URL=
SUPABASE_KEY=

# App
LOG_LEVEL=INFO
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat(docker): add compose and env template"
```

### Task 7.4: Verify local compose works

- [ ] **Step 1: Copy env template, fill minimum to boot**

```bash
cp .env.example .env
# Edit .env: at minimum set OPENAI_API_KEY to a valid key (or a dummy if health endpoint is offline-safe)
```

- [ ] **Step 2: Boot**

```bash
docker compose up -d
docker compose logs -f api
```

Expected: "Uvicorn running on http://0.0.0.0:8000".

- [ ] **Step 3: Hit health endpoint**

```bash
curl -sf http://localhost:8000/health
```

Expected: 200 response.

- [ ] **Step 4: Tear down**

```bash
docker compose down
```

---

## Phase 8 — GitHub Actions CI

### Task 8.1: Write `ci.yml`

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true

      - name: Install Python deps
        run: uv sync --frozen

      - name: Ruff lint
        run: uv run ruff check .

      - name: Ruff format check
        run: uv run ruff format --check .

      - name: Mypy
        run: uv run mypy .

      - name: Pytest
        run: uv run pytest

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

      - name: Install web deps
        run: npm ci

      - name: Lint
        run: npm run lint

      - name: Build
        run: npm run build
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add python and web CI workflow"
```

### Task 8.2: Push + verify CI passes

- [ ] **Step 1: Push all Phase 1–8 commits**

```bash
git push
```

- [ ] **Step 2: Watch CI**

```bash
gh run watch
```

Expected: both jobs green.

- [ ] **Step 3: If CI fails, fix and re-push**

For each failure, reproduce locally (`uv run pytest` etc.), fix, commit, push. Don't mark this task done until CI is green.

---

## Phase 9 — README + architecture doc

### Task 9.1: Write production README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write full README (replace placeholder)**

```markdown
# alpha-whale

AI-powered finance agent. LangGraph orchestration over market data (BigQuery), a Pinecone RAG index, and structured extraction via Instructor — exposed as a Next.js chat UI.

## Stack

- **Agent:** LangGraph ≥ 1.0, LangChain, LangSmith tracing
- **Data:** BigQuery (medallion: Bronze/Silver/Gold), Alpha Vantage ingestion
- **RAG:** LlamaIndex + Pinecone vector store
- **Structured extraction:** Instructor
- **API:** FastAPI + uvicorn, Pydantic v2, structlog, OpenTelemetry
- **Frontend:** Next.js 15, React 19, Tailwind v4, Radix UI, Framer Motion
- **Infra:** Docker, Docker Compose, Caddy (reverse proxy), AWS Lightsail, Vercel

## Architecture

See `docs/architecture.md` for the full picture.

```
web (Next.js, Vercel)  ──HTTPS──▶  api (FastAPI, Lightsail)
                                    │
                                    ├─▶ agent (LangGraph)
                                    │      ├─▶ Pinecone (RAG)
                                    │      ├─▶ BigQuery (Silver/Gold)
                                    │      └─▶ Alpha Vantage
                                    └─▶ Supabase (checkpointer)
```

## Run locally

### Backend

```bash
uv sync
cp .env.example .env           # fill keys
uv run uvicorn api.main:app --reload
```

Swagger UI: http://localhost:8000/docs

### Frontend

```bash
cd web
npm install
npm run dev
```

http://localhost:3000

### Full stack via Docker

```bash
docker compose up -d
curl http://localhost:8000/health
```

## Test + quality

```bash
uv run pytest
uv run ruff check .
uv run mypy .

cd web && npm run lint && npm run build
```

## Deploy

Backend → Lightsail (Docker Compose + Caddy). Frontend → Vercel (auto on push).

Runbook: `docs/deploy.md`.

## License

MIT.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: production README"
```

### Task 9.2: Write architecture doc

**Files:**
- Create: `docs/architecture.md`

- [ ] **Step 1: Write architecture**

```markdown
# Architecture

## Modules

| Module | Purpose | Imports allowed |
|---|---|---|
| `api/` | FastAPI HTTP surface — routes, request validation, session handling | `agent/`, `core/` |
| `agent/` | LangGraph StateGraph, tool orchestration, HITL gating | `core/` only |
| `ingestion/` | Data-layer CLI scripts — no HTTP surface | `core/` only |
| `core/` | Cross-cutting: Pydantic settings, structlog, OTel, custom exceptions | (leaf) |
| `web/` | Next.js chat UI | external API via fetch |

No circular imports. `core/` is a leaf.

## Request flow (chat)

1. User types in `web/`.
2. `POST /agent/invoke` with `{message, thread_id}`.
3. `api/routes.py` loads checkpointed state from Supabase, calls `agent.graph.invoke(...)`.
4. `llm_node` → tool calls → `tools_node` → `llm_node` → final answer.
5. `risk_gate` may interrupt with HITL — client hits `/agent/resume` to continue.
6. Response streamed back to web UI.

## Tools (`agent/tools.py`)

- `get_price(ticker)` — Alpha Vantage fetch, cached.
- `rag_search(query)` — Pinecone query via LlamaIndex.
- `bigquery_query(sql)` — read-only Silver/Gold tables, parameterized.
- `extract_signal(text)` — Instructor structured extraction.

## Ingestion flow

```bash
python -m ingestion.bronze --ticker AAPL --days 30
python -m ingestion.pipeline
python -m ingestion.rag.indexing --source news
```

Bronze → Silver → Gold medallion in BigQuery. Embeddings upserted to Pinecone.

## Observability

- LangSmith: full agent traces (LLM calls, tool I/O, latencies).
- structlog: app logs, JSON output.
- OpenTelemetry: FastAPI middleware traces (optional collector).
- Caddy: access logs on server.

## Why this shape

- Flat package layout, single uv project — zero monorepo overhead for one deployed app.
- `core/` as leaf prevents the settings/logging module from becoming a cross-cutting dumping ground.
- LangGraph checkpointer on Supabase enables HITL resume across process restarts.
- Ingestion as CLI scripts — no scheduler in v1 (YAGNI). Add cron on the VPS if/when needed.
```

- [ ] **Step 2: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: architecture overview"
```

### Task 9.3: Write deploy runbook (Plan B preview)

**Files:**
- Create: `docs/deploy.md`

- [ ] **Step 1: Write runbook**

```markdown
# Deployment Runbook

## Prerequisites

- AWS account with Lightsail enabled.
- Domain registered (Cloudflare/Namecheap).
- Vercel account linked to GitHub.
- GitHub repo secrets: `LIGHTSAIL_HOST`, `LIGHTSAIL_SSH_KEY`.

## Lightsail bootstrap

1. Create instance: Ubuntu 24.04 LTS, $5/mo plan, `eu-west-2`.
2. Attach static IP.
3. Open firewall: 22 (your IP only), 80, 443.
4. SSH in as `ubuntu`.

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
exit   # re-login for group to apply
```

5. Install Caddy:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

6. Clone repo + set secrets:

```bash
git clone https://github.com/hcslomeu/alpha-whale.git ~/alpha-whale
cd ~/alpha-whale
cp .env.example .env
chmod 600 .env
# Populate .env with real keys + upload service-account JSON if BigQuery.
```

7. First run:

```bash
docker compose up -d
curl -sf http://localhost:8000/health
```

8. Caddyfile at `/etc/caddy/Caddyfile`:

```
api.alphawhale.<domain> {
    reverse_proxy 127.0.0.1:8000
    encode gzip
    log {
        output file /var/log/caddy/alphawhale.log
    }
}
```

```bash
sudo systemctl reload caddy
```

## DNS

At registrar:

- `A  api.alphawhale  → <Lightsail static IP>`
- `CNAME  alphawhale  → cname.vercel-dns.com`

Caddy auto-fetches Let's Encrypt cert on first HTTPS hit.

## Vercel

1. Import `hcslomeu/alpha-whale` into Vercel.
2. Project settings → Root directory: `web`.
3. Env var: `NEXT_PUBLIC_API_URL=https://api.alphawhale.<domain>`.
4. Deploy.
5. Add custom domain `alphawhale.<domain>` in Vercel.

## GitHub Actions deploy secret wiring

```bash
gh secret set LIGHTSAIL_HOST --body "<static-ip-or-dns>"
gh secret set LIGHTSAIL_SSH_KEY < ~/.ssh/lightsail-alpha-whale
```

## Verify

```bash
curl -sf https://api.alphawhale.<domain>/health
```

Expected: 200.

Open `https://alphawhale.<domain>` in a browser — chat UI should round-trip to the backend.
```

- [ ] **Step 2: Commit**

```bash
git add docs/deploy.md
git commit -m "docs: deployment runbook"
```

### Task 9.4: Add deploy.yml workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: Write workflow**

```yaml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:

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
            docker compose build
            docker compose up -d
            docker image prune -f
```

- [ ] **Step 2: Commit + push**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: deploy workflow for lightsail ssh"
git push
```

- [ ] **Step 3: Verify deploy workflow exists on GitHub**

Run: `gh workflow list`
Expected: both `CI` and `Deploy` listed. `Deploy` will no-op until secrets are set (Plan B).

### Task 9.5: Keep selected `.claude/` assets

**Files:**
- Create: `~/alpha-whale/.claude/hooks/ruff-format-on-save.sh`
- Create: `~/alpha-whale/.claude/skills/` (selected skills only)
- Create: `~/alpha-whale/CLAUDE.md`

- [ ] **Step 1: Copy hook script**

```bash
mkdir -p ~/alpha-whale/.claude/hooks
cp ~/ai-engineering-monorepo/.claude/hooks/ruff-format-on-save.sh ~/alpha-whale/.claude/hooks/
chmod +x ~/alpha-whale/.claude/hooks/ruff-format-on-save.sh
```

- [ ] **Step 2: Copy settings.json if it references the hook**

```bash
[ -f ~/ai-engineering-monorepo/.claude/settings.json ] && \
  cp ~/ai-engineering-monorepo/.claude/settings.json ~/alpha-whale/.claude/settings.json || true
```

- [ ] **Step 3: Copy selected skills only**

```bash
mkdir -p ~/alpha-whale/.claude/skills
for skill in review-pr generate-linkedin-post claude-code-practices agent-development; do
  src=~/ai-engineering-monorepo/.claude/skills/$skill
  [ -d "$src" ] && cp -R "$src" ~/alpha-whale/.claude/skills/ || true
done
```

Drop: `scaffold-py-lib` (no libs anymore), `wp-research`/`wp-research.md` (no WP workflow).

- [ ] **Step 4: Write slim CLAUDE.md for the new repo**

```markdown
# CLAUDE.md

## Project
`alpha-whale` — AI finance agent. LangGraph + LlamaIndex + BigQuery + Pinecone + Next.js. Single-project repo (no workspaces).

## Structure
- `api/`       FastAPI
- `agent/`     LangGraph agent
- `ingestion/` data pipelines (CLI)
- `core/`      settings, logging, exceptions, OTel
- `web/`       Next.js 15 frontend
- `tests/`     flat pytest tree
- `migrations/` DB migrations

## Import rules
- `api` → may import `agent`, `core`
- `agent` → `core` only
- `ingestion` → `core` only
- `core` → leaf (no internal imports)

## Quality gates (run before commit)
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest

cd web && npm run lint && npm run build
```

## Git
- Conventional Commits: `type(scope): description`.
- No `Co-Authored-By` lines.
- Provide git commands as text for the user to run; don't auto-execute.

## Security
- Never commit `.env`, service-account JSON, or secrets.
- Use `SecretStr` for API keys in Pydantic Settings.
- Parameterised BigQuery queries only.

## Deploy
Backend → Lightsail via `.github/workflows/deploy.yml`. Frontend → Vercel (auto on `main`).
Runbook: `docs/deploy.md`.
```

- [ ] **Step 5: Commit**

```bash
git add .claude/ CLAUDE.md
git commit -m "chore: claude-code config for new repo"
```

### Task 9.6: Final push + final CI check

- [ ] **Step 1: Push**

```bash
git push
```

- [ ] **Step 2: Watch CI**

```bash
gh run watch
```

Expected: `CI` green.

- [ ] **Step 3: Verify repo looks right**

```bash
gh repo view hcslomeu/alpha-whale --web
```

Expected: clean top-level tree — `api/ agent/ core/ docs/ ingestion/ migrations/ tests/ web/ .github/ .claude/ Dockerfile README.md ...`

- [ ] **Step 4: Announce Plan A complete**

At this point:
- New repo exists, public, pushed.
- Python CI + Web CI green.
- Local `docker compose up` serves `/health` → 200.
- Frontend `npm run build` produces a working `.next/`.
- README + architecture + deploy runbook written.

Plan A done. Plan B (Lightsail provision + DNS + archive old repo) is follow-up manual work — runbook already written at `docs/deploy.md`.

---

## Self-review against spec

- **Phase 0** covers `apps/alpha-whale/testing_utils.py` and other WIP (Open item 5).
- **Phase 2** covers all shipped modules (api, agent, ingestion, tests, migrations).
- **Phase 3** covers py-core merge (spec decision 5) + import rewrite.
- **Phase 4** covers single `pyproject.toml` + uv lockfile.
- **Phase 5** covers green tests + ruff + mypy.
- **Phase 6** covers Next.js frontend import + build.
- **Phase 7** covers Dockerfile + compose + `.env.example`.
- **Phase 8** covers CI workflow.
- **Phase 9** covers README, architecture, deploy runbook, `.claude/` carry-over, deploy.yml.

Plan B (Phases 10–12 in spec) lives as `docs/deploy.md` content + the follow-up manual steps listed in Task 9.4 and deploy runbook. Not separate tasks in this plan because they are infra-provisioning, not code work.

**Gaps/Open items from spec addressed here:**
- Domain (Open 1) — still TBD; flagged in Task 9.3 runbook as `<domain>` placeholder to fill at deploy time.
- `.claude/` skills selection (Open 2) — resolved in Task 9.5.
- README content (Open 3) — written in Task 9.1.
- `massive.py` / `supabase_client.py` (Open 4) — copied as-is in Task 2.3; no pruning (YAGNI on cleanup; they're shipped code).
- `testing_utils.py` (Open 5) — covered in Task 0.2 decision step.
