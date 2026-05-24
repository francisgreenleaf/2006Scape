#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: agent-navigation/tools/capture-cardinal-screenshots.sh [options]

Capture compact 2006Scape client screenshots from four camera angles.

Options:
  --prefix NAME              Filename prefix, default: cardinal
  --pid PID                  Java client process id; defaults to .local/client.pid
  --native-size              Capture at 765x503 output size, default
  --max-size WxH             Capture at a bounded size instead of native-size
  --quarter-turn-seconds N   Seconds to hold right-arrow between angles, default: 0.90
  --settle-seconds N         Delay after camera changes before capture, default: 0.35
  --skip-face-north          Do not click the compass before the first capture
  --leave-camera             Do not face north again after the last capture
  --dry-run                  Print the planned client pid/options without capturing
  -h, --help                 Show this help

The default output is four PNGs under agent-navigation/screenshots/captures/<date>/:
north, east, south, and west. Output is a final JSON summary.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CAPTURE="$SCRIPT_DIR/capture-client-screenshot.sh"
PID_FILE="$ROOT/.local/client.pid"
PREFIX="cardinal"
CLIENT_PID=""
NATIVE_SIZE=1
MAX_SIZE=""
QUARTER_TURN_SECONDS="0.90"
SETTLE_SECONDS="0.35"
FACE_NORTH=1
RESTORE_NORTH=1
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      PREFIX="${2:?missing value for --prefix}"
      shift 2
      ;;
    --pid)
      CLIENT_PID="${2:?missing value for --pid}"
      shift 2
      ;;
    --native-size)
      NATIVE_SIZE=1
      MAX_SIZE=""
      shift
      ;;
    --max-size)
      MAX_SIZE="${2:?missing value for --max-size}"
      NATIVE_SIZE=0
      shift 2
      ;;
    --quarter-turn-seconds)
      QUARTER_TURN_SECONDS="${2:?missing value for --quarter-turn-seconds}"
      shift 2
      ;;
    --settle-seconds)
      SETTLE_SECONDS="${2:?missing value for --settle-seconds}"
      shift 2
      ;;
    --skip-face-north)
      FACE_NORTH=0
      shift
      ;;
    --leave-camera)
      RESTORE_NORTH=0
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$CLIENT_PID" && -f "$PID_FILE" ]]; then
  maybe_pid="$(tr -d '[:space:]' < "$PID_FILE")"
  if [[ "$maybe_pid" =~ ^[0-9]+$ ]]; then
    CLIENT_PID="$maybe_pid"
  fi
fi

if [[ -z "$CLIENT_PID" ]] && command -v pgrep >/dev/null 2>&1; then
  CLIENT_PID="$(pgrep -f 'client-1.0-jar-with-dependencies.jar' 2>/dev/null | head -n 1 || true)"
fi

if [[ -z "$CLIENT_PID" ]]; then
  echo "no running 2006Scape client pid found; try --pid or start the local runtime" >&2
  exit 1
fi

capture_args=(--pid "$CLIENT_PID")
if [[ "$NATIVE_SIZE" -eq 1 ]]; then
  capture_args+=(--native-size)
elif [[ -n "$MAX_SIZE" ]]; then
  capture_args+=(--max-size "$MAX_SIZE")
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  python3 - "$CLIENT_PID" "$PREFIX" "$NATIVE_SIZE" "$MAX_SIZE" "$QUARTER_TURN_SECONDS" "$SETTLE_SECONDS" <<'PY'
import json
import sys

pid, prefix, native_size, max_size, quarter, settle = sys.argv[1:]
print(json.dumps({
    "success": True,
    "dryRun": True,
    "clientPid": int(pid),
    "prefix": prefix,
    "outputSizing": "native-size" if native_size == "1" else max_size,
    "directions": ["north", "east", "south", "west"],
    "quarterTurnSeconds": float(quarter),
    "settleSeconds": float(settle),
}, sort_keys=True))
PY
  exit 0
fi

focus_client() {
  osascript - "$CLIENT_PID" <<'APPLESCRIPT' >/dev/null 2>&1 || true
on run argv
  set targetPid to item 1 of argv as integer
  tell application "System Events"
    set frontmost of (first process whose unix id is targetPid) to true
  end tell
end run
APPLESCRIPT
}

face_north() {
  osascript - "$CLIENT_PID" <<'APPLESCRIPT' >/dev/null 2>&1 || true
on run argv
  set targetPid to item 1 of argv as integer
  tell application "System Events"
    tell (first process whose unix id is targetPid)
      set frontmost to true
      if (count of windows) is 0 then return
      set p to position of window 1
      set s to size of window 1
    end tell
    set scaleFactor to (item 1 of s) / 765
    if scaleFactor < 1 then set scaleFactor to 1
    set titleOffset to (item 2 of s) - (503 * scaleFactor)
    if titleOffset < 0 or titleOffset > 80 then set titleOffset to 0
    set clickX to (item 1 of p) + (564 * scaleFactor)
    set clickY to (item 2 of p) + titleOffset + (23 * scaleFactor)
    click at {clickX as integer, clickY as integer}
  end tell
end run
APPLESCRIPT
  sleep "$SETTLE_SECONDS"
}

turn_right_quarter() {
  osascript - "$CLIENT_PID" "$QUARTER_TURN_SECONDS" <<'APPLESCRIPT' >/dev/null 2>&1 || true
on run argv
  set targetPid to item 1 of argv as integer
  set holdSeconds to item 2 of argv as real
  tell application "System Events"
    set frontmost of (first process whose unix id is targetPid) to true
    key down (key code 124)
    delay holdSeconds
    key up (key code 124)
  end tell
end run
APPLESCRIPT
  sleep "$SETTLE_SECONDS"
}

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

focus_client
if [[ "$FACE_NORTH" -eq 1 ]]; then
  face_north
fi

for direction in north east south west; do
  json="$("$CAPTURE" --prefix "$PREFIX-$direction" "${capture_args[@]}")"
  python3 - "$direction" "$json" >> "$tmp" <<'PY'
import json
import sys

direction = sys.argv[1]
payload = json.loads(sys.argv[2])
payload["direction"] = direction
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
PY
  if [[ "$direction" != "west" ]]; then
    turn_right_quarter
  fi
done

if [[ "$RESTORE_NORTH" -eq 1 ]]; then
  face_north
fi

python3 - "$tmp" "$CLIENT_PID" <<'PY'
import json
import sys
from pathlib import Path

records = [json.loads(line) for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]
print(json.dumps({
    "success": True,
    "clientPid": int(sys.argv[2]),
    "count": len(records),
    "directions": [record.get("direction") for record in records],
    "screenshots": records,
}, sort_keys=True))
PY
