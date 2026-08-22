# Operation Child Shield

[![Backend unit tests](https://img.shields.io/github/actions/workflow/status/DotNetRussell/OperationChildShield/ci.yml?label=Backend%20unit%20tests&logo=pytest&logoColor=white)](https://github.com/DotNetRussell/OperationChildShield/actions/workflows/ci.yml)
[![Frontend unit tests](https://img.shields.io/github/actions/workflow/status/DotNetRussell/OperationChildShield/ci.yml?label=Frontend%20unit%20tests&logo=vitest&logoColor=white)](https://github.com/DotNetRussell/OperationChildShield/actions/workflows/ci.yml)
[![Security scan](https://img.shields.io/badge/SquidScanner-security%20scan-0ea5e9?logo=shieldsdotio&logoColor=white)](https://app.squidscanner.com/job/f80760c5-d4b7-4b9b-8524-1b435f64eed4)

A transparency platform that publishes **neutral child safety voting records** for U.S. lawmakers using public data from the [Congress.gov API](https://api.congress.gov/). Each recorded floor vote is shown with how the member voted and whether that vote is consistent with Operation Child Shield board-adopted policy positions. The site does **not** publish letter grades, rankings, or scorecards.

**Production:** [https://operationchildshield.org](https://operationchildshield.org)

### Security scan

| Resource | Link |
|----------|------|
| **Latest SquidScanner report** (operationchildshield.org) | [View full security report](https://app.squidscanner.com/job/f80760c5-d4b7-4b9b-8524-1b435f64eed4) |

Independent agentic recon + AI analysis of the production site (headers, surface, findings). Open the report for grades, issues, and remediation detail.

---

## What exists today

### Public pages

| Route | Description |
|-------|-------------|
| `/` | Member directory with search, party/state filters, lazy-loaded voting records, policy badges per vote, Yes/No pie charts, and infinite scroll |
| `/member/[bioguideId]` | Full voting record: vote breakdown, policy badges, summary stats, Yes/No pie chart, Congress.gov links, social share |
| `/bills` | 30 tracked bills in three sections: House roll-call (scored), floor action (tracked only), introduced |
| `/metrics` | Bill-level roll-call statistics, **state heat map**, state policy-consistency table, charts |
| `/states/[code]` | State overview: House policy-consistency KPIs and member list for that state |
| `/learn` | Education for people seeking help/clarity and people who want to take action |
| `/get-involved` | Signup form for volunteers, advocates, media, and partners |
| `/the-facts` | **The Facts** — neutral bill bullets with Congress.gov deep links |
| `/about` | Policy positions, methodology, and 501(c)(3) public-charity status (EIN not published) |
| `/board` | Board of directors (enabled via `ENABLE_BOARD_PAGE`) |
| `/disclaimer` | Legal disclaimer (entertainment purposes, public data sources, contact) |
| `/partners` | Partner organizations |
| `/directory` | Alternate member listing |

### Hidden pages (feature-flagged off)

These routes return **404** until enabled in [`frontend/src/lib/feature-flags.ts`](frontend/src/lib/feature-flags.ts):

| Route | Flag | Description |
|-------|------|-------------|
| `/donate` | `ENABLE_DONATE_PAGE` | Donation UI with suggested amounts (no payment processor wired yet) |

Set `ENABLE_DONATE_PAGE` to `true`, add nav links in `Header.tsx` / `Footer.tsx` if desired, and rebuild. The board page is already enabled (`ENABLE_BOARD_PAGE = true`) with nav links in the header and footer.

### Backend API

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Service health, congress session, API key configured |
| `GET /api/members` | Member directory (`search`, `chamber`, `state`, `party`, `limit`, `offset`) |
| `GET /api/members/{bioguideId}/report-card` | Member voting record (`key_votes`, `policy_consistent` per vote; no letter grades) |
| `GET /api/bills` | Tracked legislation with floor-status metadata |
| `GET /api/metrics` | Bill-level roll-call aggregates plus `byState` House policy-consistency totals (no grades/rankings) |
| `GET /api/metrics/export` | CSV export of per-bill roll-call summaries |
| `POST /api/involve` | Volunteer/advocate signup (JSON body; stored as JSONL under `CACHE_DIR`) |
| `POST /api/analytics/event` | Records a page view, or an allow-listed action (`share`, `contact_congress`), into server-side SQLite (`analytics.db`). Raw events are not exposed. |
| `GET /api/impact` | Aggregate counts only: page views, shares, Congress contacts started, and signups. |

Interactive API docs: `http://localhost:8000/docs` (local).

### Voting record & policy model (summary)

- **Only House roll-call votes** on verified bills produce per-member vote records with policy-consistency indicators.
- Senate members and voice-vote bills are tracked for context but do not produce individual House roll-call records (Congress.gov limitation).
- Each scored vote includes `vote_cast`, bill metadata, Congress.gov links, and `policy_consistent` (compared to board-adopted bill stances).
- **Pro-protection bills:** Aye aligns with OCS policy; Nay does not. **Anti-protection bills:** Nay aligns; Aye does not.
- Present and Not Voting are recorded factually and marked not consistent with policy where applicable.
- Letter grades, percentage scores, and member rankings are **computed internally for policy alignment only** and are **stripped from all public API responses**.
- Bills are verified against Congress.gov titles at backend startup.
- Responses use a **stale-while-revalidate** file cache (24-hour TTL by default): expired cache is served immediately while fresh data rebuilds in the background.

Full explanation: in-app `/about` page (Policy Positions).

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose (recommended), **or**
- Python 3.12+, Node.js 24+, npm
- A free **Congress.gov API key** (required for the backend)

---

## Get a Congress.gov API key

1. Go to **[https://api.congress.gov/sign-up/](https://api.congress.gov/sign-up/)**
2. Complete the sign-up form with your name and email.
3. Congress.gov will email you an API key (usually within minutes to one business day).
4. Copy the key into your `.env` file:

   ```bash
   CONGRESS_API_KEY=your_key_here
   ```

### API limits and usage

- Congress.gov publishes a rate limit of **5,000 requests per hour** per key (confirm current limits on their site).
- This app caches all Congress.gov responses on disk for 24 hours to minimize API usage.
- The heaviest operations are building member report cards and the metrics dashboard (first request after cache expiry). Steady-state traffic is mostly cache hits with background revalidation.
- **Never commit your API key.** Keep it only in `.env` (gitignored) or your deployment secrets.

### Verify your key works

```bash
curl "https://api.congress.gov/v3/member/congress/119?api_key=YOUR_KEY&format=json&limit=1"
```

You should receive JSON with a `members` array.

---

## Quick start (Docker)

```bash
git clone <repo-url> OperationChildShield
cd OperationChildShield

cp .env.example .env
# Edit .env — set CONGRESS_API_KEY

docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

---

## Local development (without Docker)

Use the helper script for backend + frontend together:

```bash
./scripts/dev-local.sh start    # start both services
./scripts/dev-local.sh status   # check PIDs / ports
./scripts/dev-local.sh stop     # stop both
./scripts/dev-local.sh restart  # restart both
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |

Logs: `data/backend-dev.log`, `data/frontend-dev.log`

### Backend (manual)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

export CONGRESS_API_KEY=your_key
export CONGRESS_NUMBER=119
export CACHE_TTL_SECONDS=86400
export CORS_ORIGINS=http://localhost:3000

uvicorn app.main:app --reload --port 8000
```

### Frontend (manual)

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CONGRESS_API_KEY` | *(required)* | Congress.gov API key |
| `CONGRESS_NUMBER` | `119` | Congress session to query |
| `CACHE_TTL_SECONDS` | `86400` | File cache TTL (24 hours) |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `NEXT_PUBLIC_API_URL` | — | Browser-facing API URL (frontend) |
| `API_URL` | — | Server-side API URL inside Docker network |
| `NEXT_PUBLIC_SITE_URL` | `https://operationchildshield.org` | Canonical site URL for Open Graph metadata |

See [`.env.example`](.env.example) for a template.

---

## Project structure

```
OperationChildShield/
├── AGENTS.md                     # Agent notes (deployment sensitivity, roadmap pointer)
├── backend/
│   ├── app/
│   │   ├── bills.py              # Curated tracked legislation
│   │   ├── bill_verification.py  # Startup Congress.gov title checks
│   │   ├── cache.py              # File cache with stale-while-revalidate
│   │   ├── cache_refresh.py      # Background cache revalidation
│   │   ├── congress_client.py    # Congress.gov HTTP client + cache
│   │   ├── scoring.py            # Vote scoring, policy_consistent, internal grades (not exposed)
│   │   ├── services.py           # Report cards, directory, API serialization
│   │   ├── metrics.py            # Bill-level roll-call aggregation (no member rankings)
│   │   └── routes/               # FastAPI routers
│   └── tests/                    # 97 pytest unit tests (no live API calls)
├── frontend/
│   └── src/
│       ├── app/                  # Next.js App Router pages
│       ├── components/
│       │   ├── charts/           # SVG pie and bar charts (metrics + member cards)
│       │   ├── metrics/          # Metrics page chart sections
│       │   ├── PolicyBadge.tsx   # Per-vote policy consistency badges
│       │   └── PolicyLegend.tsx  # Badge legend (landing + member pages)
│       └── lib/                  # API client, types, vote-count helpers + Vitest tests
├── .github/workflows/ci.yml      # Backend + frontend test CI on push/PR
├── scripts/
│   ├── deploy-prod.example.sh    # Production deploy template (copy → deploy-prod.sh)
│   ├── dev-local.sh              # Local backend + frontend without Docker
│   ├── verify_bills.py           # Manual bill verification
│   └── test.sh                   # Run backend + frontend tests
├── docker-compose.yml            # Local development stack
├── docker-compose.prod.example.yml  # Production template (copy → docker-compose.prod.yml)
├── Caddyfile.example             # Reverse proxy template (copy → Caddyfile)
└── Makefile                      # Common dev commands
```

Deployment scripts and production configs (`deploy-prod.sh`, `docker-compose.prod.yml`, `Caddyfile`, `deploy_paramiko.py`, etc.) are **gitignored** — copy from the `*.example` templates locally. See [`AGENTS.md`](AGENTS.md).

---

## Testing

**177 unit tests** total — **122 backend** (pytest) + **55 frontend** (Vitest). CI runs both suites on every push and pull request to `main` ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

```bash
# All tests (recommended — uses backend venv via scripts/test.sh)
make test

# Backend only
make test-backend

# Frontend only
make test-frontend

# Lint frontend
make lint

# Verify tracked bills against Congress.gov (requires API key)
make verify-bills
```

### Backend coverage (`backend/tests/`)

| Module | Tests |
|--------|-------|
| `scoring`, `bills`, `utils` | Vote normalization, policy consistency, bill catalog, member parsing |
| `services`, `metrics` | Report-card serialization, bill-level metrics aggregation |
| `cache`, `config`, `rate_limit` | File cache TTL, stale-while-revalidate, settings, concurrency limits |
| `bill_verification` | Congress.gov title verification (mocked client) |
| `routes/health` | Health endpoint (isolated FastAPI app) |

Backend tests do **not** call Congress.gov — pure logic, mocked async clients, and an isolated health route.

### Frontend coverage (`frontend/src/lib/*.test.ts`)

| Module | Tests |
|--------|-------|
| `format`, `party`, `states` | Member labels, policy consistency helpers, state codes |
| `vote-counts` | Yes/No vote counting, bill roll-call aggregation for charts |
| `share`, `fetch-queue`, `theme` | Social sharing URLs, API request concurrency, dark/light theme |

---

## Production deployment

Production runs with Docker Compose behind **Caddy** (TLS + reverse proxy: `/api/*` → backend, everything else → frontend).

Deployment configs are **gitignored** so server hosts and credentials stay out of version control.

If `deploy-prod.sh`, `docker-compose.prod.yml`, or `Caddyfile` were committed before, remove them from the index (local copies are kept):

```bash
git rm --cached scripts/deploy-prod.sh docker-compose.prod.yml Caddyfile .env 2>/dev/null || true
```

Copy the example files locally:

```bash
cp scripts/deploy-prod.example.sh scripts/deploy-prod.sh
cp docker-compose.prod.example.yml docker-compose.prod.yml
cp Caddyfile.example Caddyfile
chmod +x scripts/deploy-prod.sh
# Edit the three files for your domain, server, and CORS origins
```

```bash
# From your machine (requires SSH access to the server)
DEPLOY_REMOTE=user@your-server ./scripts/deploy-prod.sh
```

Before deploying:

1. Ensure `.env` on the server has `CONGRESS_API_KEY` and production `CORS_ORIGINS`.
2. Run `make verify-bills` locally or let the deploy script verify bill mappings.
3. Run `make test` locally.

---

## Operational notes

- **First request after cache expiry** can take 30–60+ seconds while report cards or metrics are built; stale cache is served during background refresh when available.
- **Backend startup** verifies all 30 tracked bills against Congress.gov; mismatches prevent the server from starting.
- **Senate members** appear in the directory but House roll-call votes drive per-member records; Senate floor votes are not available per-member via Congress.gov today.
- **Metrics page** aggregates bill-level roll-call statistics only — no member leaderboards or grade distributions.
- **Board page** is live (`ENABLE_BOARD_PAGE = true`). **Donate page** remains disabled until `ENABLE_DONATE_PAGE` is enabled and a payment processor is integrated.

---

## Development roadmap

Priorities below focus on launch readiness, production hardening, and sustainable growth. Timelines are estimates.

### Production migration assumptions

- **Current MVP**: Development Docker Compose setup (single VPS or local). Caddy handles TLS and reverse proxy.
- **Target production**: Dedicated server (e.g., Linode, DigitalOcean, Hetzner, or AWS Lightsail). Docker Compose for consistency, with secrets via Docker secrets or `.env` + systemd.
- **Benefits**: Better uptime, isolated services, easier scaling, automated backups, monitoring, and compliance (e.g., for donations).
- **Timeline**: 1–3 days for a basic migration when following `deploy-prod.example.sh` / `docker-compose.prod.example.yml`.

### Phase 1: Immediate priorities — features + production migration (1–3 weeks)

Focus on stability and launch readiness before deeper work.

1. **Polish Board of Directors page** (live — flag and nav enabled)
   - Refine bios, images, and content.
   - Continue QA and accessibility review.

2. **Enable and implement donation page**
   - Enable feature flag (`ENABLE_DONATE_PAGE`).
   - Integrate Stripe (primary) with PayPal fallback: forms with suggested/recurring amounts, fee coverage, impact messaging.
   - Add receipt/thank-you flows and basic donor logging.
   - Test thoroughly (sandbox first).

3. **Migrate to production server environment** (do this immediately after or alongside #1/#2)
   - **Prep**: Copy and customize `docker-compose.prod.example.yml`, `Caddyfile.example`, and `scripts/deploy-prod.example.sh`. Set production env vars (CORS, `NEXT_PUBLIC_SITE_URL`, API keys). Use secrets management — never commit keys. Run `make verify-bills` and `make test`.
   - **Server setup**: Provision a clean VPS (Ubuntu/Debian; 2–4 CPU, 4+ GB RAM). Install Docker and Docker Compose. Configure firewall (UFW: 80/443, SSH), fail2ban, automatic security updates. Set up Caddy for HTTPS and reverse proxy (`/api/*` → backend, static → frontend). Deploy via `DEPLOY_REMOTE=user@prod-server ./scripts/deploy-prod.sh`.
   - **Migration**: Copy cached files/DB if any. Point DNS (`operationchildshield.org`) to the new server. Preserve URLs; add 301 redirects if needed. Harden with rate limiting, WAF (e.g., CrowdSec), monitoring (UptimeRobot or Prometheus/Grafana), and automated offsite backups. Post-deploy: verify health endpoint, full site functionality, donation test transaction, cache warming.
   - **Rollback**: Keep MVP accessible temporarily; use blue-green or backup containers.

**Milestone**: Live production site with board and donate pages functional, secure, and performant. Monitor the first 24–48 hours.

### Phase 2: Deeper integrations and enhancements (2–4 weeks post-production)

Build on the stable production foundation.

- **Donor and engagement**: Stripe webhooks → Zapier/Mailchimp automation, donor portal.
- **Advocacy tools**: Bill alerts, analytics (GA4). *(State heat map, learn/get-involved, and share-to-platform links shipped.)*
- **Tech**: CI/CD improvements, performance tuning, accessibility audit.
- **Security review**: Full penetration test once production is live.

### Phase 3: Growth and sustainability (ongoing)

- Fundraising campaigns, advanced features (e.g., AI summaries), reporting, marketing.
- Scale hosting as traffic and donations grow.

---

## Data sources and disclaimer

- Member and vote data from the [Congress.gov API](https://api.congress.gov/)
- Site provided for **entertainment purposes** — see [/disclaimer](https://operationchildshield.org/disclaimer)
- Disputes or concerns: [Contact@OperationChildShield.com](mailto:Contact@OperationChildShield.com)
- Not affiliated with the U.S. Government
- Always verify official records at [congress.gov](https://www.congress.gov/)

---

## License

Provided for public transparency and educational purposes.
