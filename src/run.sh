#!/usr/bin/env bash
set -euo pipefail

# Simple launcher for the MCP project:
# - detects apt/dnf
# - installs python/pip/docker (requires sudo)
# - creates a virtualenv `.venv` and installs `requirements.txt`
# - starts uvicorn (index:app) on 127.0.0.1:3333
# - optionally starts ngrok in Docker if NGROK_AUTHTOKEN is provided

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

REQ_FILE="requirements.txt"
VENV_DIR=".venv"
ENV_FILE=".env"

# If a .env file exists, export its variables into the environment for the script
if [ -f "$ENV_FILE" ]; then
	echo "Loading environment variables from $ENV_FILE"
	# set -a exports all sourced variables into the environment
	set -o allexport
	# shellcheck disable=SC1090
	source "$ENV_FILE"
	set +o allexport
fi

# Hard-code host and port (ignore HOST/PORT in environment)
UVICORN_HOST="127.0.0.1"
UVICORN_PORT="3333"

# Read ngrok vars from environment (may come from .env)
NGROK_TOKEN="${NGROK_AUTHTOKEN:-}"
NGROK_URL="${NGROK_URL:-}"

detect_pkg_mgr(){
	if command -v apt-get >/dev/null 2>&1; then echo apt;
	elif command -v dnf >/dev/null 2>&1; then echo dnf;
	else echo none; fi
}

PKG_MGR=$(detect_pkg_mgr)

install_system_pkgs(){
	echo "Detected package manager: $PKG_MGR"
	case "$PKG_MGR" in
		apt)
			sudo apt-get update
			sudo apt-get install -y python3 python3-venv python3-pip docker.io || true
			;;
		dnf)
			sudo dnf install -y python3 python3-virtualenv python3-pip docker || true
			;;
		none)
			echo "No supported package manager found (apt or dnf). Please install Python3, pip and Docker manually.";
			;;
	esac
}

create_venv_and_install(){
	if [ ! -d "$VENV_DIR" ]; then
		echo "Creating virtualenv in $VENV_DIR..."
		python3 -m venv "$VENV_DIR"
	fi
	# shellcheck disable=SC1090
	source "$VENV_DIR/bin/activate"
	python -m pip install --upgrade pip
	if [ -f "$REQ_FILE" ]; then
		echo "Installing Python requirements from $REQ_FILE..."
		pip install -r "$REQ_FILE"
	else
		echo "No $REQ_FILE found. Skipping pip install.";
	fi
}

start_uvicorn(){
	# start in background and write pid
	echo "Starting uvicorn on ${UVICORN_HOST}:${UVICORN_PORT}..."
	nohup python -m uvicorn index:app --host "$UVICORN_HOST" --port "$UVICORN_PORT" > uvicorn.log 2>&1 &
	echo $! > uvicorn.pid
	echo "Uvicorn started (pid=$(cat uvicorn.pid)), logs -> uvicorn.log"
}

# Wait for the server to accept HTTP connections before proceeding.
# Tries /health then /; returns 0 on success, 1 on failure after timeout.
wait_for_server(){
	local retries=30
	local i=0
	echo "Waiting for server to become available at http://${UVICORN_HOST}:${UVICORN_PORT}..."
	while [ $i -lt $retries ]; do
		if command -v curl >/dev/null 2>&1; then
			if curl -sSf "http://${UVICORN_HOST}:${UVICORN_PORT}/health" >/dev/null 2>&1; then
				echo "Server responded on /health"
				return 0
			fi
			if curl -sSf "http://${UVICORN_HOST}:${UVICORN_PORT}/" >/dev/null 2>&1; then
				echo "Server responded on /"
				return 0
			fi
		else
			# fallback to python check
			python3 - <<PY >/dev/null 2>&1 || true
import sys, urllib.request
try:
	urllib.request.urlopen('http://%s:%s/health' % ('${UVICORN_HOST}','${UVICORN_PORT}'), timeout=2)
	sys.exit(0)
except:
	try:
		urllib.request.urlopen('http://%s:%s/' % ('${UVICORN_HOST}','${UVICORN_PORT}'), timeout=2)
		sys.exit(0)
	except:
		sys.exit(1)
PY
			if [ $? -eq 0 ]; then
				echo "Server responded (python check)"
				return 0
			fi
		fi
		i=$((i+1))
		sleep 1
	done
	echo "Timed out waiting for server after ${retries}s"
	return 1
}

