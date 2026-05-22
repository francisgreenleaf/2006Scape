#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/launcher-common.sh"

ROOT_DIR="$(launcher_repo_root)"
JAVA_BIN="$(launcher_java)"
SERVER_DIR="$ROOT_DIR/2006Scape Server"
SERVER_JAR="$SERVER_DIR/target/server-1.0-jar-with-dependencies.jar"
CONFIG_FILE="$(launcher_server_config "$ROOT_DIR")"

if [[ ! -f "$SERVER_JAR" ]]; then
    echo "Server jar is missing; building first..."
    "$SCRIPT_DIR/build-local.sh"
fi

launcher_require_file "$CONFIG_FILE" "Server config not found: $CONFIG_FILE"

cd "$SERVER_DIR"
echo "Starting 2006Scape server from $SERVER_DIR"
echo "Using server config: $CONFIG_FILE"
exec "$JAVA_BIN" -jar "$SERVER_JAR" -c "$CONFIG_FILE" "$@"
