#!/usr/bin/env bash
# Local-only stack: build and run the frontend in production mode, backend with
# uvicorn. Nothing here touches a remote host. See docs/local-deploy.md.
#
#   scripts/local-deploy.sh start [--port 3010] [--api-port 8000]
#   scripts/local-deploy.sh stop
#   scripts/local-deploy.sh status
#   scripts/local-deploy.sh logs
#   scripts/local-deploy.sh reset      # stop + remove local runtime databases
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_PORT="${FRONTEND_PORT:-3010}"
API_PORT="${API_PORT:-8000}"
RUN_DIR="$ROOT/.local-deploy"
BACKEND_PID="$RUN_DIR/backend.pid"
FRONTEND_PID="$RUN_DIR/frontend.pid"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"

mkdir -p "$RUN_DIR"

# The repo's backend/.venv is not reliable on every machine; prefer system
# python3.13 when FastAPI is importable there, else fall back to the venv.
pick_python() {
  if command -v python3.13 >/dev/null 2>&1 && python3.13 -c "import fastapi" >/dev/null 2>&1; then
    echo "python3.13"
  elif [ -x "$ROOT/backend/.venv/bin/python" ] && "$ROOT/backend/.venv/bin/python" -c "import fastapi" >/dev/null 2>&1; then
    echo "$ROOT/backend/.venv/bin/python"
  else
    echo ""
  fi
}

stop_one() {
  local pid_file="$1" name="$2"
  if [ -f "$pid_file" ]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "stopped $name (pid $pid)"
    fi
    rm -f "$pid_file"
  fi
}

port_busy() {
  ss -ltn 2>/dev/null | grep -q ":$1 "
}

start() {
  local py
  py="$(pick_python)"
  if [ -z "$py" ]; then
    echo "error: no Python with FastAPI available. Run: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
  fi

  if port_busy "$API_PORT"; then
    echo "error: port $API_PORT is already in use" >&2
    exit 1
  fi
  if port_busy "$FRONTEND_PORT"; then
    echo "error: port $FRONTEND_PORT is already in use (set FRONTEND_PORT)" >&2
    exit 1
  fi

  export CACHE_DIR="${CACHE_DIR:-$ROOT/data}"
  export SKIP_BILL_VERIFICATION="${SKIP_BILL_VERIFICATION:-1}"
  # Local captcha uses Cloudflare's documented test keys, which always pass.
  export TURNSTILE_SITE_KEY="${TURNSTILE_SITE_KEY:-1x00000000000000000000AA}"
  export TURNSTILE_SECRET_KEY="${TURNSTILE_SECRET_KEY:-1x0000000000000000000000000000000AA}"
  export CORS_ORIGINS="http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT"
  export ADMIN_ALLOWED_HOSTNAMES="localhost,127.0.0.1,operationchildshield.org,www.operationchildshield.org"
  # Local only: account verification/reset links are returned inline instead of
  # requiring a working mailbox.
  export DEV_EMAIL_OUTBOX="${DEV_EMAIL_OUTBOX:-1}"
  export DEV_RELAX_RATE_LIMITS="${DEV_RELAX_RATE_LIMITS:-1}"
  export PUBLIC_SITE_URL="http://localhost:$FRONTEND_PORT"

  echo "starting backend on http://127.0.0.1:$API_PORT"
  ( cd "$ROOT/backend" && nohup "$py" -m uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" \
      >"$BACKEND_LOG" 2>&1 & echo $! >"$BACKEND_PID" )

  echo "building frontend (production bundle)…"
  ( cd "$ROOT/frontend" && NEXT_PUBLIC_API_URL="http://127.0.0.1:$API_PORT" API_URL="http://127.0.0.1:$API_PORT" npm run build >"$RUN_DIR/build.log" 2>&1 )

  # `output: "standalone"` emits a self-contained server that does NOT include
  # static chunks or public assets. The production Dockerfile copies them in;
  # do the same here or every JS chunk 404s and the captcha never loads.
  if [ -d "$ROOT/frontend/.next/standalone" ]; then
    mkdir -p "$ROOT/frontend/.next/standalone/.next" "$ROOT/frontend/.next/standalone/public"
    rm -rf "$ROOT/frontend/.next/standalone/.next/static"
    cp -R "$ROOT/frontend/.next/static" "$ROOT/frontend/.next/standalone/.next/static"
    cp -R "$ROOT/frontend/public/." "$ROOT/frontend/.next/standalone/public/"
  fi

  echo "starting frontend on http://127.0.0.1:$FRONTEND_PORT"
  ( cd "$ROOT/frontend" && nohup env PORT="$FRONTEND_PORT" HOSTNAME=127.0.0.1 \
      NEXT_PUBLIC_API_URL="http://127.0.0.1:$API_PORT" API_URL="http://127.0.0.1:$API_PORT" \
      node .next/standalone/server.js >"$FRONTEND_LOG" 2>&1 & echo $! >"$FRONTEND_PID" )

  wait_for_health
}

wait_for_health() {
  local i
  for i in $(seq 1 60); do
    # /admin/login is a cheap server render; "/" pulls member data and is slow.
    if curl -fsS --max-time 3 "http://127.0.0.1:$API_PORT/api/health" >/dev/null 2>&1 \
      && curl -fsS --max-time 5 -o /dev/null "http://127.0.0.1:$FRONTEND_PORT/admin/login" 2>&1; then
      echo
      echo "Local stack ready:"
      echo "  Public site  http://localhost:$FRONTEND_PORT"
      echo "  Admin        http://localhost:$FRONTEND_PORT/admin/login"
      echo "  Your account http://localhost:$FRONTEND_PORT/account"
      echo "  API docs     http://localhost:$API_PORT/docs"
      echo "  Logs         $RUN_DIR/{backend,frontend}.log"
      return 0
    fi
    sleep 1
  done
  echo "timed out waiting for services; see $BACKEND_LOG and $FRONTEND_LOG" >&2
  return 1
}

status() {
  local file name port
  for entry in "$BACKEND_PID|backend|$API_PORT" "$FRONTEND_PID|frontend|$FRONTEND_PORT"; do
    IFS='|' read -r file name port <<<"$entry"
    if [ -f "$file" ] && kill -0 "$(cat "$file")" 2>/dev/null; then
      echo "$name: running (pid $(cat "$file"), port $port)"
    else
      echo "$name: stopped"
    fi
  done
}

case "${1:-start}" in
  start) start ;;
  stop) stop_one "$FRONTEND_PID" frontend; stop_one "$BACKEND_PID" backend ;;
  status) status ;;
  logs) tail -n 40 "$BACKEND_LOG" "$FRONTEND_LOG" 2>/dev/null || true ;;
  reset)
    stop_one "$FRONTEND_PID" frontend
    stop_one "$BACKEND_PID" backend
    echo "removing local runtime databases and caches under data/"
    rm -f "$ROOT"/data/{analytics,admin,users}.db "$ROOT"/data/involve_signups.jsonl
    ;;
  *)
    echo "usage: $0 {start|stop|status|logs|reset}" >&2
    exit 2
    ;;
esac