start_ngrok_docker(){
	# Prefer using an env file if present so docker picks up all variables
	# Prefer using an env file if present so docker picks up all variables
	if [ -f "$ENV_FILE" ]; then
		echo "Using env file $ENV_FILE for Docker (NGROK_AUTHTOKEN will be passed there)."
		echo "Pulling ngrok Docker image..."
		docker pull ngrok/ngrok:latest
		echo "Starting ngrok (Docker) using --env-file $ENV_FILE (detached)..."
		# If a container with the name exists, start/reuse it to avoid name conflicts
		EXISTING_CID=$(docker ps -a -q -f name=mcp_ngrok 2>/dev/null || true)
		if [ -n "$EXISTING_CID" ]; then
			# check container status
			STATUS=$(docker inspect --format '{{.State.Status}}' mcp_ngrok 2>/dev/null || true)
			if [ "$STATUS" = "running" ]; then
				RUNNING_CID=$(docker ps -q -f name=mcp_ngrok 2>/dev/null || true)
				echo "ngrok container 'mcp_ngrok' is already running. Skipping start."
				echo "$RUNNING_CID" > ngrok.cid
				return
			else
				if [ "$DO_KEEP_NGROK" = true ]; then
					echo "Found existing stopped container 'mcp_ngrok', starting it due to --keep-ngrok..."
					docker start mcp_ngrok >/dev/null 2>&1 || true
					docker ps -q -f name=mcp_ngrok >/dev/null 2>&1 && docker ps -q -f name=mcp_ngrok > ngrok.cid || true
					echo "ngrok started (existing container). Use 'docker logs -f mcp_ngrok' to follow logs." 
					return
				else
					echo "Found existing stopped container 'mcp_ngrok' (id=$EXISTING_CID). Removing it to avoid conflicts..."
					docker rm -f mcp_ngrok >/dev/null 2>&1 || true
					# continue to start a fresh container
				fi
			fi
		fi
		if [ -n "$NGROK_URL" ]; then
			CID=$(docker run --net=host --env-file "$ENV_FILE" -d --name mcp_ngrok ngrok/ngrok:latest http --url="$NGROK_URL" "$UVICORN_PORT")
		else
			CID=$(docker run --net=host --env-file "$ENV_FILE" -d --name mcp_ngrok ngrok/ngrok:latest http "$UVICORN_PORT")
		fi
		echo "$CID" > ngrok.cid
		echo "ngrok started detached (container id=$CID), use 'docker logs -f mcp_ngrok' to follow logs or 'docker stop mcp_ngrok' to stop."
		return
	fi

	if [ -z "$NGROK_TOKEN" ]; then
		echo "NGROK_AUTHTOKEN not set; skipping ngrok start.";
		return
	fi

	echo "Pulling ngrok Docker image..."
	docker pull ngrok/ngrok:latest
	echo "Starting ngrok (Docker) (detached)..."
	# If a container with the name exists, start/reuse it to avoid name conflicts
	EXISTING_CID=$(docker ps -a -q -f name=mcp_ngrok 2>/dev/null || true)
	if [ -n "$EXISTING_CID" ]; then
		STATUS=$(docker inspect --format '{{.State.Status}}' mcp_ngrok 2>/dev/null || true)
		if [ "$STATUS" = "running" ]; then
			RUNNING_CID=$(docker ps -q -f name=mcp_ngrok 2>/dev/null || true)
			echo "ngrok container 'mcp_ngrok' is already running. Skipping start."
			echo "$RUNNING_CID" > ngrok.cid
			return
		else
			if [ "$DO_KEEP_NGROK" = true ]; then
				echo "Found existing stopped container 'mcp_ngrok', starting it due to --keep-ngrok..."
				docker start mcp_ngrok >/dev/null 2>&1 || true
				docker ps -q -f name=mcp_ngrok >/dev/null 2>&1 && docker ps -q -f name=mcp_ngrok > ngrok.cid || true
				echo "ngrok started (existing container). Use 'docker logs -f mcp_ngrok' to follow logs." 
				return
			else
				echo "Found existing stopped container 'mcp_ngrok' (id=$EXISTING_CID). Removing it to avoid conflicts..."
				docker rm -f mcp_ngrok >/dev/null 2>&1 || true
				# continue to start a fresh container
			fi
		fi
	fi
	# Use provided NGROK_URL if set (note: custom subdomains may require paid plan)
	if [ -n "$NGROK_URL" ]; then
		CID=$(docker run --net=host -d --name mcp_ngrok -e NGROK_AUTHTOKEN="$NGROK_TOKEN" ngrok/ngrok:latest http --url="$NGROK_URL" "$UVICORN_PORT")
	else
		CID=$(docker run --net=host -d --name mcp_ngrok -e NGROK_AUTHTOKEN="$NGROK_TOKEN" ngrok/ngrok:latest http "$UVICORN_PORT")
	fi
	echo "$CID" > ngrok.cid
	echo "ngrok started detached (container id=$CID), use 'docker logs -f mcp_ngrok' to follow logs or 'docker stop mcp_ngrok' to stop."
}

