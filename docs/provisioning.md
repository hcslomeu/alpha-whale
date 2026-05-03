# Provisioning runbook

Step-by-step setup of every external service alpha-whale depends on. Run sections in the suggested order to keep dependencies satisfied as you go.

Companion to [`deploy.md`](deploy.md) — that doc covers the deploy pipeline; this doc covers what to provision *before* the first deploy.

## Service map

| # | Service       | Tier     | Purpose                              |
|---|---------------|----------|--------------------------------------|
| 1 | AWS Lightsail | $5/mo    | Backend host (Docker + Caddy)        |
| 2 | Vercel        | Free     | Frontend host (Next.js)              |
| 3 | Supabase      | Free     | Postgres (LangGraph checkpoints)     |
| 4 | Pinecone      | Free     | Vector store (RAG)                   |
| 5 | AWS Bedrock   | pay-as-go (AWS credits) | LLM (Claude) + embeddings (Titan v2) |
| 6 | Cohere        | Free     | RAG reranking                        |
| 7 | Firecrawl     | Free     | News article scraping                |
| 8 | LangSmith     | Free     | Agent tracing                        |
| 9 | Logfire       | Free     | Backend observability                |
| 10| Upstash Redis | Free     | Market-data cache                    |
| 11| GitHub repo   | —        | Secrets for `deploy.yml`             |
| 12| Domain (DNS)  | $10-15/yr| Custom URL (deferrable)              |

---

## 1. AWS Lightsail

**Prereqs:** AWS account + payment method on file. Free tier doesn't cover Lightsail $5 plan — billed from day 1 (prorated daily).

### Steps

1. Sign in → https://lightsail.aws.amazon.com
2. **Region selector (top-right):** `London, eu-west-2`
3. Click **Create instance**
4. Configure:
   - **Instance location:** `London, Zone A (eu-west-2a)`
   - **Pick instance image:**
     - Platform: `Linux/Unix`
     - Blueprint: `OS Only` → `Ubuntu 24.04 LTS`
   - **SSH key pair:**
     - Click `Change SSH key pair`
     - Click `Create new` → name: `alpha-whale`
     - Click `Generate key pair` → **download `.pem` file immediately** (only chance to get private key)
     - Save to: `~/.ssh/alpha-whale-lightsail.pem`
     - Run locally: `chmod 600 ~/.ssh/alpha-whale-lightsail.pem`
   - **Choose instance plan:** `$5 USD / month · 1 GB RAM · 2 vCPUs · 40 GB SSD · 2 TB transfer`
   - **Identify your instance:** name = `alpha-whale-prod`
5. Click **Create instance** (takes ~60s)
6. **Static IP** (critical — instance IP changes on stop/restart otherwise):
   - Lightsail console → **Networking** tab (top nav)
   - Click **Create static IP**
   - Region: `eu-west-2`
   - Attach to: `alpha-whale-prod`
   - Name: `alpha-whale-ip`
   - Click **Create**
   - Note the IP (e.g. `18.135.xxx.xxx`) → this is `LIGHTSAIL_HOST`
7. **Open firewall ports:**
   - Click instance `alpha-whale-prod` → **Networking** tab
   - Under **IPv4 Firewall** → click **Add rule** for each:
     - SSH (TCP 22) — already exists
     - HTTP (TCP 80)
     - HTTPS (TCP 443)
     - Custom (UDP 443) — HTTP/3
   - Save

### Outputs

- `LIGHTSAIL_HOST` = static IP
- `~/.ssh/alpha-whale-lightsail.pem` with `chmod 600`

---

## 2. Lightsail SSH hardening + Docker install

**Prereqs:** §1 done.

### Steps

From local terminal:

```bash
ssh -i ~/.ssh/alpha-whale-lightsail.pem ubuntu@<LIGHTSAIL_HOST>
```

(Accept fingerprint with `yes`.)

**On the Lightsail box, run these blocks one at a time:**

Block 1 — system update + security tools:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ufw fail2ban
```

Block 2 — firewall (defense-in-depth on top of Lightsail console firewall):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw --force enable
sudo systemctl enable --now fail2ban
```

