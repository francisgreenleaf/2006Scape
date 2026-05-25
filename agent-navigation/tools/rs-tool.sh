#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: agent-navigation/tools/rs-tool.sh TOOL [JSON_ARGUMENTS]

Call a 2006Scape rs bridge tool through the active local session.

Examples:
  agent-navigation/tools/rs-tool.sh observe_state '{}'
  agent-navigation/tools/rs-tool.sh walk_to_tile_until_arrived '{"x":3222,"y":3218,"height":0}'

Environment:
  RS_PROFILE              Select a profile-specific session file
  RSBRIDGE_SESSION_FILE  Override session file path
  RSBRIDGE_EXPECT_PLAYER Validate the session player before sending the tool call
  RSBRIDGE_TOOL_URL      Override tool URL, default http://127.0.0.1:43610/agent/tool
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 1 ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROFILE="${RS_PROFILE:-${RSBRIDGE_PROFILE:-}}"
if [[ -n "${RSBRIDGE_SESSION_FILE:-}" ]]; then
  SESSION_FILE="$RSBRIDGE_SESSION_FILE"
elif [[ -n "$PROFILE" ]]; then
  SAFE_PROFILE="$(python3 - "$PROFILE" <<'PY'
import sys
text = "".join(ch for ch in sys.argv[1].strip().lower() if ch.isalnum() or ch in ("-", "_"))
print(text or "default")
PY
)"
  if [[ "$SAFE_PROFILE" == "mrflame" ]]; then
    SESSION_FILE="$ROOT/.local/rsbridge-session.json"
  else
    SESSION_FILE="$ROOT/.local/rsbridge-session-$SAFE_PROFILE.json"
  fi
else
  SESSION_FILE="$ROOT/.local/rsbridge-session.json"
fi
EXPECT_PLAYER="${RSBRIDGE_EXPECT_PLAYER:-$PROFILE}"
TOOL_URL="${RSBRIDGE_TOOL_URL:-http://127.0.0.1:43610/agent/tool}"
TOOL="$1"
if [[ $# -ge 2 ]]; then
  ARGS_JSON="$2"
else
  ARGS_JSON="{}"
fi

if [[ ! -f "$SESSION_FILE" ]]; then
  echo "bridge session file not found: $SESSION_FILE" >&2
  exit 1
fi

token="$(python3 - "$SESSION_FILE" "$EXPECT_PLAYER" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)
expected = " ".join(sys.argv[2].strip().lower().replace("_", " ").split())
actual = " ".join(str(data.get("playerName") or "").strip().lower().replace("_", " ").split())
if expected and actual and expected != actual:
    raise SystemExit("session player mismatch: expected {} but session is {}".format(expected, actual))
print(data["token"])
PY
)"

payload="$(python3 - "$TOOL" "$ARGS_JSON" <<'PY'
import json
import sys

tool = sys.argv[1]
try:
    args = json.loads(sys.argv[2])
except json.JSONDecodeError as exc:
    raise SystemExit("invalid JSON arguments: {}".format(exc))
if not isinstance(args, dict):
    raise SystemExit("JSON arguments must be an object")
print(json.dumps({"tool": tool, "arguments": args}, separators=(",", ":")))
PY
)"

python3 "$SCRIPT_DIR/usage_log.py" --tool rs-tool --surface full "$TOOL" "$ARGS_JSON" >/dev/null 2>&1 || true

curl -sS -X POST "$TOOL_URL" \
  -H "X-Agent-Token: $token" \
  -H 'Content-Type: application/json' \
  -d "$payload"
