#!/usr/bin/env bash
set -euo pipefail

# Cleaner launcher for Quitto MCP
# - detects apt/dnf (optional)
# - creates virtualenv `.venv` and installs `requirements.txt`
# - starts uvicorn (index:app) on 127.0.0.1:3333
# - optionally starts ngrok (Docker)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

REQ_FILE="requirements.txt"
VENV_DIR=".venv"
ENV_FILE=".env"

# Load .env into environment if present
if [ -f "$ENV_FILE" ]; then
	echo "Loading environment variables from $ENV_FILE"
	set -o allexport
	# shellcheck disable=SC1090
	source "$ENV_FILE"
	set +o allexport
fi

# Default host/port
UVICORN_HOST="127.0.0.1"
UVICORN_PORT="3333"

# Default number of uvicorn workers (use all CPUs). Cap to a sane default to avoid fork storms.
DETECTED_CPUS=$(nproc 2>/dev/null || echo 1)
WORKERS="$DETECTED_CPUS"
# Cap workers to at most 4 unless user overrides via UVICORN_WORKERS env var
if [ -n "${UVICORN_WORKERS:-}" ]; then
	WORKERS="$UVICORN_WORKERS"
else
	if [ "$DETECTED_CPUS" -gt 4 ] 2>/dev/null; then
		WORKERS=4
	fi
fi

# Read ngrok vars from environment (may come from .env)
NGROK_TOKEN="${NGROK_AUTHTOKEN:-}"
NGROK_URL="${NGROK_URL:-}"

detect_pkg_mgr(){
	if command -v apt-get >/dev/null 2>&1; then echo apt;
	elif command -v dnf >/dev/null 2>&1; then echo dnf;
	else echo none; fi
}

# ---------- Helper functions (moved up so they are defined before use) ----------

# Stop and remove existing ngrok container if present (force restart behavior)
stop_ngrok_container(){
	EXISTING_CID=$(docker ps -a -q -f name=mcp_ngrok 2>/dev/null || true)
	if [ -n "$EXISTING_CID" ]; then
		echo "Stopping and removing existing ngrok container(s): $EXISTING_CID"
		docker stop mcp_ngrok >/dev/null 2>&1 || true
		docker rm -f mcp_ngrok >/dev/null 2>&1 || true
		rm -f ngrok.cid || true
	fi
}

# Stop any running uvicorn process (by pidfile or by searching process list)
stop_uvicorn_if_running(){
	if [ -f uvicorn.pid ]; then
		PID=$(cat uvicorn.pid 2>/dev/null || true)
		if [ -n "$PID" ] && kill -0 "$PID" >/dev/null 2>&1; then
			echo "Stopping existing uvicorn (pid=$PID)"
			kill "$PID" >/dev/null 2>&1 || true
			sleep 1
			if kill -0 "$PID" >/dev/null 2>&1; then
				echo "uvicorn did not exit, killing forcefully"
				kill -9 "$PID" >/dev/null 2>&1 || true
			fi
		fi
		rm -f uvicorn.pid || true
	fi

	# Also try to find any uvicorn processes matching index:app and kill them
	PIDS=$(pgrep -f "uvicorn.*index:app" || true)
	for P in $PIDS; do
		if [ -n "$P" ] && kill -0 "$P" >/dev/null 2>&1; then
			echo "Killing stray uvicorn process $P"
			kill "$P" >/dev/null 2>&1 || true
			sleep 1
			if kill -0 "$P" >/dev/null 2>&1; then
				kill -9 "$P" >/dev/null 2>&1 || true
			fi
		fi
	done
}

# Kill any process listening on a TCP port (used to ensure port is free)
kill_process_on_port(){
	PORT="$1"
	if [ -z "$PORT" ]; then
		return 0
	fi
	echo "Checking for processes listening on port $PORT..."
	PIDS=""
	if command -v lsof >/dev/null 2>&1; then
		PIDS=$(lsof -ti ":${PORT}" 2>/dev/null || true)
	else
		# fallback to ss+awk to extract pids
		PIDS=$(ss -ltnp 2>/dev/null | awk -v port=":${PORT}" '$4 ~ port { split($7,a,","); for(i in a) if(a[i] ~ /pid=/) { sub(/pid=/,"",a[i]); split(a[i],b,";"); print b[1]} }' || true)
	fi
	for P in $PIDS; do
		if [ -n "$P" ] && kill -0 "$P" >/dev/null 2>&1; then
			echo "Killing process $P listening on port $PORT"
			kill "$P" >/dev/null 2>&1 || true
			sleep 1
			if kill -0 "$P" >/dev/null 2>&1; then
				echo "Process $P did not exit, killing -9"
				kill -9 "$P" >/dev/null 2>&1 || true
			fi
		fi
	done
}

