#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/launcher-common.sh"

SERVER_PORT="${SERVER_PORT:-43594}"
SERVER_START_TIMEOUT="${SERVER_START_TIMEOUT:-90}"
SERVER_PID=""

cleanup() {
    if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" >/dev/null 2>&1; then
        echo "Stopping local 2006Scape server..."
        kill "$SERVER_PID" >/dev/null 2>&1 || true
        wait "$SERVER_PID" >/dev/null 2>&1 || true
    fi
}

on_signal() {
    cleanup
    exit 130
}

wait_for_server() {
    local elapsed=0

    echo "Waiting for server on 127.0.0.1:$SERVER_PORT..."
    while (( elapsed < SERVER_START_TIMEOUT )); do
        if ! kill -0 "$SERVER_PID" >/dev/null 2>&1; then
            echo "Server exited before it was ready." >&2
            wait "$SERVER_PID"
            return 1
        fi

        if launcher_port_open "$SERVER_PORT"; then
            echo "Server is ready."
            return 0
        fi

        if ! command -v nc >/dev/null 2>&1 && (( elapsed >= 6 )); then
            echo "netcat is unavailable; continuing after ${elapsed}s startup wait."
            return 0
        fi

        sleep 1
        elapsed=$((elapsed + 1))
    done

    echo "Timed out waiting for server on 127.0.0.1:$SERVER_PORT." >&2
    return 1
}

trap cleanup EXIT
trap on_signal INT TERM

if launcher_port_open "$SERVER_PORT"; then
    echo "Port $SERVER_PORT is already in use. Stop the existing server or run ./scripts/start-client.sh to attach a client." >&2
    exit 1
fi

if [[ "${SKIP_BUILD:-}" != "1" ]]; then
    "$SCRIPT_DIR/build-local.sh"
fi

"$SCRIPT_DIR/start-server.sh" &
SERVER_PID=$!

wait_for_server
"$SCRIPT_DIR/start-client.sh" "$@"
