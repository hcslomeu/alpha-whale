# Architecture

## System overview

```
┌─────────────┐      HTTPS      ┌──────────────────┐
│   Vercel    │ ◄─── static ──► │   Next.js 15     │
│  (frontend) │                 │  React 19, Radix │
└──────┬──────┘                 └──────────────────┘
       │ /api/* fetch
       ▼
┌──────────────────────────────────────────────────┐
│   AWS Lightsail (eu-west-2) · 1GB · $5/mo         │
│                                                   │
│   ┌────────────┐     ┌──────────────────────┐    │
│   │   Caddy    │ ──► │  FastAPI (uvicorn)   │    │
│   │  :80 :443  │     │  api.main:create_app │    │
│   │  auto-TLS  │     └─────────┬────────────┘    │
│   └────────────┘               │                 │
│                                │ LangGraph       │
│                                ▼                 │
│                    ┌───────────────────────┐     │
│                    │   Agent state machine │     │
│                    │   llm → tools → gate  │     │
│                    └─────────┬─────────────┘     │
└──────────────────────────────┼───────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │   Pinecone   │   │   Supabase   │   │   OpenAI     │
    │  (vectors)   │   │  (pg chkpt)  │   │ (LLM+embed)  │
    └──────────────┘   └──────────────┘   └──────────────┘
```

## Layers

### `core/` — shared utilities

Pure-Python foundation reused by all other packages. No domain logic.

- `config/` — Pydantic `BaseSettings` with env + `.env` loading
- `logging/` — `structlog` configuration + `get_logger(name)`
- `observability.py` — Logfire init + FastAPI instrumentation
- `async_utils.py` — `AsyncHTTPClient`, `retry_with_backoff`, `gather_with_concurrency`
- `redis_client.py` — Async Redis wrapper
- `extraction.py` — Instructor client factory for structured outputs
- `exceptions/` — Domain-typed exception hierarchy

### `ingestion/` — Medallion pipeline

Bronze → Silver → Gold flow for market data and knowledge-base sources.

- `bronze.py` — Raw market data ingest (Alpha Vantage → Supabase)
- `massive.py` — Batch market data loader
- `stochastic.py` — Indicator computation (EMA, RSI, Stochastic)
- `pipeline.py` — Top-level orchestrator
- `rag/` — RAG-specific subpipeline:
  - `edgar.py` — SEC EDGAR 10-K/10-Q fetcher (HTML → text)
  - `firecrawl_source.py` — News article scraping
  - `chunking.py` — Metadata-enhanced chunking (ticker, filing type, section)
  - `indexing.py` — Embed + upsert to Pinecone
  - `retrieval.py` — Hybrid retrieval (dense + BM25 fusion + Cohere rerank)
  - `pipeline.py` — End-to-end RAG pipeline

### `agent/` — LangGraph state machine

- `state.py` — `AgentState` TypedDict (messages, risk flags, tool results)
- `graph.py` — StateGraph with nodes: `llm`, `tools`, `risk_gate`, conditional edges, `MemorySaver` checkpointer
- `tools.py` — Tool-calling surface: `get_market_data`, `compute_indicators`, `query_knowledge_base`
- `models.py` — Pydantic schemas for tool arguments and agent outputs
- `chain.py` — Pre-LangGraph LangChain tool-calling chain (legacy, kept for comparison)
- `config.py` — Agent-level settings (model, temperature, tool timeouts)
- `evaluate.py` — LangSmith evaluation harness

### `api/` — FastAPI surface

- `main.py` — `create_app()` factory with middleware (CORS, Logfire)
- `routes.py` — `POST /api/chat` (SSE streaming), `GET /health`, thread management
- `dependencies.py` — Dependency-injected `get_graph`, `get_redis_client`, `get_supabase`
- `config.py` — API-level settings
- `models.py` — Request/response schemas

### `web/` — Next.js frontend

- `app/` — App Router entry (`layout.tsx`, `page.tsx`)
- `components/` — Chat UI, message rendering, Radix primitives
- `lib/` — API client, utilities

Deploys to Vercel. Calls the Lightsail-hosted API via `NEXT_PUBLIC_API_URL`.

## Data flows

### Chat turn

1. Browser → Vercel (SSR) → `POST /api/chat` via SSE
2. FastAPI route creates/loads `thread_id` state from Supabase checkpoint
3. LangGraph invokes `llm` node → decides on tool call or final answer
4. If tool call: `tools` node executes → may hit Pinecone (RAG), Supabase (market data), or external APIs
5. `risk_gate` checks for HITL conditions (trade execution, large positions) — pauses graph if triggered
6. Stream tokens back via SSE; persist updated state to Supabase

### RAG ingestion (offline)

1. Scheduler triggers `ingestion.rag.pipeline.run()`
2. EDGAR + Firecrawl fetch new filings/articles → raw docs
3. `chunking` splits with ticker/filing/section metadata
4. `indexing` embeds via OpenAI + upserts to Pinecone

### RAG retrieval (online, agent tool)

1. Agent calls `query_knowledge_base(query, filters)`
2. Hybrid retriever: dense (Pinecone embedding search) + BM25 (in-memory sparse) → RRF fusion
3. Cohere reranks top-k → returns context chunks

## Cross-cutting

- **Observability:** Logfire spans wrap every LangGraph node + tool + RAG retrieval. Metrics: tool duration histogram, retrieval latency, cache hit counter.
- **State persistence:** Supabase Postgres as LangGraph checkpoint store (thread-scoped).
- **Caching:** Redis for idempotent market-data lookups (TTL: 1 hour).
- **Secrets:** `SecretStr` throughout; never logged. Loaded from env or Lightsail `.env`.