Block 3 — Docker + Compose plugin:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
```

Block 4 — apply group change (logout + back in):

```bash
exit
```

Then re-SSH:

```bash
ssh -i ~/.ssh/alpha-whale-lightsail.pem ubuntu@<LIGHTSAIL_HOST>
```

Block 5 — verify Docker:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

Block 6 — create app dir:

```bash
sudo mkdir -p /opt/alpha-whale
sudo chown ubuntu:ubuntu /opt/alpha-whale
```

### Outputs

- Confirmation `docker --version` + `docker compose version` print
- `hello-world` container ran clean

---

## 3. Vercel (frontend)

**Prereqs:** GitHub account linked, repo `hcslomeu/alpha-whale` exists.

### Steps

1. https://vercel.com/signup → **Continue with GitHub**
2. Authorize Vercel for your GitHub user/org
3. **Add New** (top-right) → **Project**
4. **Import Git Repository** → find `hcslomeu/alpha-whale` → **Import**
5. Configure project:
   - **Framework Preset:** Next.js (auto-detected)
   - **Root Directory:** click **Edit** → enter `web` → **Continue**
   - **Build settings:** leave defaults
   - **Environment Variables:** skip for now (will add `NEXT_PUBLIC_API_URL` after Lightsail deploy)
6. Click **Deploy** → ~2 min build
7. Note deployment URL: `alpha-whale-<hash>.vercel.app`

### Outputs

- Vercel project URL

---

## 4. Supabase

**Prereqs:** Free tier sufficient (500 MB DB + 2 GB bandwidth).

### Steps

1. https://supabase.com/dashboard → sign up with GitHub
2. **New project**:
   - Org: personal
   - Name: `alpha-whale`
   - Database password: generate strong → **save in 1Password/keychain**
   - Region: `West EU (London)` (closest to Lightsail eu-west-2)
   - Pricing plan: Free
3. Wait ~2 min for provisioning
4. **Project Settings** (gear icon, bottom-left) → **API**
5. Copy:
   - **Project URL** → `https://<project-ref>.supabase.co` = `SUPABASE_URL`
   - **service_role key** (under "Project API keys" → reveal `secret`) = `SUPABASE_SERVICE_ROLE_KEY`

> ⚠️ `service_role` key bypasses RLS. **Server-only**. Never expose to frontend.

**LangGraph checkpoint table** — agent code creates it auto on first run via `AsyncPostgresSaver.setup()`. No manual SQL needed.

### Outputs

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

---

## 5. Pinecone

**Prereqs:** Free tier = 1 serverless index, sufficient for portfolio scale.

### Steps

1. https://app.pinecone.io → sign up
2. **Create index**:
   - Name: `alpha-whale`
   - **Dimensions: `1024`** (matches Bedrock Titan v2 / Cohere embed v3 default — see §6)
   - **Metric: `cosine`**
   - **Capacity mode: Serverless**
   - **Cloud:** AWS
   - **Region:** `us-east-1` (only free-tier serverless option as of writing)
3. Click **Create index** → ready in ~30s
4. **API Keys** (left sidebar) → copy:
   - Default key = `PINECONE_API_KEY`
5. **Environment** value: with serverless not strictly needed; use `us-east-1-aws` or remove from `.env` if code allows

> **Latency note:** Lightsail in eu-west-2 → Pinecone in us-east-1 = ~80ms cross-region per query. Acceptable for chat (LLM latency dominates at 500ms+). Upgrade to paid tier later for region match if needed.

### Outputs

- `PINECONE_API_KEY`
- Index name = `alpha-whale`
- Dim = 1024

---

## 6. AWS Bedrock

**Why Bedrock over OpenAI direct:** AWS credits apply directly (one bill, one budget). Same AWS account as Lightsail = unified IAM + observability. Eu-west-2 region = co-located with Lightsail = ~0ms latency for embeddings + chat.

