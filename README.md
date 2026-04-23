# alpha-whale

AI-powered finance agent. Conversational trading assistant with retrieval-augmented reasoning over SEC filings, market data, and financial news.

[![CI](https://github.com/hcslomeu/alpha-whale/actions/workflows/ci.yml/badge.svg)](https://github.com/hcslomeu/alpha-whale/actions/workflows/ci.yml)

## Stack

**Backend (Python 3.12):** FastAPI · LangGraph 1.0 · LangChain · LlamaIndex · Pinecone · Instructor · Logfire · Supabase
**Frontend (Next.js 15):** React 19 · Tailwind v4 · Radix UI · Framer Motion
**Infra:** Docker · Caddy (auto-TLS) · AWS Lightsail (API) · Vercel (web) · GitHub Actions CI/CD

## What it does

- **Agent** — LangGraph state machine with tools for market data, indicators, and knowledge-base retrieval. Human-in-the-loop gates for high-risk actions (execution, large positions).
- **RAG pipeline** — Ingests SEC 10-K/10-Q filings (EDGAR) + financial news (Firecrawl) → metadata-enhanced chunks → Pinecone vector store → hybrid retrieval (dense + BM25) → Cohere rerank.
- **Structured extraction** — Instructor-backed Pydantic output for deterministic downstream consumption.
- **Observability** — Logfire traces + metrics across agent steps, tool calls, and RAG retrieval.

## Repository layout

```
alpha-whale/
├── agent/           # LangGraph graph, tools, risk gate, evaluation
├── api/             # FastAPI app + routes (chat, SSE streaming)
├── core/            # Shared utilities: config, logging, observability, async HTTP, Redis
├── ingestion/       # Market data + RAG ingestion (EDGAR, Firecrawl, chunking, indexing)
├── migrations/      # SQL migrations (Supabase)
├── tests/           # Pytest suite (358 tests)
├── web/             # Next.js frontend
├── Dockerfile       # Multi-stage uv build
├── docker-compose.yml
├── Caddyfile        # Reverse proxy + auto-TLS
└── docs/
    ├── architecture.md
    └── deploy.md    # Lightsail + Vercel provisioning runbook
```

## Quickstart

```bash
# Backend
uv sync
cp .env.example .env  # fill in API keys
uv run uvicorn --factory api.main:create_app --reload

# Frontend
cd web
pnpm install
pnpm dev
```

Open http://localhost:3000.

## Quality gates

```bash
uv run ruff check .          # Lint
uv run ruff format --check . # Format
uv run mypy agent api core ingestion  # Strict type-check
uv run pytest                # 358 tests
```

All four pass in CI on every push.

## Deployment

Backend: AWS Lightsail (Docker Compose + Caddy). Frontend: Vercel.
See [`docs/deploy.md`](docs/deploy.md) for the full runbook.

## License

MIT