# Truncate uvicorn log file to start fresh
clear_uvicorn_log(){
	if [ -f uvicorn.log ]; then
		: > uvicorn.log
		echo "Cleared uvicorn.log"
	else
		touch uvicorn.log
	fi
}

# ---------- end moved helpers ----------

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

# Start uvicorn. If FOREGROUND mode is requested, run in foreground so logs appear live.
start_uvicorn(){
	echo "Starting uvicorn on ${UVICORN_HOST}:${UVICORN_PORT} (foreground=${FOREGROUND}, workers=${WORKERS})..."
	# ensure venv is active
	# shellcheck disable=SC1090
	source "$VENV_DIR/bin/activate" || true

	if [ "$FOREGROUND" = true ]; then
		# Clear logs before starting so the TUI shows fresh output
		clear_uvicorn_log || true
		# run single-process in foreground so user sees logs directly and can Ctrl-C to stop
		python -m uvicorn index:app --host "$UVICORN_HOST" --port "$UVICORN_PORT" --proxy-headers --log-level info
	else
		# background (production-style): run with multiple workers, write logs to uvicorn.log
		nohup stdbuf -oL python -m uvicorn index:app --host "$UVICORN_HOST" --port "$UVICORN_PORT" --workers "$WORKERS" --proxy-headers --log-level info > uvicorn.log 2>&1 &
		echo $! > uvicorn.pid
		echo "Uvicorn started (pid=$(cat uvicorn.pid)), logs -> uvicorn.log"
	fi
}

# Start uvicorn in the background as a single-process (used by the TUI)
start_uvicorn_background_single(){
	echo "Starting uvicorn (single-process background) on ${UVICORN_HOST}:${UVICORN_PORT}..."
	# ensure venv is active
	# shellcheck disable=SC1090
	source "$VENV_DIR/bin/activate" || true
	clear_uvicorn_log || true
	nohup stdbuf -oL python -m uvicorn index:app --host "$UVICORN_HOST" --port "$UVICORN_PORT" --proxy-headers --log-level info > uvicorn.log 2>&1 &
	echo $! > uvicorn.pid
	echo "Uvicorn started (pid=$(cat uvicorn.pid)), logs -> uvicorn.log"
}

# Interactive TUI: clear terminal before running server, allow start/stop ngrok and uvicorn,
# show ngrok public URL (if available) and tail logs. Keys: s=start, S=stop, n=ngrok start/stop,
# l=tail logs, q=quit
interactive_tui(){
	trap 'stty sane; echo; cleanup; exit' INT TERM
	while true; do
		clear
		echo "================== Quitto MCP — Interactive TUI =================="
		# uvicorn status
		if [ -f uvicorn.pid ]; then
			PID=$(cat uvicorn.pid 2>/dev/null || true)
			if [ -n "$PID" ] && kill -0 "$PID" >/dev/null 2>&1; then
				echo "Uvicorn: running (pid=$PID)"
			else
				echo "Uvicorn: not running (stale pid)"
			fi
		else
			echo "Uvicorn: not running"
		fi

		# ngrok public url
		NG_PUBLIC=""
		if [ -n "$NGROK_URL" ]; then
			NG_PUBLIC="$NGROK_URL"
		fi
		if command -v curl >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
			API=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null || true)
			if [ -n "$API" ]; then
				NG_PUBLIC=$(echo "$API" | python3 -c 'import sys,json; s=sys.stdin.read(); print("") if not s.strip() else (json.loads(s).get("tunnels",[])[0].get("public_url",""))')
			fi
		fi
		if [ -n "$NG_PUBLIC" ]; then
			echo "ngrok: running -> $NG_PUBLIC"
		else
			echo "ngrok: not running / no public URL"
		fi

		echo
		echo "Last uvicorn log lines (concise):"
		if [ -f uvicorn.log ]; then
			tail -n 12 uvicorn.log | sed -n '1,200p'
		else
			echo "(no uvicorn.log yet)"
		fi

		echo
		echo "Controls: s=start server, S=stop server, n=toggle ngrok, l=view logs, q=quit"
		read -r -n 1 KEY || true
		echo
		case "${KEY:-}" in
			s|S)
				if [ "${KEY}" = "s" ]; then
					echo "Starting uvicorn (background single-process)..."
					stop_uvicorn_if_running || true
					start_uvicorn_background_single || true
				else
					echo "Stopping uvicorn..."
					stop_uvicorn_if_running || true
				fi
				sleep 1
				;;
			n)
				NG_CID=$(docker ps -q -f name=mcp_ngrok 2>/dev/null || true)
				if [ -n "$NG_CID" ]; then
					echo "Stopping ngrok container..."
					stop_ngrok_container || true
				else
					echo "Starting ngrok (detached)..."
					start_ngrok_docker || true
				fi
				sleep 1
				;;
			l)
				if [ -f uvicorn.log ]; then
					stty sane
					less +F uvicorn.log || true
				else
					echo "No uvicorn.log to view. Press Enter to continue."
					read -r
				fi
				;;
			q|Q)
				cleanup
				exit 0
				;;
			*)
				# ignore
				;;
		esac
	done
}

