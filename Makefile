.PHONY: test test-backend test-frontend lint install verify-bills dev dev-local \
	dev-fresh seed-admin backup restore test-cov e2e precommit-install

# Prefer the backend venv when it can import the app; otherwise the system interpreter.
PYTHON := $(shell if backend/.venv/bin/python -c 'import fastapi, pydantic_settings' >/dev/null 2>&1; \
	then echo backend/.venv/bin/python; else echo python3; fi)

test:
	./scripts/test.sh

test-backend:
	cd backend && python3 -m pytest -q

test-frontend:
	cd frontend && npm test

test-cov:
	cd backend && $(PYTHON) -m pytest -q \
		--cov=app --cov-config=../pyproject.toml \
		--cov-report=term-missing --cov-fail-under=70

lint:
	cd frontend && npm run lint

install:
	cd backend && pip install -r requirements.txt -r requirements-dev.txt
	cd frontend && npm install

verify-bills:
	python3 scripts/verify_bills.py

dev:
	docker compose up --build

dev-local:
	./scripts/dev-local.sh start

# Rebuild containers from scratch (drops the anonymous build cache, keeps data volume).
dev-fresh:
	docker compose down
	docker compose build --no-cache
	docker compose up

# Usage: make seed-admin EMAIL=admin@example.org
# Reads ADMIN_PASSWORD when set, otherwise prompts twice.
seed-admin:
	@test -n "$(EMAIL)" || (echo "usage: make seed-admin EMAIL=admin@example.org" >&2; exit 2)
	$(PYTHON) scripts/seed_admin.py add "$(EMAIL)"

backup:
	@test -f scripts/backup_db.py || (echo "error: scripts/backup_db.py is missing (see scripts/backup_scheduler.md)" >&2; exit 2)
	$(PYTHON) scripts/backup_db.py backup

# Usage: make restore FILE=data/backups/backup-20260101T000000Z.zip
restore:
	@test -f scripts/backup_db.py || (echo "error: scripts/backup_db.py is missing (see scripts/backup_scheduler.md)" >&2; exit 2)
	@test -n "$(FILE)" || (echo "usage: make restore FILE=data/backups/<file>.zip  (see 'make backup' or scripts/backup_db.py list)" >&2; exit 2)
	$(PYTHON) scripts/backup_db.py restore "$(FILE)"

# Playwright smoke test against a running stack (E2E_BASE_URL, default localhost:3000).
e2e:
	cd frontend && npm install --no-save @playwright/test && npx playwright install chromium
	cd frontend && npx playwright test e2e/smoke.spec.ts --reporter=list

precommit-install:
	$(PYTHON) -m pip install pre-commit
	$(PYTHON) -m pre_commit install --install-hooks
