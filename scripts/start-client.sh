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

CLIENT_JAVA_OPTS_ARRAY=()
if [[ -n "${CLIENT_JAVA_OPTS:-}" ]]; then
    read -r -a CLIENT_JAVA_OPTS_ARRAY <<< "$CLIENT_JAVA_OPTS"
fi

if [[ "${CLIENT_SINGLE_INSTANCE:-1}" != "0" ]] && command -v pgrep >/dev/null 2>&1; then
    CLIENT_JAR_PATTERN="[$(printf '%s' "${CLIENT_JAR:0:1}")]${CLIENT_JAR:1}"
    EXISTING_CLIENT_PIDS="$(pgrep -f "$CLIENT_JAR_PATTERN" || true)"

    if [[ -n "$EXISTING_CLIENT_PIDS" ]]; then
        if [[ "${CLIENT_REPLACE_EXISTING:-0}" == "1" ]]; then
            echo "Stopping existing 2006Scape client process(es): $EXISTING_CLIENT_PIDS"
            while IFS= read -r pid; do
                [[ -n "$pid" ]] && kill "$pid" >/dev/null 2>&1 || true
            done <<< "$EXISTING_CLIENT_PIDS"
            sleep 2
        else
            echo "A 2006Scape client is already running for this checkout: $EXISTING_CLIENT_PIDS" >&2
            echo "Set CLIENT_REPLACE_EXISTING=1 to stop it first, or CLIENT_SINGLE_INSTANCE=0 to allow another client." >&2
            exit 1
        fi
    fi
fi

cd "$CLIENT_DIR"
echo "Launching 2006Scape client against localhost..."
if (( ${#CLIENT_JAVA_OPTS_ARRAY[@]} > 0 )); then
    exec "$JAVA_BIN" "${CLIENT_JAVA_OPTS_ARRAY[@]}" -jar "$CLIENT_JAR" -local -s localhost "$@"
fi
exec "$JAVA_BIN" -jar "$CLIENT_JAR" -local -s localhost "$@"