# Minimal TUI: show concise status and a short tail of logs. Keys: q=quit, v=view full logs
tui_loop(){
	# ensure terminal is sane
	trap 'stty sane; echo; cleanup; exit' INT TERM
	while true; do
		clear
		echo "================== Quitto MCP — Status =================="
		# uvicorn status
		if [ -f uvicorn.pid ]; then
			PID=$(cat uvicorn.pid 2>/dev/null || true)
			if [ -n "$PID" ] && kill -0 "$PID" >/dev/null 2>&1; then
				echo "Uvicorn: running (pid=$PID)"
			else
				echo "Uvicorn: not running (stale pid)"
			fi
		else
			echo "Uvicorn: not running"
		fi

		# ngrok status
		NG_CID=""
		if [ -f ngrok.cid ]; then
			NG_CID=$(cat ngrok.cid 2>/dev/null || true)
		fi
		if [ -n "$NG_CID" ] && docker ps -q -f id="$NG_CID" >/dev/null 2>&1; then
			echo "ngrok: running (container id=${NG_CID})"
		elif docker ps -q -f name=mcp_ngrok >/dev/null 2>&1 && [ -n "$(docker ps -q -f name=mcp_ngrok)" ]; then
			echo "ngrok: running (container name=mcp_ngrok)"
		else
			echo "ngrok: not running"
		fi

		echo
		echo "Last uvicorn log lines ( concise ):"
		if [ -f uvicorn.log ]; then
			tail -n 12 uvicorn.log | sed -n '1,200p'
		else
			echo "(no uvicorn.log yet)"
		fi

		echo
		echo "Controls: q=quit (stop services), v=view full uvicorn log (press Ctrl-C to return)"
		# read a single character with timeout to refresh the display
		read -r -t 2 -n 1 KEY || true
		if [ "${KEY:-}" = "q" ] || [ "${KEY:-}" = "Q" ]; then
			echo "Quitting..."
			cleanup
			exit 0
		elif [ "${KEY:-}" = "v" ] || [ "${KEY:-}" = "V" ]; then
			if [ -f uvicorn.log ]; then
				stty sane
				less +F uvicorn.log || true
				# re-enable raw mode behavior after pager exits
			else
				echo "No uvicorn.log to view. Press Enter to continue."
				read -r
			fi
		fi
	done
}

