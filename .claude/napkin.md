# Napkin Runbook

## Curation Rules
- Re-prioritize on every read.
- Keep recurring, high-value notes only.
- Max 10 items per category.
- Each item includes date + "Do instead".

## Execution & Validation (Highest Priority)

1. **[2026-05-03] Pinecone dim must match embedding model — pick model BEFORE creating index**
   Do instead: confirm embedding provider + model first (OpenAI 1536, Bedrock Titan v2 = 1024, Cohere v3 = 1024). Recreating Pinecone forces full re-ingest.

2. **[2026-05-03] Pre-push verification gate is non-negotiable**
   Do instead: run `uv run ruff check . && uv run ruff format --check . && uv run mypy agent api core ingestion && uv run pytest` before any push or PR. All four must pass.

3. **[2026-05-03] Bedrock model access is per-account + per-model + per-region**
   Do instead: when adding a new Bedrock model, request access in console first (Anthropic gated, Titan instant), then verify via `aws bedrock list-foundation-models --region <r> --query "modelSummaries[?modelId=='<id>'].modelLifecycle.status"` showing ACTIVE.

## Shell & Command Reliability

1. **[2026-05-03] zsh chokes on visually-wrapped multi-line commands**
   Do instead: use `\` continuations for long commands, or keep on a single line. Long heredocs in `gh pr create` cause `dquote cmdsubst heredoc>` — use single double-quoted string with real newlines instead.

2. **[2026-05-03] Xcode license blocks `git` via Apple-shim binary**
   Do instead: if `git` returns "You have not agreed to the Xcode license", run `sudo xcodebuild -license` once. Affects every Bash session until resolved.

## Domain Behavior Guardrails

1. **[2026-05-03] Instructor + Bedrock uses Anthropic-style API**
   Do instead: call `client.messages.create(...)` (NOT `client.chat.completions.create(...)`). Always pass `max_tokens`. Different from Instructor + OpenAI.

2. **[2026-05-03] LangChain return-type strictness**
   Do instead: type `.bind_tools()` return as `Runnable`, not `ChatOpenAI`/`ChatBedrockConverse`. Type `response.tool_calls` items as `ToolCall` from `langchain_core.messages.tool`. Narrow `last_message` to `AIMessage` via `isinstance` before reading `.tool_calls` in LangGraph routers.

3. **[2026-05-03] Pydantic SecretStr for all API keys**
   Do instead: declare keys as `SecretStr` in pydantic-settings models, access via `.get_secret_value()`. Prevents leaks in logs/repr.

## User Directives

1. **[2026-05-03] Conventional Commits, NO Co-Authored-By lines**
   Do instead: use `feat(scope): ...` / `fix(scope): ...` / `docs: ...` / `chore: ...`. Developer is sole author.

2. **[2026-05-03] Provide git commands as text by default**
   Do instead: write the exact command in a code block for the user to copy. Run only when user explicitly says "run it" / "go ahead and push" / similar.

3. **[2026-05-03] Push only after explicit user OK**
   Do instead: never push automatically. Stop after commit, surface the push command, wait.

4. **[2026-05-03] Caveman mode is sticky across the session**
   Do instead: once user invokes `/caveman lite|full`, drop articles/filler/pleasantries/hedging in chat for every subsequent reply until user says "stop caveman" or "normal mode". Keep code/commits/security advisories written normally.

5. **[2026-05-03] User-language preference: pt-BR per memory, but verify**
   Do instead: memory says all chat in pt-BR. Recent sessions ran English. On first turn of a new session, match user's language. If unclear, ask once.
