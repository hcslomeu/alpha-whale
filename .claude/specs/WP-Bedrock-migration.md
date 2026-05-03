# WP-Bedrock — Migrate LLM + Embeddings from OpenAI to AWS Bedrock

> **Status:** Draft
> **Owner:** Claude (executor) + user (provisioning)
> **Blocked by:** §6 of `docs/provisioning.md` — IAM keys + model access granted
> **Sub-skill (for executor):** `superpowers:executing-plans`

## Goal

Replace direct OpenAI API usage (`ChatOpenAI`, `OpenAIEmbedding`, `instructor.from_openai`) with AWS Bedrock equivalents (`ChatBedrockConverse`, `BedrockEmbedding`, `instructor.from_bedrock`). Single AWS bill consumes existing AWS credits. Keep all tests green. Re-create Pinecone index at dim 1024.

## Why

User has AWS promo credits (~$200). OpenAI direct API charges separately and does not consume AWS credits. Bedrock = AWS-native LLM API → credits apply, single bill, IAM-scoped. Lightsail eu-west-2 + Bedrock eu-west-2 = co-located → ~0ms LLM latency.

## What changes

| File | Current | After |
|---|---|---|
| `agent/graph.py` | `ChatOpenAI("gpt-5-mini")` | `ChatBedrockConverse(model_id=BEDROCK_CHAT_MODEL)` |
| `agent/chain.py` | `ChatOpenAI("gpt-4o-mini")` | same as above |
| `core/extraction.py` | `instructor.from_openai(OpenAI())` | `instructor.from_bedrock(boto3.client("bedrock-runtime"))` |
| `ingestion/rag/indexing.py` | `OpenAIEmbedding(text-embedding-3-small)` | `BedrockEmbedding(amazon.titan-embed-text-v2:0)` |
| `ingestion/rag/config.py` | `openai_api_key`, `embedding_dimensions=1536` | drop `openai_api_key`, default dims=1024, add AWS region/model fields |
| `pyproject.toml` | `openai`, `langchain-openai`, `llama-index-embeddings-openai` | add `langchain-aws`, `llama-index-embeddings-bedrock`, `boto3`; drop OpenAI deps |
| Pinecone index | dim 1536 | dim 1024 (re-create) |
| `.env` (local + Lightsail) | `OPENAI_API_KEY` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `BEDROCK_CHAT_MODEL`, `BEDROCK_EMBED_MODEL` |

## What stays

- LangGraph state machine, tools, system prompt (same `bind_tools` API on `ChatBedrockConverse`)
- Pinecone (just dim change), Supabase, Upstash Redis, Cohere rerank, Firecrawl, LangSmith, Logfire — all unchanged
- Instructor public API in `core/extraction.py` — only the inner client backend changes
- All tool definitions in `agent/tools.py`

## What we're NOT doing

- ❌ Swapping vector store (still Pinecone)
- ❌ Swapping reranker (still Cohere — cheap, free-tier covers it, no Bedrock equivalent worth the latency)
- ❌ Removing Instructor (keep it; just change backend)
- ❌ Adding Bedrock Agents / Knowledge Bases (managed services duplicate what we already have)
- ❌ Multi-model routing (one chat model, one embed model)

---

## Phase 0 — Pre-flight (user action)

**Blocks all subsequent phases.**

- [ ] User completed `docs/provisioning.md` §6 (IAM user + access keys + model access)
- [ ] User pasted `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` to executor (or set in local `.env`)
- [ ] `aws bedrock list-foundation-models --region eu-west-2` returns `ACTIVE` for both models

**Success:** local `aws` CLI sanity check passes; both model IDs resolve.

---

## Phase 1 — Dependencies

### Step 1.1: Update `pyproject.toml`

```toml
dependencies = [
    # ... unchanged ...

    # REMOVE:
    # "openai>=1.0",
    # "langchain-openai>=0.3",
    # "llama-index-embeddings-openai>=0.6",

    # ADD:
    "boto3>=1.35",
    "langchain-aws>=0.2",
    "llama-index-embeddings-bedrock>=0.5",
]
```

> Keep `instructor>=1.0` — it has a Bedrock backend via `instructor.from_bedrock(boto3.client(...))`.

### Step 1.2: Sync

```bash
uv sync
```

### Step 1.3: Verify imports

```bash
uv run python -c "from langchain_aws import ChatBedrockConverse; from llama_index.embeddings.bedrock import BedrockEmbedding; import instructor; print('ok')"
```

**Success:** prints `ok` without ImportError.

---

## Phase 2 — Chat LLM swap

### Step 2.1: `agent/graph.py`

Replace:
```python
from langchain_openai import ChatOpenAI
# ...
llm = ChatOpenAI(model="gpt-5-mini", temperature=0.0)
```