# Wait for the server to accept HTTP connections before proceeding.
wait_for_server(){
	local retries=30
	local i=0
	echo "Waiting for server to become available at http://${UVICORN_HOST}:${UVICORN_PORT}..."
	while [ $i -lt $retries ]; do
		if command -v curl >/dev/null 2>&1; then
			if curl -sSf "http://${UVICORN_HOST}:${UVICORN_PORT}/health" >/dev/null 2>&1 || curl -sSf "http://${UVICORN_HOST}:${UVICORN_PORT}/" >/dev/null 2>&1; then
				echo "Server responded"
				return 0
			fi
		else
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
	# Start ngrok detached and write container id to ngrok.cid. Always prefer detached run so it won't block the terminal.
	echo "Starting ngrok (detached)..."
	docker pull ngrok/ngrok:latest || true
	EXISTING_CID=$(docker ps -a -q -f name=mcp_ngrok 2>/dev/null || true)
	if [ -n "$EXISTING_CID" ]; then
		STATUS=$(docker inspect --format '{{.State.Status}}' mcp_ngrok 2>/dev/null || true)
		if [ "$STATUS" = "running" ]; then
			RUNNING_CID=$(docker ps -q -f name=mcp_ngrok 2>/dev/null || true)
			echo "ngrok container 'mcp_ngrok' is already running."
			echo "$RUNNING_CID" > ngrok.cid
			return
		else
			if [ "$DO_KEEP_NGROK" = true ]; then
				docker start mcp_ngrok >/dev/null 2>&1 || true
				docker ps -q -f name=mcp_ngrok >/dev/null 2>&1 && docker ps -q -f name=mcp_ngrok > ngrok.cid || true
				echo "ngrok started (existing container)."
				return
			else
				docker rm -f mcp_ngrok >/dev/null 2>&1 || true
			fi
		fi
	fi
	# Build docker run arguments
	RUN_ARGS=( -d --name mcp_ngrok )
	# expose host networking only when explicitly desired; prefer default bridge unless NGROK_NEEDS_HOST_NET is true
	if [ "${NGROK_NEEDS_HOST_NET:-false}" = "true" ]; then
		RUN_ARGS+=( --net=host )
	fi
	if [ -f "$ENV_FILE" ]; then
		RUN_ARGS+=( --env-file "$ENV_FILE" )
	fi
	if [ -n "$NGROK_TOKEN" ]; then
		RUN_ARGS+=( -e NGROK_AUTHTOKEN="$NGROK_TOKEN" )
	fi
	if [ -n "$NGROK_URL" ]; then
		CID=$(docker run "${RUN_ARGS[@]}" ngrok/ngrok:latest http --url="$NGROK_URL" "$UVICORN_PORT")
	else
		CID=$(docker run "${RUN_ARGS[@]}" ngrok/ngrok:latest http "$UVICORN_PORT")
	fi
	if [ -n "$CID" ]; then
		echo "$CID" > ngrok.cid
		echo "ngrok started detached (container id=$CID)"
	else
		echo "Failed to start ngrok container"
	fi
}

show_help(){
	cat <<EOF
Usage: ./run.sh [--install-system] [--ngrok] [--foreground]

Options:
	--install-system   Attempt to install system packages via apt or dnf (requires sudo)
	--ngrok            Start ngrok (Docker) after launching uvicorn. Requires NGROK_AUTHTOKEN env var.
	--no-ui            Do not start the interactive TUI; print status and return to shell
	--keep-ngrok       Do not stop ngrok container on Ctrl-C (leave running)
	--foreground       Run uvicorn in foreground (see logs live in terminal)
	--tui              Start an interactive TUI (clean terminal, control server/ngrok, view logs)
	--help             Show this help

Environment:
	NGROK_AUTHTOKEN    ngrok authtoken (or pass to script env)
	NGROK_URL          Optional ngrok URL/subdomain
	HOST               Host to bind (default 127.0.0.1)
	PORT               Port to bind (default 3333)

Examples:
	NGROK_AUTHTOKEN=TOKEN ./run.sh --install-system --ngrok
	./run.sh --foreground
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
	show_help; exit 0
fi

# Defaults and flags
DO_NGROK=false
DO_SERVER=false
DO_INSTALL=false
DO_KEEP_NGROK=false
DO_NO_UI=false
DO_TUI=false
# Run uvicorn in foreground by default so logs are visible and the terminal is occupied
FOREGROUND=true
CLEAN_PID=false
NGROK_STARTED=false

if [ "$#" -eq 0 ]; then
	DO_SERVER=true
	DO_NGROK=true
else
	for arg in "$@"; do
		case "$arg" in
			--ngrok) DO_NGROK=true ;;
			--server) DO_SERVER=true ;;
			--tui) DO_TUI=true ;;
			--no-ui) DO_NO_UI=true ;;
			--install-system) DO_INSTALL=true ;;
			--keep-ngrok) DO_KEEP_NGROK=true ;;
			--foreground) FOREGROUND=true ;;
			--clean-pid) CLEAN_PID=true ;;
		esac
	done
	if [ "$DO_SERVER" = false ] && [ "$DO_NGROK" = false ]; then
		DO_SERVER=true
		DO_NGROK=true
	fi
