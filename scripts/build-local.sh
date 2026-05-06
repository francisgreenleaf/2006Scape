#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/launcher-common.sh"

ROOT_DIR="$(launcher_repo_root)"
MAVEN_BIN="$(launcher_maven)"

cd "$ROOT_DIR"
echo "Building 2006Scape with Maven..."
exec "$MAVEN_BIN" -B clean install "$@"
