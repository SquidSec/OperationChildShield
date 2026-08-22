# Deploy: GitHub Actions → DigitalOcean

## Production droplet (reference)

Keep host-specific values in **private** ops notes or GitHub Environment secrets — do not commit live IPs, SSH users, or key material to this public repo.

| Field | Guidance |
|-------|----------|
| Name | e.g. `operation-child-shield-prod` |
| Size | `s-2vcpu-4gb` class (or larger) |
| App path | `/opt/operationchildshield` (or set `DEPLOY_PATH`) |
| SSH | Prefer a non-root deploy user with Docker group + limited sudo; root works but raises blast radius |
| SSH key | Private key only in GitHub Environment secrets and local `~/.ssh/` (never committed) |

Site (HTTPS + Let's Encrypt): https://operationchildshield.org and https://www.operationchildshield.org

## What you must add in GitHub

Deploy job uses `environment: prod`. Secrets must be available to that environment (Environment secrets for **prod**, or repository secrets if you change the workflow).

Path:

1. Repo → **Settings** → **Environments** → **prod** (or **Secrets and variables** → **Actions**)
2. Add secrets (values never committed):

| Secret name | Value |
|-------------|--------|
| `DEPLOY_HOST` | Droplet public IP or hostname |
| `DEPLOY_USER` | SSH user (prefer non-root deploy user) |
| `DEPLOY_SSH_KEY` | Full private key PEM (including BEGIN/END lines), **or** use `DEPLOY_SSH_KEY_B64` instead |
| `DEPLOY_SSH_KEY_B64` | Preferred: single-line base64 of the private key (avoids multiline paste issues) |
| `DEPLOY_PATH` | e.g. `/opt/operationchildshield` |
| `PUBLIC_SITE_URL` | `https://operationchildshield.org` |

### Preferred: base64 SSH key

On the machine that has the deploy private key:

```bash
base64 -w0 ~/.ssh/YOUR_DEPLOY_KEY
echo   # newline for your terminal only; do not include trailing newline in the secret if your paste tool adds one
```

Paste the single line into secret `DEPLOY_SSH_KEY_B64`.

### Alternative: raw PEM

```bash
cat ~/.ssh/YOUR_DEPLOY_KEY
```

Paste the entire output into `DEPLOY_SSH_KEY`. Do **not** commit this file.

### If Actions still says Missing secret

Check the deploy job log secret-presence lines. If host/user/key are EMPTY, secrets are not injected — wrong environment, Variables instead of Secrets, or wrong repo. Re-create under the environment the workflow uses, then re-run.

## How deploy works

1. Push/merge to **`main`**
2. Workflow **Build and deploy** (`.github/workflows/deploy.yml`):
   - Runs backend + frontend tests
   - Builds Docker images and pushes to GHCR:
      - `ghcr.io/squidsec/operationchildshield-backend:main`
      - `ghcr.io/squidsec/operationchildshield-frontend:main`
   - SSHs to the droplet, pulls images, restarts Compose
3. Smoke-checks `/api/health`

First successful deploy job also requires GHCR package write via `GITHUB_TOKEN` (workflow already has `packages: write`). After the first image push, open the package on GitHub and set visibility to **Public** if the droplet cannot pull anonymously.

## DNS cutover (when ready)

1. Point `operationchildshield.org` A record to the droplet
2. Replace server `Caddyfile` with domain-based config (see `Caddyfile.example`)
3. Update secret `PUBLIC_SITE_URL` to `https://operationchildshield.org`
4. Update server `.env` `CORS_ORIGINS` / `NEXT_PUBLIC_API_URL`
5. Rebuild frontend image (so `NEXT_PUBLIC_API_URL` is baked correctly) and redeploy

## Security headers & proxy hardening (Caddy)

Production `Caddyfile.example` sets baseline browser security headers on both apex and `www`:

| Header | Purpose |
|--------|---------|
| `Strict-Transport-Security` | HSTS — force HTTPS for 1 year (+ subdomains) |
| `X-Frame-Options` | Deny framing (clickjacking) |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` / `Permissions-Policy` | Extra hardening |
| `Cross-Origin-Opener-Policy` | `same-origin` — isolate top-level browsing context |
| `Cross-Origin-Resource-Policy` | `same-origin` — block cross-site embedding of our resources |
| `Cross-Origin-Embedder-Policy` | `credentialless` — isolation without breaking congress.gov images |

**Content-Security-Policy** is set by the Next.js app (`frontend/src/proxy.ts`) with **per-request nonces** — no `script-src 'unsafe-inline'` / `'unsafe-eval'` in production. Do **not** re-declare CSP in Caddy (a second policy would defeat nonces and reintroduce scanner findings).

Also:

- Strips `Server` and `X-Powered-By` from responses
- Overwrites `X-Real-IP` / `X-Forwarded-For` with the real peer (blocks client XFF spoofing used against app rate limits)

After updating the server `Caddyfile`, reload Caddy (and redeploy the frontend image so proxy CSP is live):

```bash
ssh -i ~/.ssh/YOUR_DEPLOY_KEY USER@HOST
cd /opt/operationchildshield
docker compose -f docker-compose.prod.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
# verify:
curl -sI https://operationchildshield.org/ | grep -iE 'strict-transport|content-security|x-frame|x-content-type|cross-origin'
```

## Backend security notes

- Backend image runs as non-root (`uid 1001`). Ensure the Docker volume for `/app/data` is writable by that user (`chown -R 1001:1001` on the volume mount if needed).
- Set `ENV=production` / `DISABLE_API_DOCS=1` (compose templates do this) so OpenAPI UI is disabled.
- Congress.gov key is sent as `X-Api-Key` header (not query string). API errors never echo upstream exception URLs.
- After any historical key exposure, **rotate** `CONGRESS_API_KEY` at https://api.congress.gov/sign-up/ and update server `.env`.

## Manual commands on the droplet

```bash
ssh -i ~/.ssh/YOUR_DEPLOY_KEY USER@HOST
cd /opt/operationchildshield
docker compose -f docker-compose.prod.ghcr.yml ps
curl -s http://127.0.0.1/api/health
```
