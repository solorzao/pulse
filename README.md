# Pulse

Pulse is a globe that shows how people in each region feel about a topic. It builds the view from social posts (text, images and video) and adds an agent you can ask "why does Ireland hate AI datacenters?" and get a cited answer. A topic is scored per region from enriched posts (sentiment, narrative and location) and shown as a diverging heatmap. You can open any region to see its narratives, top posts and trend, or follow how a meme spreads across the world. The MVP runs on mock data, and real sources plug in behind the same interface later.

## Architecture

```
                    ┌──────────────────────────┐
  browser ────────► │  Vercel: Next.js (web/)  │
     │              │  react-globe.gl UI       │
     │              └──────────────────────────┘
     │  fetch NEXT_PUBLIC_API_URL
     ▼
  ┌───────────────────────────────────────────┐        ┌───────────────┐
  │ Azure Container Apps: pulse-api (api/)    │ ─────► │ Anthropic API │
  │ FastAPI + in-memory DuckDB + agent loop   │        │ (agent /ask)  │
  │ seed/ baked into the image                │        └───────────────┘
  └───────────────────────────────────────────┘
        ▲ image pulled via managed identity
  ┌───────────────┐      az acr build      ┌──────────────────────────┐
  │ ACR pulse-api │ ◄───────────────────── │ GitHub Actions (OIDC)    │
  └───────────────┘                        │ api.yml on push to main  │
                                           └──────────────────────────┘
```

## Local dev

```bash
# 1. Seed data (already committed in seed/; regenerate only if needed)
python scripts/generate_seed.py
python scripts/mock_enrich.py          # or: ANTHROPIC_API_KEY=... python scripts/enrich.py

# 2. API -> http://localhost:8000
cd api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...    # optional: without it, /ask returns a deterministic answer
uvicorn app.main:app --reload --port 8000

# 3. Web -> http://localhost:3000 (new terminal)
cd web && npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Deploy (run in this order)

You need `az`, `gh` and `git`, and you must be logged in (`az login`, `gh auth login`). Docker is not needed because images build in ACR.

**1. GitHub repo**
```bash
git init -b main 2>/dev/null; git add -A && git commit -m "Pulse MVP"
gh repo create pulse --private --source=. --remote=origin --push
```

**2. Azure backend** (creates RG `pulse-rg`, ACR, Container Apps env `pulse-env` and app `pulse-api`, then prints the FQDN)
```bash
export ANTHROPIC_API_KEY=sk-ant-...
./infra/deploy-azure.sh                 # optional overrides: LOCATION=eastus ACR_NAME=myuniqueacr
```

**3. GitHub Actions to Azure (OIDC, no stored passwords)**
```bash
./infra/setup-github-oidc.sh <owner>/pulse
# then paste the 6 printed `gh secret set` / `gh variable set` lines
```
After this, every push to `main` that touches `api/**` or `seed/**` rebuilds the image, rolls out the new image and checks `/health`. You can also run it by hand with `gh workflow run "Deploy API"`.

**4. Vercel frontend**: at vercel.com/new, import the GitHub repo and set:
- Root Directory: `web` (Framework: Next.js is auto-detected)
- Environment variable: `NEXT_PUBLIC_API_URL=https://<fqdn-from-step-2>`

Then deploy. Pushes to `main` redeploy automatically, and PRs get preview URLs.

**5. CORS**: the API already allows `localhost` and `*.vercel.app`. If you use a custom domain, or just want to pin the origin, run:
```bash
az containerapp update -n pulse-api -g pulse-rg \
  --set-env-vars CORS_ORIGINS=https://<your-app>.vercel.app
```

## Costs and teardown

- `min-replicas 1` keeps one 0.5 vCPU / 1 GiB replica warm so the demo never cold-starts. That costs a few dollars per day. ACR Basic is about $5 per month.
- After the hackathon, scale to zero (you then pay only for requests, and the first request takes a few seconds):
  ```bash
  az containerapp update -n pulse-api -g pulse-rg --min-replicas 0
  ```
- To delete everything:
  ```bash
  az group delete -n pulse-rg --yes --no-wait
  az ad app delete --id "$(az ad app list --display-name pulse-github-actions --query '[0].appId' -o tsv)"
  ```
