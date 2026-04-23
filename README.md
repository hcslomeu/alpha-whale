# alpha-whale

AI-powered finance agent. Conversational trading assistant with retrieval-augmented reasoning.

**Stack:** Python 3.12 · FastAPI · LangGraph · LangChain · LlamaIndex · Pinecone · BigQuery · Instructor · Next.js 15 · Tailwind v4

**Status:** Migration in progress — setting up from scratch. See [`.claude/specs/`](.claude/specs/) for design + implementation plan.

## Quickstart

```bash
# API
uv sync
uv run uvicorn api.main:app --reload

# Web
cd web && pnpm install && pnpm dev
```

Full docs coming in Phase 9.
