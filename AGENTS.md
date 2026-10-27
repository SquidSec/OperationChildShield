# Agent notes (OperationChildShield)

## Deployment files are sensitive — do not commit

This is a **public repository**. Production deployment artifacts must stay local and gitignored.

### Gitignored (never add to version control)

| Path | Purpose |
|------|---------|
| `scripts/deploy-prod.sh` | Main production deploy (copy from `deploy-prod.example.sh`) |
| `scripts/deploy-now.sh` | Fast deploy variant (skips bill verification) |
| `scripts/deploy_paramiko.py` | Tarball + Paramiko SSH deploy helper |
| `scripts/deploy-*.sh` | Any other deploy shell scripts (except `*.example.sh`) |
| `docker-compose.prod.yml` | Production Compose stack (copy from `docker-compose.prod.example.yml`) |
| `Caddyfile` | Production reverse proxy (copy from `Caddyfile.example`) |
| `deploy.env` | Deploy-specific environment overrides |
| `.env` / `.env.*` | API keys, SSH passwords, Stripe secrets |

### Safe to commit (templates only)

- `scripts/deploy-prod.example.sh`
- `docker-compose.prod.example.yml`
- `Caddyfile.example`
- `.env.example`

### When working on deployment

1. Edit **local gitignored copies**, not the example files (unless improving the template).
2. Never paste server IPs, SSH users, passwords, or API keys into tracked files or chat logs in commits.
3. If a deploy script was accidentally staged, `git rm --cached <file>` and confirm `.gitignore` covers it.
4. Roadmap and feature priorities live in `README.md` → **Development roadmap**.

### Current production direction

Migrate from the MVP Docker setup to a hardened dedicated production server (Docker Compose + Caddy). See README roadmap Phase 1, item 3.

## Local work: do not fetch external data

When running the app locally to check UI, routes, auth, or layout, **do not pull data from Congress.gov** (or any other external API) unless the task specifically requires verifying that integration.

- Start the backend with `SKIP_BILL_VERIFICATION=1` and avoid endpoints that trigger a live fetch (`/api/members`, `/api/metrics`, report cards) when they are not the thing under test.
- Prefer the existing cached JSON under `data/`. Do not delete or re-fetch it to "make sure."
- Use synthetic local data (for example `POST /api/analytics/event` for traffic) when a screen needs rows.
- Browser checks should exercise the feature under test and stop there. Do not crawl every public page, which triggers Congress.gov calls and burns the shared API rate limit.