show_help(){
	cat <<EOF
Usage: ./run.sh [--install-system] [--ngrok]

Options:
	--install-system   Attempt to install system packages via apt or dnf (requires sudo)
	--ngrok            Start ngrok (Docker) after launching uvicorn. Requires NGROK_AUTHTOKEN env var.
	--no-ui            Do not start the interactive TUI; print status and return to shell
	--keep-ngrok       Do not stop ngrok container on Ctrl-C (leave running)
	--help             Show this help

Environment:
	NGROK_AUTHTOKEN    ngrok authtoken (or pass to script env)
	NGROK_URL          Optional ngrok URL/subdomain (may require paid plan)
	HOST               Host to bind (default 127.0.0.1)
	PORT               Port to bind (default 3333)

Examples:
	NGROK_AUTHTOKEN=TOKEN ./run.sh --install-system --ngrok
	./run.sh
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
	show_help; exit 0
fi

# Behavior:
# - no flags: start both server and ngrok
# - --server: start only the server
# - --ngrok: start only ngrok
# - both flags: start both

DO_NGROK=false
DO_SERVER=false
DO_INSTALL=false
DO_KEEP_NGROK=false
DO_NO_UI=false

if [ "$#" -eq 0 ]; then
	# no args -> default: run both
	DO_SERVER=true
	DO_NGROK=true
else
	for arg in "$@"; do
		case "$arg" in
			--ngrok) DO_NGROK=true ;;
			--server) DO_SERVER=true ;;
			--no-ui) DO_NO_UI=true ;;
			--install-system) DO_INSTALL=true ;;
			--keep-ngrok) DO_KEEP_NGROK=true ;;
		esac
	done
	# if user passed flags but none were server/ngrok, default to both
	if [ "$DO_SERVER" = false ] && [ "$DO_NGROK" = false ]; then
		DO_SERVER=true
		DO_NGROK=true
	fi
fi

if $DO_INSTALL; then
	install_system_pkgs
fi

if $DO_SERVER; then
	create_venv_and_install
	start_uvicorn
else
	echo "Server start skipped (--server not set)."
fi

# If requested to start ngrok, wait until server is up (if server was started here)
if $DO_NGROK; then
	if $DO_SERVER; then
		if wait_for_server; then
			echo "Server is up — starting ngrok..."
		else
			echo "Warning: server did not become ready in time. Proceeding to start ngrok anyway."
		fi
	fi
	start_ngrok_docker
else
	echo "ngrok start skipped (--ngrok not set)."
	echo "To start ngrok only: ./run.sh --ngrok"
fi

# Cleanup function to stop uvicorn and ngrok container on SIGINT/SIGTERM
cleanup(){
	echo "\nShutting down..."
	# stop uvicorn if started
	if [ -f uvicorn.pid ]; then
		PID=$(cat uvicorn.pid 2>/dev/null || true)
		if [ -n "$PID" ] && kill -0 "$PID" >/dev/null 2>&1; then
			echo "Stopping uvicorn (pid=$PID)"
			kill "$PID" || true
			sleep 1
		fi
		rm -f uvicorn.pid
	fi

	# stop ngrok container if created (unless user asked to keep it)
	if [ "$DO_KEEP_NGROK" = false ]; then
		if docker ps -q -f name=mcp_ngrok >/dev/null 2>&1 && [ -n "$(docker ps -q -f name=mcp_ngrok)" ]; then
			echo "Stopping ngrok container 'mcp_ngrok'"
			docker stop mcp_ngrok >/dev/null 2>&1 || true
		fi
	else
		echo "--keep-ngrok set; leaving ngrok container running."
	fi
	rm -f ngrok.cid || true
	exit 0
}

trap cleanup INT TERM

