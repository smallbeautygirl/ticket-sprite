#!/usr/bin/env bash
# Start / stop the single-user trial on this VM (backend :8020, frontend :3000).
# Settings come from ../.env (see .env.example); data lives in ../data.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$ROOT/data"
mkdir -p "$DATA/logs"

# Each service runs in its own session, so its pid is also its process group id:
# stopping the group takes down npx's next-server child too, not just the wrapper.
stop() {
  for name in backend frontend; do
    local pid
    pid="$(cat "$DATA/$name.pid" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 -- "-$pid" 2>/dev/null; then
      kill -- "-$pid"
      for _ in $(seq 1 50); do kill -0 -- "-$pid" 2>/dev/null || break; sleep 0.2; done
      kill -0 -- "-$pid" 2>/dev/null && kill -9 -- "-$pid"
      echo "stopped $name"
    fi
    rm -f "$DATA/$name.pid"
  done
}

# Detach fully (own session, no inherited stdin/stdout) so the caller's shell returns at once
launch() {
  local name="$1" dir="$2"; shift 2
  (cd "$dir"; setsid "$@" > "$DATA/logs/$name.log" 2>&1 < /dev/null & echo $! > "$DATA/$name.pid")
}

start() {
  [ -f "$ROOT/.env" ] || { echo "missing $ROOT/.env (copy .env.example)"; exit 1; }
  set -a; source "$ROOT/.env"; set +a
  export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///$DATA/ticket_sprite.db}"
  export UPLOAD_DIR="${UPLOAD_DIR:-$DATA/uploads}" KNOWLEDGE_ROOT="${KNOWLEDGE_ROOT:-$DATA/knowledge}"
  export BACKEND_URL="http://localhost:${BACKEND_PORT:-8020}"

  launch backend "$ROOT/backend" .venv/bin/uvicorn ticket_sprite.main:app --host 127.0.0.1 \
    --port "${BACKEND_PORT:-8020}"
  launch frontend "$ROOT/frontend" npx next start -H 0.0.0.0 -p "${SPRITE_PORT:-3000}"
  echo "started: ${PUBLIC_BASE_URL:-http://localhost:${SPRITE_PORT:-3000}}  (logs in $DATA/logs)"
}

case "${1:-start}" in
  start) stop; start ;;
  stop) stop ;;
  *) echo "usage: $0 [start|stop]"; exit 1 ;;
esac