fi

if $DO_INSTALL; then
	install_system_pkgs
fi

if [ "${DO_SERVER}" = true ]; then
		create_venv_and_install

	# helper: remove stale pid file if it points to a non-running process
	remove_stale_pid(){
		if [ -f uvicorn.pid ]; then
			PID=$(cat uvicorn.pid 2>/dev/null || true)
			if [ -n "$PID" ] && ! kill -0 "$PID" >/dev/null 2>&1; then
				echo "Removing stale uvicorn.pid (pid=$PID not running)"
				rm -f uvicorn.pid
			fi
		fi
	}

	# If user requested clean or to avoid stale pid blocking start, remove it now
	if [ "$CLEAN_PID" = true ]; then
		remove_stale_pid
	fi
		# if starting in foreground, run uvicorn directly (this process will not return)
		if [ "$FOREGROUND" = true ]; then
		# if ngrok requested, stop existing and start it first (detached)
		if [ "${DO_NGROK}" = true ]; then
			stop_ngrok_container
			start_ngrok_docker
			NGROK_STARTED=true
		fi
		# stop any running uvicorn and ensure no stale pid prevents foreground start
		stop_uvicorn_if_running || true
		remove_stale_pid || true
			if [ "$DO_TUI" = true ]; then
				echo "TUI mode: not starting uvicorn automatically. Use the TUI to start/stop the server."
			else
				start_uvicorn
			fi
		# start_uvicorn in foreground will block here
	else
		# background path: ensure existing services are stopped and start fresh
		if [ "${DO_NGROK}" = true ]; then
			stop_ngrok_container
		fi
		stop_uvicorn_if_running || true
		remove_stale_pid || true
			if [ "$DO_TUI" = true ]; then
				echo "TUI mode: not starting uvicorn automatically. Use the TUI to start/stop the server."
			else
				start_uvicorn
			fi
	fi
else
	echo "Server start skipped (--server not set)."
fi

# If requested to start ngrok, wait until server is up (if server was started here)
if [ "${DO_NGROK}" = true ]; then
	if $DO_SERVER && [ "$FOREGROUND" = false ]; then
		if wait_for_server; then
			echo "Server is up — starting ngrok..."
		else
			echo "Warning: server did not become ready in time. Proceeding to start ngrok anyway."
		fi
	fi
	if [ "$NGROK_STARTED" = true ]; then
		echo "ngrok already started earlier; skipping duplicate start"
	else
			start_ngrok_docker
	fi
else
	echo "ngrok start skipped (--ngrok not set)."
	echo "To start ngrok only: ./run.sh --ngrok"
fi

