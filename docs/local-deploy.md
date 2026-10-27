# Local deployment

Run the whole stack on your machine. Nothing in this guide touches production or
a remote host.

```bash
./scripts/local-deploy.sh start
./scripts/local-deploy.sh status
./scripts/local-deploy.sh logs
./scripts/local-deploy.sh stop
./scripts/local-deploy.sh reset   # stop and delete local databases
```

`start` builds the frontend production bundle, runs it with `next` standalone
output, and starts the API with uvicorn. Defaults:

| Service | URL |
|---|---|
| Public site | http://localhost:3010 |
| Admin sign in | http://localhost:3010/admin/login |
| Your account | http://localhost:3010/account |
| API docs | http://localhost:8000/docs |

Ports are configurable: `FRONTEND_PORT=4010 API_PORT=9000 ./scripts/local-deploy.sh start`.

## Seed an admin

There is no admin registration. Accounts are seeded:

```bash
ADMIN_PASSWORD='at-least-12-chars' ./scripts/local-deploy.sh stop
cd backend
CACHE_DIR=../data ADMIN_PASSWORD='at-least-12-chars' python3 ../scripts/seed_admin.py add you@example.org --name "Your Name"
```

The first seeded account becomes the `owner` role. Add `--role viewer` or
`--role editor` for staff who should not manage accounts.

## Local captcha

Local runs use Cloudflare's documented **test keys**, which always pass. The
widget really renders and the server really calls Cloudflare's verification
endpoint, so the integration is exercised. Set real `TURNSTILE_SITE_KEY` and
`TURNSTILE_SECRET_KEY` to test with a real challenge.

## Constituent accounts

`/account` supports sign up, email verification, sign in, password reset, saved
lawmakers, and alert toggles. Email is sent through the SMTP settings in `.env`.

Without SMTP configured, registration still creates the account and the
verification link is written to the backend log instead of being emailed. Read
it from `data/backend.log` or the local-deploy log:

```bash
grep -i "verification" .local-deploy/backend.log
```

## Reset local data

`reset` deletes `data/analytics.db`, `data/admin.db`, `data/users.db`, and the
involve signups file. Congress.gov cache files are left in place so the site
still renders without refetching.
