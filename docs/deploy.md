# Deployment runbook

Plan B of the simplification migration. Manual steps only — no Terraform/IaC. One-time provisioning + ongoing deploys via GitHub Actions.

## Targets

| Layer    | Host             | Region      | Cost    |
|----------|------------------|-------------|---------|
| API      | AWS Lightsail    | eu-west-2   | $5/mo   |
| Frontend | Vercel           | auto-edge   | $0 (hobby) |
| DNS      | (TBD — Cloudflare or Route53 once domain chosen) | — | $0–1 |

## 1 — Provision Lightsail (one-time, ~20 min)

1. **Create instance**
   - AWS Console → Lightsail → Create instance
   - Region: `London, Zone A (eu-west-2a)`
   - Platform: Linux/Unix · Blueprint: OS Only · **Ubuntu 24.04 LTS**
   - Plan: **$5/mo · 1 GB RAM · 2 vCPU · 40 GB SSD · 2 TB transfer**
   - Name: `alpha-whale-prod`
   - SSH key: generate new (download + `chmod 600 ~/.ssh/alpha-whale-lightsail.pem`)
   - **Create static IP** → attach to instance (prevents IP churn on reboot)

2. **Networking**
   - Open ports in Lightsail firewall: **22 (SSH), 80 (HTTP), 443 (HTTPS + UDP/443 for HTTP/3)**

3. **First login + harden**

   ```bash
   ssh -i ~/.ssh/alpha-whale-lightsail.pem ubuntu@<STATIC_IP>
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y ufw fail2ban
   sudo ufw allow OpenSSH
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw allow 443/udp
   sudo ufw --force enable
   sudo systemctl enable --now fail2ban
   ```

4. **Install Docker + Compose plugin**

   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker ubuntu
   # re-login for group change
   docker --version && docker compose version
   ```

5. **Create app dir + env file**

   ```bash
   sudo mkdir -p /opt/alpha-whale
   sudo chown ubuntu:ubuntu /opt/alpha-whale
   cd /opt/alpha-whale
   # Upload .env (see template below) via scp from workstation
   chmod 600 .env
   ```

## 2 — First deploy (manual, before CI/CD)

From workstation:

```bash
cd ~/alpha-whale
# Build image on Lightsail (simpler than registry for first deploy)
rsync -avz --exclude=.git --exclude=node_modules --exclude=.venv --exclude=web \
  ./ ubuntu@<STATIC_IP>:/opt/alpha-whale/

ssh ubuntu@<STATIC_IP> "cd /opt/alpha-whale && docker compose up -d --build"
ssh ubuntu@<STATIC_IP> "docker compose ps"
```

Verify:

```bash
curl -k https://<STATIC_IP>/health    # expect 200 (cert warning until DNS + domain set)
ssh ubuntu@<STATIC_IP> "docker compose logs -f --tail=50"
```

## 3 — DNS + domain (deferred until domain picked)

When ready:

| Record | Type | Value            |
|--------|------|------------------|
| `api.<domain>` | A    | `<STATIC_IP>`     |
| `api.<domain>` | AAAA | `<IPv6 if set>`   |
| `@` (apex)  | CNAME → Vercel | — |
| `www`       | CNAME → Vercel | — |

On Lightsail:

```bash
ssh ubuntu@<STATIC_IP>
cd /opt/alpha-whale
# set DOMAIN var in .env
echo "DOMAIN=api.<domain>" >> .env
docker compose up -d --force-recreate caddy
```

Caddy auto-fetches Let's Encrypt cert on first request to `https://api.<domain>/health`.

## 4 — Vercel (frontend)

1. `vercel login` → link repo via GitHub integration
2. Project settings:
   - Root directory: `web`
   - Framework: Next.js (auto-detected)
   - Env vars: `NEXT_PUBLIC_API_URL=https://api.<domain>` (or Lightsail IP for initial testing)
3. Deploy on push to `main` — automatic.
4. Vercel placeholder URL: `alpha-whale-<hash>.vercel.app` works immediately without custom domain.

## 5 — CI/CD (Plan A + Plan B bridge)

`.github/workflows/ci.yml` runs on every push/PR:
- Python: ruff + mypy + pytest
- Frontend: `pnpm build`
- Docker: builds image (doesn't push yet)

`.github/workflows/deploy.yml` (TO ADD once first manual deploy works):
- Trigger: push to `main` (after CI passes)
- SSH into Lightsail using `LIGHTSAIL_SSH_KEY` secret
- `git pull` + `docker compose up -d --build`
- Healthcheck `curl https://api.<domain>/health`

Skeleton (not yet added):

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  workflow_run:
    workflows: [CI]
    branches: [main]
    types: [completed]
jobs:
  deploy:
    if: github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-latest
    steps:
      - uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.LIGHTSAIL_SSH_KEY }}
      - run: |
          ssh -o StrictHostKeyChecking=no ubuntu@${{ secrets.LIGHTSAIL_HOST }} <<'EOF'
            cd /opt/alpha-whale
            git pull
            docker compose up -d --build
            sleep 10
            curl -sf https://localhost/health || exit 1
          EOF
```

Secrets needed in GitHub repo settings:
- `LIGHTSAIL_SSH_KEY` — contents of `~/.ssh/alpha-whale-lightsail.pem`
- `LIGHTSAIL_HOST` — static IP (or hostname after DNS)

## 6 — Env vars

Template `.env` (on Lightsail only, never commit):

```bash
# Domain (empty = localhost on first deploy)
DOMAIN=

# OpenAI
OPENAI_API_KEY=sk-...

# Pinecone
PINECONE_API_KEY=...
PINECONE_ENVIRONMENT=...
PINECONE_INDEX=alpha-whale

# Cohere (rerank)
COHERE_API_KEY=...

# Firecrawl
FIRECRAWL_API_KEY=...

# Supabase
SUPABASE_URL=https://...supabase.co
SUPABASE_SERVICE_ROLE_KEY=...

# Redis (managed or local)
REDIS_URL=redis://localhost:6379/0

# LangSmith (optional)
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=alpha-whale

# Logfire (optional)
LOGFIRE_TOKEN=...
```

## 7 — Operations

| Task              | Command                                                      |
|-------------------|--------------------------------------------------------------|
| View logs         | `ssh ubuntu@<ip> 'docker compose logs -f --tail=100'`       |
| Restart API       | `ssh ubuntu@<ip> 'cd /opt/alpha-whale && docker compose restart api'` |
| Pull + redeploy   | `ssh ubuntu@<ip> 'cd /opt/alpha-whale && git pull && docker compose up -d --build'` |
| Disk usage        | `ssh ubuntu@<ip> 'df -h && docker system df'`                |
| Prune dead images | `ssh ubuntu@<ip> 'docker system prune -a --volumes'`         |
| Rotate SSH key    | Lightsail console → Snapshots → Instance → Manage SSH keys   |

## 8 — Rollback

```bash
ssh ubuntu@<STATIC_IP>
cd /opt/alpha-whale
git log --oneline -5
git checkout <previous-sha>
docker compose up -d --build
```

## Archive handoff

Old monorepo: https://github.com/hcslomeu/ai-engineering-monorepo — kept read-only with `pre-simplification-snapshot` tag marking the state before this migration.
