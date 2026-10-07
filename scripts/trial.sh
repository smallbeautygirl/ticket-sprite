#!/usr/bin/env bash
# Start / stop the single-user trial on this VM (backend :8020, frontend :3000).
# Settings come from ../.env (see .env.example); data lives in ../data.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$ROOT/data"
mkdir -p "$DATA/logs"

stop() {
  for name in backend frontend; do
    if [ -f "$DATA/$name.pid" ] && kill -0 "$(cat "$DATA/$name.pid")" 2>/dev/null; then
      kill "$(cat "$DATA/$name.pid")" && echo "stopped $name"
    fi
    rm -f "$DATA/$name.pid"
  done
}

start() {
  [ -f "$ROOT/.env" ] || { echo "missing $ROOT/.env (copy .env.example)"; exit 1; }
  set -a; source "$ROOT/.env"; set +a
  export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///$DATA/ticket_sprite.db}"
  export UPLOAD_DIR="${UPLOAD_DIR:-$DATA/uploads}" KNOWLEDGE_ROOT="${KNOWLEDGE_ROOT:-$DATA/knowledge}"
  export BACKEND_URL="http://localhost:${BACKEND_PORT:-8020}"

  (cd "$ROOT/backend" && nohup .venv/bin/uvicorn ticket_sprite.main:app --host 127.0.0.1 \
     --port "${BACKEND_PORT:-8020}" > "$DATA/logs/backend.log" 2>&1 & echo $! > "$DATA/backend.pid")
  (cd "$ROOT/frontend" && nohup npx next start -H 0.0.0.0 -p "${SPRITE_PORT:-3000}" \
     > "$DATA/logs/frontend.log" 2>&1 & echo $! > "$DATA/frontend.pid")
  echo "started: ${PUBLIC_BASE_URL:-http://localhost:${SPRITE_PORT:-3000}}  (logs in $DATA/logs)"
}

case "${1:-start}" in
  start) stop; start ;;
  stop) stop ;;
  *) echo "usage: $0 [start|stop]"; exit 1 ;;
esac