**Models chosen:**
- **Chat:** `anthropic.claude-3-5-haiku-20241022-v1:0` (native eu-west-2, function-calling reliable). Optional upgrade: Claude Haiku 4.5 via **cross-region inference profile** if higher quality needed.
- **Embeddings:** `amazon.titan-embed-text-v2:0` (native eu-west-2, dim 1024, $0.02 / Mtok). Cohere v3 alternative not available eu-west-2.

### Steps

#### 6.1 Create IAM user (programmatic access)

1. Sign in AWS console → **IAM** → **Users** → **Create user**
2. User name: `alpha-whale-prod`
3. Access type: **leave "Provide user access to AWS Management Console" UNCHECKED** (programmatic only)
4. Click **Next** → **Permissions options** → **Attach policies directly**
5. Search + attach: **`AmazonBedrockFullAccess`** (managed policy)
   - Tighten later to inline policy scoped to specific model ARNs once stable.
6. **Next** → **Create user**
7. Click the new user → **Security credentials** tab → **Create access key**
8. Use case: **Application running outside AWS** (Lightsail counts as this) → **Next**
9. (Optional tag) → **Create access key**
10. **Download .csv** OR copy:
    - **Access key ID** → `AWS_ACCESS_KEY_ID`
    - **Secret access key** → `AWS_SECRET_ACCESS_KEY` (only shown once)

> ⚠️ Store both in 1Password/keychain immediately. Secret cannot be re-fetched.

#### 6.2 Request Bedrock model access

Bedrock requires per-model access approval, even within your own account.

1. Switch region to **`eu-west-2` (London)** (top-right region selector)
2. Open **Amazon Bedrock** → left sidebar → **Model access** (under "Bedrock configurations")
3. Click **Modify model access** (or **Manage model access** depending on console version)
4. Check the boxes for:
   - **Anthropic — Claude 3.5 Haiku** (`anthropic.claude-3-5-haiku-20241022-v1:0`)
   - **Amazon — Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`)
5. **Next** → fill use-case form (Anthropic requires it):
   - Company: personal / portfolio
   - Use case: "AI engineering portfolio project — financial news Q&A agent"
   - Approve → **Submit**
6. Wait for status → **Access granted** (Anthropic models: usually <5 min, sometimes hours; Titan: instant)

> If Claude Haiku 4.5 desired: enable **cross-region inference profile** by also requesting access to `us.anthropic.claude-haiku-4-5-*` and using the inference profile ID in code instead of the model ID.

#### 6.3 Verify from local terminal (sanity check)

```bash
# install AWS CLI if missing
brew install awscli

aws configure --profile alpha-whale
# paste AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
# default region: eu-west-2
# default output: json

aws bedrock list-foundation-models \
  --region eu-west-2 \
  --profile alpha-whale \
  --query 'modelSummaries[?contains(modelId, `claude-3-5-haiku`) || contains(modelId, `titan-embed-text-v2`)].[modelId,modelLifecycle.status]' \
  --output table
```

Expect both rows showing `ACTIVE`.

#### 6.4 Cost guardrail (recommended)

1. AWS Console → **Billing** → **Budgets** → **Create budget**
2. Type: **Cost budget** → monthly: $50
3. Filter: **Service = Amazon Bedrock**
4. Alert at 80% + 100% → email yourself
5. (Stops surprise burn through your credits.)

### Outputs

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION=eu-west-2`
- `BEDROCK_CHAT_MODEL=anthropic.claude-3-5-haiku-20241022-v1:0`
- `BEDROCK_EMBED_MODEL=amazon.titan-embed-text-v2:0`
- Confirmed model access for both

---

## 7-9. AI service keys

Each is a quick API-key grab.

| Service       | URL                                                | What to grab                                  |
|---------------|----------------------------------------------------|-----------------------------------------------|
| **Cohere**    | https://dashboard.cohere.com/api-keys              | `COHERE_API_KEY` (free trial = 1000 calls/mo) — used for **reranking only**, embeddings come from Bedrock |
| **Firecrawl** | https://www.firecrawl.dev/app/api-keys             | `FIRECRAWL_API_KEY` (free = 500 pages/mo)     |
| **LangSmith** | https://smith.langchain.com/o/<org>/settings       | `LANGSMITH_API_KEY` (free dev = 5k traces/mo) |
| **Logfire**   | https://logfire.pydantic.dev → New project `alpha-whale` | `LOGFIRE_TOKEN` (Settings → Write Tokens) |