# Cleanup function to stop uvicorn and ngrok container on SIGINT/SIGTERM
cleanup(){
	echo "\nShutting down..."
	# stop uvicorn if started in background
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

# Stop and remove existing ngrok container if present (force restart behavior)
stop_ngrok_container(){
	EXISTING_CID=$(docker ps -a -q -f name=mcp_ngrok 2>/dev/null || true)
	if [ -n "$EXISTING_CID" ]; then
		echo "Stopping and removing existing ngrok container(s): $EXISTING_CID"
		docker stop mcp_ngrok >/dev/null 2>&1 || true
		docker rm -f mcp_ngrok >/dev/null 2>&1 || true
		rm -f ngrok.cid || true
	fi
}

# Stop any running uvicorn process (by pidfile or by searching process list)
stop_uvicorn_if_running(){
	if [ -f uvicorn.pid ]; then
		PID=$(cat uvicorn.pid 2>/dev/null || true)
		if [ -n "$PID" ] && kill -0 "$PID" >/dev/null 2>&1; then
			echo "Stopping existing uvicorn (pid=$PID)"
			kill "$PID" >/dev/null 2>&1 || true
			sleep 1
			if kill -0 "$PID" >/dev/null 2>&1; then
				echo "uvicorn did not exit, killing forcefully"
				kill -9 "$PID" >/dev/null 2>&1 || true
			fi
		fi
		rm -f uvicorn.pid || true
	fi

	# Also try to find any uvicorn processes matching index:app and kill them
	PIDS=$(pgrep -f "uvicorn.*index:app" || true)
	for P in $PIDS; do
		if [ -n "$P" ] && kill -0 "$P" >/dev/null 2>&1; then
			echo "Killing stray uvicorn process $P"
			kill "$P" >/dev/null 2>&1 || true
			sleep 1
			if kill -0 "$P" >/dev/null 2>&1; then
				kill -9 "$P" >/dev/null 2>&1 || true
			fi
		fi
	done
}

# Kill any process listening on a TCP port (used to ensure port is free)
kill_process_on_port(){
	PORT="$1"
	if [ -z "$PORT" ]; then
		return 0
	fi
	echo "Checking for processes listening on port $PORT..."
	PIDS=""
	if command -v lsof >/dev/null 2>&1; then
		PIDS=$(lsof -ti ":${PORT}" 2>/dev/null || true)
	else
		# fallback to ss+awk to extract pids
		PIDS=$(ss -ltnp 2>/dev/null | awk -v port=":${PORT}" '$4 ~ port { split($7,a,","); for(i in a) if(a[i] ~ /pid=/) { sub(/pid=/,"",a[i]); split(a[i],b,";"); print b[1]} }' || true)
	fi
	for P in $PIDS; do
		if [ -n "$P" ] && kill -0 "$P" >/dev/null 2>&1; then
			echo "Killing process $P listening on port $PORT"
			kill "$P" >/dev/null 2>&1 || true
			sleep 1
			if kill -0 "$P" >/dev/null 2>&1; then
				echo "Process $P did not exit, killing -9"
				kill -9 "$P" >/dev/null 2>&1 || true
			fi
		fi
	done
}

trap cleanup INT TERM

# Small TUI: banner, status and recent logs. Refreshes until interrupted.
render_ui(){
	local sleep_sec="0.5"
	while true; do
		printf '\033[2J\033[H'
		printf '%b\n' '\033[1;36m============================================================='
		printf '%b\n' '                       QUITTO MCP SERVER                       '
		printf '%b\n' '=============================================================\033[0m'

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

		NGROK_CID=$(docker ps -q -f name=mcp_ngrok 2>/dev/null || true)
		if [ -n "$NGROK_CID" ]; then
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

		echo
		printf '%b\n' 'ngrok recent logs (last 6 lines):'
		if [ -n "$NGROK_CID" ]; then
			docker logs --tail 6 mcp_ngrok 2>/dev/null | sed -e 's/^/  /' || echo "  (no ngrok logs yet)"
		else
			echo "  (ngrok not running)"
		fi

		printf '%b\n' '-------------------------------------------------------------'
		printf '%b\n' 'Combined recent logs (uvicorn + ngrok):'
		(
			if [ -f uvicorn.log ]; then
				tail -n 20 uvicorn.log
			fi
			if [ -n "$NGROK_CID" ]; then
				docker logs --tail 20 mcp_ngrok 2>/dev/null || true
			fi
		) | sed -e 's/^/  /' | tail -n 30 || true

		printf "\n(Press Ctrl-C to stop server + ngrok)\n"
		sleep "$sleep_sec"
	done
}

if [ "${DO_SERVER}" = true ]; then
	# Ensure log file exists for background mode
	touch uvicorn.log || true
	if [ -f uvicorn.pid ]; then
		# keep previous PID if present
		true
	fi
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
	# If running in background mode, show the TUI. If foreground, start_uvicorn already blocked.
	if [ "$FOREGROUND" = false ]; then
		render_ui
		cleanup
	fi
else
	if [ "$DO_NO_UI" = true ]; then
		echo "No server process to show. ngrok started (if requested)."
		if [ -f ngrok.cid ]; then
			echo "ngrok container id: $(cat ngrok.cid)"
		fi
		exit 0
	fi
	echo "No server process to show. ngrok started (if requested)."
fi