With:
```python
from langchain_aws import ChatBedrockConverse
# ...
import os
llm = ChatBedrockConverse(
    model_id=os.environ.get("BEDROCK_CHAT_MODEL", "anthropic.claude-3-5-haiku-20241022-v1:0"),
    region_name=os.environ.get("AWS_REGION", "eu-west-2"),
    temperature=0.0,
)
```

> `ChatBedrockConverse` (Converse API) supports `bind_tools` identically to `ChatOpenAI`. No tool schema changes needed.

### Step 2.2: `agent/chain.py`

Same swap. Drop the older `gpt-4o-mini` reference; reuse same env-var-driven model id.

### Step 2.3: LangChain Redis cache

Verify `RedisCache` still works with `ChatBedrockConverse` — it caches at the LangChain layer, so it should be model-agnostic. Add smoke test if uncertain.

**Success:** `uv run pytest tests/test_agent_graph.py -k "agent_node"` passes (will need fixture changes — see Phase 5).

---

## Phase 3 — Embeddings swap

### Step 3.1: `ingestion/rag/config.py`

Replace:
```python
openai_api_key: SecretStr = Field(validation_alias="OPENAI_API_KEY")
# ...
embedding_model: str = Field(default="text-embedding-3-small", ...)
embedding_dimensions: int = Field(default=1536, ...)
```

With:
```python
aws_region: str = Field(default="eu-west-2", validation_alias="AWS_REGION")
# ...
embedding_model: str = Field(
    default="amazon.titan-embed-text-v2:0", validation_alias="BEDROCK_EMBED_MODEL"
)
embedding_dimensions: int = Field(default=1024, validation_alias="RAG_EMBEDDING_DIMENSIONS")
```

> `boto3` reads `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` from env vars implicitly. No `SecretStr` field needed unless we want explicit logging redaction (Pydantic still redacts `SecretStr` in repr — recommend adding `aws_secret_access_key: SecretStr | None` field for safety).

### Step 3.2: `ingestion/rag/indexing.py`

Replace:
```python
from llama_index.embeddings.openai import OpenAIEmbedding

def build_embed_model(settings: RAGSettings) -> OpenAIEmbedding:
    return OpenAIEmbedding(
        model=settings.embedding_model,
        api_key=settings.openai_api_key.get_secret_value(),
        dimensions=settings.embedding_dimensions,
    )
```

With:
```python
from llama_index.embeddings.bedrock import BedrockEmbedding

def build_embed_model(settings: RAGSettings) -> BedrockEmbedding:
    return BedrockEmbedding(
        model_name=settings.embedding_model,
        region_name=settings.aws_region,
        # boto3 picks up AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from env
    )
```

> Titan v2 supports `additional_kwargs={"dimensions": 256|512|1024}`. Default 1024 — matches Pinecone index.

**Success:** `uv run pytest tests/test_rag_indexing.py` passes (after Phase 5 fixture updates).

---

## Phase 4 — Instructor extraction swap

### Step 4.1: `core/extraction.py`

Replace:
```python
from openai import OpenAI

def create_instructor_client(*, openai_client: OpenAI | None = None, ...) -> instructor.Instructor:
    base_client = openai_client or OpenAI()
    return instructor.from_openai(base_client, mode=mode)

def extract(text, response_model, *, model="gpt-4o-mini", ...):
    ...
```

With:
```python
import os
import boto3

def create_instructor_client(
    *,
    bedrock_client: Any | None = None,
    mode: instructor.Mode = instructor.Mode.ANTHROPIC_TOOLS,
) -> instructor.Instructor:
    base_client = bedrock_client or boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "eu-west-2"),
    )
    return instructor.from_bedrock(base_client, mode=mode)

def extract(
    text,
    response_model,
    *,
    model: str | None = None,
    max_retries: int = 2,
):
    client = _get_client()
    model = model or os.environ.get("BEDROCK_CHAT_MODEL", "anthropic.claude-3-5-haiku-20241022-v1:0")
    return client.messages.create(  # ← anthropic-style, NOT chat.completions
        model=model,
        response_model=response_model,
        max_retries=max_retries,
        max_tokens=1024,
        messages=[{"role": "user", "content": text}],
    )
```

> ⚠️ **API shape change.** Instructor's Anthropic backend uses `client.messages.create(...)` not `client.chat.completions.create(...)`, and requires `max_tokens`. Audit all callers for breakage.

### Step 4.2: Audit callers of `extract()`

```bash
grep -rn "extract(" agent/ ingestion/ core/ tests/ --include="*.py"
```

Verify each call passes a `response_model`. Public signature unchanged (only internals + default model differ).

**Success:** `uv run pytest tests/test_extraction.py` passes (after Phase 5).

---

## Phase 5 — Test fixture updates

Tests currently mock `openai.OpenAI` and `langchain_openai.ChatOpenAI`. Switch to mocking boto3 + LangChain Bedrock.

