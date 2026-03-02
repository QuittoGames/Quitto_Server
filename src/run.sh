#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

REQ_FILE="requirements.txt"
VENV_DIR=".venv"
ENV_FILE=".env"

# ================= ENV =================
if [ -f "$ENV_FILE" ]; then
  set -o allexport
  source "$ENV_FILE"
  set +o allexport
fi

UVICORN_HOST="0.0.0.0"
UVICORN_PORT="3333"
WORKERS="${UVICORN_WORKERS:-1}"

NGROK_TOKEN="${NGROK_AUTHTOKEN:-}"
NGROK_URL="${NGROK_URL:-}"

# ================= HELPERS =================
kill_process_on_port() {
  ss -lntp | awk -v p=":${1}" '$4~p {print $7}' | grep -oP 'pid=\K\d+' | xargs -r kill -9 || true
}

stop_uvicorn() {
  if [ -f uvicorn.pid ]; then
    kill "$(cat uvicorn.pid)" 2>/dev/null || true
    rm -f uvicorn.pid
  fi
}

stop_ngrok() {
  docker rm -f mcp_ngrok 2>/dev/null || true
  rm -f ngrok.cid
}

wait_for_server() {
  for _ in {1..30}; do
    curl -sf "http://127.0.0.1:${UVICORN_PORT}/" && return 0
    sleep 1
  done
  echo "❌ server não respondeu"
  exit 1
}

# ================= SERVER =================
start_server() {
  [ -d "$VENV_DIR" ] || python3 -m venv "$VENV_DIR"
  source "$VENV_DIR/bin/activate"
  pip install -q --upgrade pip
  [ -f "$REQ_FILE" ] && pip install -q -r "$REQ_FILE"

  kill_process_on_port "$UVICORN_PORT"
  nohup python -m uvicorn index:app \
    --host "$UVICORN_HOST" \
    --port "$UVICORN_PORT" \
    --workers "$WORKERS" \
    --proxy-headers \
    > uvicorn.log 2>&1 &

  echo $! > uvicorn.pid
}

# ================= NGROK =================
start_ngrok() {
  wait_for_server
  docker pull ngrok/ngrok:latest >/dev/null
  docker run -d \
    --name mcp_ngrok \
    --net=host \
    -e NGROK_AUTHTOKEN="$NGROK_TOKEN" \
    ngrok/ngrok:latest http "$UVICORN_PORT" > ngrok.cid
}

# ================= FLAGS =================
DO_SERVER=false
DO_NGROK=false

for arg in "$@"; do
  case "$arg" in
    --server) DO_SERVER=true ;;
    --ngrok) DO_NGROK=true ;;
  esac
done

[ "$DO_SERVER" = false ] && [ "$DO_NGROK" = false ] && DO_SERVER=true && DO_NGROK=true

# ================= RUN =================
trap 'stop_uvicorn; stop_ngrok; exit 0' INT TERM

$DO_SERVER && start_server
$DO_NGROK && start_ngrok

echo "✅ server + ngrok ativos"
tail -f uvicorn.log