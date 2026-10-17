# Handoff: deploy Pulse (for a local Claude Code session)

Context: Pulse is a hackathon MVP. Read `CONTRACT.md` (data formats, API, demo stories) and `README.md` first.

## Status (2026-10-17)
- Done and verified in a cloud session: `seed/` (2,782 mock posts, 44 regions, 3 topics), `api/` (FastAPI + DuckDB + Claude agent with a no-key fallback; 18 tests pass), `web/` (Next.js + react-globe.gl; builds, lints, and was checked end to end against the API), `infra/`, and `.github/workflows/`.
- NOT done: the Azure deploy. The cloud sandbox can't reach Azure, so the deploy has to run here, where `az` is logged in.
- A deploy attempt may have been started from `C:\Users\olive\source\repos\deploy-pulse.cmd`. Check its log at `C:\Users\olive\source\repos\pulse-deploy.log` and the state of resource group `pulse-rg` before starting again. The script is idempotent, so re-running it is safe.

## Next steps
1. Deploy the API (Windows PowerShell):
   `$env:ANTHROPIC_API_KEY = "sk-ant-..."` (optional), then
   `powershell -ExecutionPolicy Bypass -File infra\deploy-azure.ps1`
   Bash/WSL alternative: `./infra/deploy-azure.sh`. The PowerShell script has never been run all the way through before, so fix it if it breaks.
2. Check `https://<fqdn>/health`, which should return `{"ok":true,"posts":2782}`.
3. Set up CI: `./infra/setup-github-oidc.sh solorzao/pulse` (needs bash, e.g. Git Bash), then run the printed `gh secret/variable set` commands.
4. Vercel: import `solorzao/pulse` with Root Directory `web` and env `NEXT_PUBLIC_API_URL=https://<fqdn>`.
5. Optional: `az containerapp update -n pulse-api -g pulse-rg --set-env-vars CORS_ORIGINS=https://<app>.vercel.app` (`*.vercel.app` is already allowed).
6. After the hackathon: `az containerapp update -n pulse-api -g pulse-rg --min-replicas 0`, or `az group delete -n pulse-rg --yes`.

## Known gaps
- The no-key fallback answers in `/ask` read mechanically. Set `ANTHROPIC_API_KEY` on the container app before the demo.
- `scripts/enrich.py` (real Claude enrichment) has not been run against the API yet.
- Media tiles in the web app are placeholders (seed media URLs are null).
