# Development workflow

## Prerequisites

- Python 3.13+ for the backend (`backend/`), Node 24 for the frontend (`frontend/`).
- `make install` installs both dependency sets. Backend runtime deps are stdlib-only
  plus FastAPI/pydantic/httpx; test-only tools live in `backend/requirements-dev.txt`.

## Tests

```bash
make test-backend      # cd backend && python3 -m pytest -q
make test-frontend     # cd frontend && npm test
make test-cov          # backend with --cov=app --cov-fail-under=70
```

Coverage thresholds:

- Backend: 70% (`--cov-fail-under=70`, config in the root `pyproject.toml`).
- Frontend: 60% across lines/functions/branches/statements, scoped to `src/lib`
  (`frontend/vitest.config.ts`). `npm run test:coverage` needs
  `@vitest/coverage-v8`, which is declared in `package.json`; run `npm install`
  once in `frontend/` to update the lockfile.

## Pre-commit hooks

```bash
make precommit-install
```

Fast hooks (trailing whitespace, EOF newline, YAML validity, large-file and
merge-conflict checks) run on `pre-commit`. Slower checks run on `pre-push`:

| Hook | Command | Working dir |
|------|---------|-------------|
| `frontend-tsc` | `npx tsc --noEmit` | `frontend/` |
| `frontend-eslint` | `npx eslint .` | `frontend/` |
| `backend-pytest` | `python3 -m pytest -q` | `backend/` |

Run everything without committing:

```bash
pre-commit run --all-files
pre-commit run --hook-stage pre-push --all-files
```

## Local dev shortcuts

```bash
make dev-local          # start backend + frontend with local data
make dev-fresh          # rebuild containers from scratch
make seed-admin EMAIL=admin@example.org
make backup             # scripts/backup_db.py backup
make restore FILE=data/backups/<file>.zip
make e2e                # Playwright smoke test against a running stack
```

`make e2e` expects the site on `http://localhost:3000` (override with
`E2E_BASE_URL`). Playwright is installed per-run with `--no-save`, so it never
enters `package.json`.

## Background jobs

`backend/app/jobs.py` runs an in-process scheduler thread when
`SCHEDULER_ENABLED=true` (default). `SCHEDULER_INTERVAL_SECONDS` controls the
tick. Registered jobs: `prune_analytics`, `send_alerts`, `verify_bills` (skipped
when `SKIP_BILL_VERIFICATION=1`). Inspect it through `scheduler_state()`.

## CI

`.github/workflows/ci.yml` runs backend pytest with coverage, frontend Vitest
plus coverage, and a Trivy config scan. The `e2e` job is `workflow_dispatch`
only and is not a required check.