### Files likely affected (verify with grep)

```bash
grep -rln "ChatOpenAI\|OpenAIEmbedding\|instructor.from_openai\|openai.OpenAI" tests/
```

Expected hits:
- `tests/test_agent_graph.py` — mock `langchain_aws.ChatBedrockConverse` instead
- `tests/test_extraction.py` — mock `instructor.from_bedrock` or stub `boto3.client`
- `tests/test_rag_indexing.py` — mock `BedrockEmbedding`
- `tests/test_rag_config.py` — update env var assertions (drop `OPENAI_API_KEY`, add `AWS_*`)

### Pattern: replace `monkeypatch.setenv("OPENAI_API_KEY", ...)` with:

```python
monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key")
monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
monkeypatch.setenv("AWS_REGION", "eu-west-2")
```

### Pattern: replace `Mock(spec=ChatOpenAI)` with `Mock(spec=ChatBedrockConverse)`.

**Success:** full `uv run pytest` green.

---

## Phase 6 — Local validation (smoke)

Requires real AWS credentials in local `.env`. **Costs cents** (paid via AWS credits anyway).

### Step 6.1: Chat smoke

```bash
uv run python -c "
from agent.graph import get_model
m = get_model()
out = m.invoke([{'role': 'user', 'content': 'Say one word: hi'}])
print(out.content)
"
```

Expect: short response (model ID logged to stdout).

### Step 6.2: Embedding smoke

```bash
uv run python -c "
from ingestion.rag.config import RAGSettings
from ingestion.rag.indexing import build_embed_model
m = build_embed_model(RAGSettings())
emb = m.get_text_embedding('hello world')
print(f'dim={len(emb)}')
"
```

Expect: `dim=1024`.

### Step 6.3: Extraction smoke

```bash
uv run python -c "
from pydantic import BaseModel
from core.extraction import extract
class P(BaseModel):
    name: str
    age: int
p = extract('John is 30 years old', P)
print(p)
"
```

Expect: `P(name='John', age=30)`.

**Success:** all three print expected output, no AWS access errors.

---

## Phase 7 — Pinecone re-index

**Only run after** Phases 1-6 green.

### Step 7.1: Update Pinecone index dim

If user already created Pinecone index at dim 1536 → must delete + re-create.
If user followed updated `provisioning.md` §5 (dim 1024) → already correct, skip to 7.2.

```bash
# in Pinecone console: delete `alpha-whale` index → create new at dim 1024 cosine us-east-1
```

### Step 7.2: Re-run ingestion pipeline

```bash
uv run python -m ingestion.rag.run_pipeline  # or whatever the CLI entrypoint is
```

> If no CLI entrypoint exists, write a one-shot script in `scripts/reindex.py` that reads documents and calls `index_nodes(...)`.

**Success:** Pinecone index `alpha-whale` shows expected vector count; retrieval test returns relevant docs.

---

## Phase 8 — Deploy

1. Sync new `.env` to Lightsail (5 new AWS vars, removed `OPENAI_API_KEY`)
2. `docker compose pull && docker compose up -d`
3. Hit `/health` → green
4. Test chat endpoint with real query → response uses Claude, traces appear in LangSmith with model name `bedrock/...`

---

## Success criteria

**Automated:**
- [ ] `uv run pytest` — all green
- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] `uv run mypy agent api core ingestion`
- [ ] `aws bedrock list-foundation-models --region eu-west-2` shows access to chosen models

**Manual:**
- [ ] Local chat smoke (Phase 6.1) returns sane response
- [ ] Local embedding smoke (Phase 6.2) prints `dim=1024`
- [ ] Local extraction smoke (Phase 6.3) returns valid Pydantic model
- [ ] Pinecone retrieval returns at least 1 hit on a known query
- [ ] LangSmith trace shows Bedrock model used
- [ ] AWS billing dashboard shows Bedrock charges (consuming credit, not cash)

---

## Rollback

If Bedrock proves unreliable (e.g., model-access loss, region outage):
1. Revert `pyproject.toml` deps
2. Revert files in Phase 2-4
3. Restore `OPENAI_API_KEY` in `.env`
4. Re-create Pinecone index at dim 1536
5. Re-run ingestion

Keep migration commits atomic per phase to enable per-phase revert.

---

## Open questions

1. Use `anthropic.claude-3-5-haiku-20241022-v1:0` (eu-west-2 native) **or** Claude Haiku 4.5 via cross-region inference profile? — Default to 3.5 Haiku for cost + latency; revisit if quality lacking.
2. Add `boto3-stubs[bedrock-runtime]` for mypy? — yes, dev-only dep.
3. Cache Bedrock client (singleton) similar to current `_client` pattern? — yes, boto3 clients are thread-safe to share.
