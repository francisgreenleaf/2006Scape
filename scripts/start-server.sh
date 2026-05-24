#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/launcher-common.sh"

ROOT_DIR="$(launcher_repo_root)"
JAVA_BIN="$(launcher_java)"
SERVER_DIR="$ROOT_DIR/2006Scape Server"
SERVER_JAR="$SERVER_DIR/target/server-1.0-jar-with-dependencies.jar"
CONFIG_FILE="$(launcher_server_config "$ROOT_DIR")"
RUN_DIR="${SERVER_RUN_DIR:-/tmp/2006scape-run}"

if [[ ! -f "$SERVER_JAR" ]]; then
    echo "Server jar is missing; building first..."
    "$SCRIPT_DIR/build-local.sh"
fi

launcher_require_file "$CONFIG_FILE" "Server config not found: $CONFIG_FILE"

RUN_JAR="$SERVER_JAR"
if [[ "${SERVER_RUN_FROM_TARGET:-0}" != "1" ]]; then
    mkdir -p "$RUN_DIR"
    RUN_JAR="$RUN_DIR/server-$(date +%Y%m%d-%H%M%S)-$$.jar"
    cp "$SERVER_JAR" "$RUN_JAR"
fi

SERVER_JAVA_OPTS_ARRAY=()
if [[ -n "${SERVER_JAVA_OPTS:-}" ]]; then
    read -r -a SERVER_JAVA_OPTS_ARRAY <<< "$SERVER_JAVA_OPTS"
fi

cd "$SERVER_DIR"
echo "Starting 2006Scape server from $SERVER_DIR"
echo "Using server config: $CONFIG_FILE"
if [[ "$RUN_JAR" != "$SERVER_JAR" ]]; then
    echo "Running immutable server jar copy: $RUN_JAR"
fi
if (( ${#SERVER_JAVA_OPTS_ARRAY[@]} > 0 )); then
    exec "$JAVA_BIN" "${SERVER_JAVA_OPTS_ARRAY[@]}" -jar "$RUN_JAR" -c "$CONFIG_FILE" "$@"
fi
exec "$JAVA_BIN" -jar "$RUN_JAR" -c "$CONFIG_FILE" "$@"
