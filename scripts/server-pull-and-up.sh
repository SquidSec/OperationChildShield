#!/usr/bin/env bash
# Run on the production droplet to pull GHCR images and restart the stack.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/operationchildshield}"
IMAGE_TAG="${IMAGE_TAG:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.ghcr.yml}"
# Backend Dockerfile USER app is uid/gid 1001
BACKEND_UID="${BACKEND_UID:-1001}"
BACKEND_GID="${BACKEND_GID:-1001}"

cd "$APP_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export IMAGE_TAG
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://$(curl -fsS ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')}"

# Public GHCR packages can be pulled anonymously; if private, set GHCR_TOKEN in .env
if [[ -n "${GHCR_TOKEN:-}" ]]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "${GHCR_USER:-squidsec}" --password-stdin
fi

# Ensure cache/PII volume is writable by non-root backend user before start.
# Named volume path may not exist until first create; ignore failure then fix after up.
VOL_NAME="$(docker compose -f "$COMPOSE_FILE" config --volumes 2>/dev/null | head -1 || true)"
if [[ -n "${VOL_NAME:-}" ]]; then
  # Prefer project-prefixed volume names Docker Compose uses.
  for v in \
    "${COMPOSE_PROJECT_NAME:-operationchildshield}_backend-cache" \
    "operationchildshield_backend-cache" \
    "backend-cache"; do
    mp="$(docker volume inspect -f '{{ .Mountpoint }}' "$v" 2>/dev/null || true)"
    if [[ -n "${mp:-}" && -d "$mp" ]]; then
      chown -R "${BACKEND_UID}:${BACKEND_GID}" "$mp" || true
      # Tighten perms on known PII/db files if present
      chmod 600 "$mp"/involve_signups.jsonl 2>/dev/null || true
      chmod 600 "$mp"/analytics.db 2>/dev/null || true
      break
    fi
  done
fi

docker compose -f "$COMPOSE_FILE" pull
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

# Re-apply ownership after containers start (volume mountpoints always exist then).
for v in \
  "${COMPOSE_PROJECT_NAME:-operationchildshield}_backend-cache" \
  "operationchildshield_backend-cache"; do
  mp="$(docker volume inspect -f '{{ .Mountpoint }}' "$v" 2>/dev/null || true)"
  if [[ -n "${mp:-}" && -d "$mp" ]]; then
    chown -R "${BACKEND_UID}:${BACKEND_GID}" "$mp" || true
    chmod 600 "$mp"/involve_signups.jsonl 2>/dev/null || true
    chmod 600 "$mp"/analytics.db 2>/dev/null || true
  fi
done

echo "Waiting for backend health..."
for i in $(seq 1 40); do
  if docker compose -f "$COMPOSE_FILE" exec -T backend curl -fsS http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "Backend healthy."
    docker compose -f "$COMPOSE_FILE" ps
    exit 0
  fi
  sleep 3
done

echo "Backend health check timed out" >&2
docker compose -f "$COMPOSE_FILE" ps
docker compose -f "$COMPOSE_FILE" logs --tail=80 backend || true
exit 1
