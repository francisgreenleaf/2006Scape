#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/launcher-common.sh"

ROOT_DIR="$(launcher_repo_root)"
JAVA_BIN="$(launcher_java)"
CLIENT_DIR="$ROOT_DIR/2006Scape Client"
CLIENT_JAR="$CLIENT_DIR/target/client-1.0-jar-with-dependencies.jar"

if [[ ! -f "$CLIENT_JAR" ]]; then
    echo "Client jar is missing; building first..."
    "$SCRIPT_DIR/build-local.sh"
fi

cd "$CLIENT_DIR"
echo "Launching 2006Scape client against localhost..."
exec "$JAVA_BIN" -jar "$CLIENT_JAR" -local -s localhost "$@"