### Outputs

All 4 keys.

---

## 10. Redis — Upstash

**Why Upstash over self-hosted:** managed, free tier 10k commands/day, no Lightsail RAM consumed (1 GB box already tight with API + Caddy).

### Steps

1. https://console.upstash.com → sign up with GitHub
2. **Create database**:
   - Name: `alpha-whale`
   - Type: `Regional`
   - Region: `eu-west-1` (Ireland — closest to Lightsail London)
   - Eviction: `noeviction`
3. Once created → **Details** tab
4. Copy **Redis URL** under "TLS/SSL" tab → format: `rediss://default:<token>@<host>:<port>`

### Outputs

- `REDIS_URL`

---

## 11. GitHub repo secrets

**Prereqs:** §1-2 complete (need static IP + SSH key).

### Steps

1. https://github.com/hcslomeu/alpha-whale/settings/secrets/actions
2. Click **New repository secret** for each:

| Name                | Value                                                                                    |
|---------------------|------------------------------------------------------------------------------------------|
| `LIGHTSAIL_SSH_KEY` | **full contents** of `~/.ssh/alpha-whale-lightsail.pem` (open in editor, copy entire file including `-----BEGIN/END-----` lines) |
| `LIGHTSAIL_HOST`    | static IP from §1                                                                        |

### Outputs

- Confirmation both secrets added.

---

## 12. Domain (deferrable)

**Why skip now:** Vercel `.vercel.app` URL + Lightsail IP work fine for portfolio demo. Custom domain = $10-15/yr ongoing cost.

### When ready

1. Pick registrar (Cloudflare cheapest — at-cost pricing, no upsell)
2. Buy domain
3. DNS records:

| Record           | Type  | Value                          |
|------------------|-------|--------------------------------|
| `api.<domain>`   | A     | Lightsail static IP            |
| `@` (apex)       | CNAME | `cname.vercel-dns.com`         |
| `www`            | CNAME | `cname.vercel-dns.com`         |

4. SSH into Lightsail:

```bash
ssh ubuntu@<LIGHTSAIL_HOST>
cd /opt/alpha-whale
echo "DOMAIN=api.<domain>" >> .env
docker compose up -d --force-recreate caddy
```

Caddy auto-fetches Let's Encrypt cert on first request to `https://api.<domain>/health`.

### Outputs

- Chosen domain.

---

## Suggested execution order

| Day | Tasks                                                                  | Time    |
|-----|------------------------------------------------------------------------|---------|
| 1   | §1 Lightsail + §2 SSH/Docker + §6 AWS Bedrock (IAM + model access)    | ~50 min |
| 2   | §4 Supabase + §5 Pinecone (dim 1024) + §10 Upstash + §7-9 keys        | ~20 min |
| 3   | Code migration (WP-Bedrock spec) + first manual deploy                 | ~varies |
| 4   | §11 GitHub secrets + §3 Vercel — auto-deploy live                     | ~10 min |
| 5+  | §12 domain when picked                                                 | —       |

## Final `.env` template

After all sections complete, the Lightsail `/opt/alpha-whale/.env` should look like:

```bash
DOMAIN=                                        # empty until §12

# AWS Bedrock (replaces OpenAI API)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=eu-west-2
BEDROCK_CHAT_MODEL=anthropic.claude-3-5-haiku-20241022-v1:0
BEDROCK_EMBED_MODEL=amazon.titan-embed-text-v2:0

# Vector + cache
PINECONE_API_KEY=...
PINECONE_ENVIRONMENT=us-east-1-aws
PINECONE_INDEX=alpha-whale
REDIS_URL=rediss://default:...@...upstash.io:6379

# Postgres (LangGraph checkpoints)
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...

# Tools
COHERE_API_KEY=...
FIRECRAWL_API_KEY=...

# Observability
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=alpha-whale
LOGFIRE_TOKEN=...
```

Permissions: `chmod 600 .env`. Never commit.