# Small TUI: banner, status and recent logs. Refreshes until interrupted.
render_ui(){
	# smaller interval for smoother updates
	local sleep_sec="0.5"
	while true; do
		# clear screen for clearer layout
		printf '\033[2J\033[H'

		# Banner (bright cyan)
		printf '%b\n' '\033[1;36m============================================================='
		printf '%b\n' '                       QUITTO MCP SERVER                       '
		printf '%b\n' '=============================================================\033[0m'

		# Server status (green/yellow/red)
		if [ -f uvicorn.pid ]; then
			PID=$(cat uvicorn.pid 2>/dev/null || true)
			if [ -n "$PID" ] && kill -0 "$PID" >/dev/null 2>&1; then
				printf '%b\n' "\033[1;32mServer:\033[0m    OK     (pid=${PID})"
			else
				printf '%b\n' "\033[1;33mServer:\033[0m    WARN   (pid file exists but process not running)"
			fi
		else
			printf '%b\n' "\033[1;31mServer:\033[0m    DOWN   (not running)"
		fi

		# ngrok status and public URL
		NGROK_CID=$(docker ps -q -f name=mcp_ngrok 2>/dev/null || true)
		if [ -n "$NGROK_CID" ]; then
			# attempt to fetch public url from local ngrok API (available when using --net=host)
			NGROK_PUBLIC=""
			if command -v curl >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
				NGROK_PUBLIC=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c 'import sys,json; s=sys.stdin.read(); print("" if not s.strip() else (lambda d: (d.get("tunnels",[])[0].get("public_url","") if d.get("tunnels") else ""))(json.loads(s)))')
			fi
			if [ -n "$NGROK_PUBLIC" ]; then
				printf '%b\n' "\033[1;32mngrok:\033[0m    OK     (container=${NGROK_CID}) -> ${NGROK_PUBLIC}"
			else
				printf '%b\n' "\033[1;32mngrok:\033[0m    OK     (container=${NGROK_CID})"
			fi
		else
			# check if stopped container exists
			EXIST_CID=$(docker ps -a -q -f name=mcp_ngrok 2>/dev/null || true)
			if [ -n "$EXIST_CID" ]; then
				printf '%b\n' "\033[1;33mngrok:\033[0m    STOPPED (container=${EXIST_CID})"
			else
				printf '%b\n' "\033[1;31mngrok:\033[0m    DOWN    (not running)"
			fi
		fi

		printf '%b\n' '-------------------------------------------------------------'
		printf '%b\n' 'Recent server logs (last 12 lines):'
		echo
		if [ -f uvicorn.log ]; then
			tail -n 12 uvicorn.log | sed -e 's/^/  /'
		else
			echo "  (no uvicorn.log yet)"
		fi

		# small ngrok log excerpt for quick visibility
		echo
		printf '%b\n' 'ngrok recent logs (last 6 lines):'
		if [ -n "$NGROK_CID" ]; then
			docker logs --tail 6 mcp_ngrok 2>/dev/null | sed -e 's/^/  /' || echo "  (no ngrok logs yet)"
		else
			echo "  (ngrok not running)"
		fi

		# Combined recent logs (uvicorn + ngrok) for quick debugging
		printf '%b\n' '-------------------------------------------------------------'
		printf '%b\n' 'Combined recent logs (uvicorn + ngrok):'
		# collect uvicorn log (if exists) and a short ngrok tail, then show last 30 lines
		(
			if [ -f uvicorn.log ]; then
				tail -n 20 uvicorn.log
			fi
			if [ -n "$NGROK_CID" ]; then
				docker logs --tail 20 mcp_ngrok 2>/dev/null || true
			fi
		) | sed -e 's/^/  /' | tail -n 30 || true

		printf "\n(Press Ctrl-C to stop server + ngrok)\n"
		# flush output then sleep
		sleep "$sleep_sec"
	done
}

if $DO_SERVER; then
	# Ensure log file exists
	touch uvicorn.log
	if [ "$DO_NO_UI" = true ]; then
		echo "Services started in background (no-ui mode)."
		if [ -f uvicorn.pid ]; then
			echo "Uvicorn pid: $(cat uvicorn.pid)"
		fi
		if [ -f ngrok.cid ]; then
			echo "ngrok container id: $(cat ngrok.cid)"
		else
			NGROK_CID=$(docker ps -q -f name=mcp_ngrok 2>/dev/null || true)
			if [ -n "$NGROK_CID" ]; then
				echo "ngrok container id: $NGROK_CID"
			fi
		fi
		echo "Uvicorn logs: uvicorn.log"
		echo "Follow ngrok logs: docker logs -f mcp_ngrok"
		exit 0
	fi
	render_ui
	# when render_ui exits, run cleanup
	cleanup
else
	# no server to render; if only ngrok started, just print info and exit
	if [ "$DO_NO_UI" = true ]; then
		echo "No server process to show. ngrok started (if requested)."
		if [ -f ngrok.cid ]; then
			echo "ngrok container id: $(cat ngrok.cid)"
		fi
		exit 0
	fi
	echo "No server process to show. ngrok started (if requested)."
fi

wwdswddswds