#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: agent-navigation/tools/capture-client-screenshot.sh [options]

Capture the running 2006Scape Java client to a PNG and print JSON metadata.

Options:
  --prefix NAME       Filename prefix, default: client
  --output PATH       Exact PNG output path
  --pid PID           Java client process id to capture
  --native-size       Downsample to the classic 765x503 client size
  --max-size WxH      Downsample to fit inside WxH, preserving aspect ratio
  --full-screen       Capture the full desktop instead of the client window
  --no-focus          Do not focus the Java client before capture
  -h, --help          Show this help

The default mode finds a running client jar process, focuses it, reads its
front window bounds through System Events, and captures that rectangle.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PREFIX="client"
OUTPUT=""
CLIENT_PID=""
FULL_SCREEN=0
FOCUS=1
NATIVE_SIZE=0
MAX_SIZE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      PREFIX="${2:?missing value for --prefix}"
      shift 2
      ;;
    --output)
      OUTPUT="${2:?missing value for --output}"
      shift 2
      ;;
    --pid)
      CLIENT_PID="${2:?missing value for --pid}"
      shift 2
      ;;
    --native-size)
      NATIVE_SIZE=1
      shift
      ;;
    --max-size)
      MAX_SIZE="${2:?missing value for --max-size}"
      shift 2
      ;;
    --full-screen)
      FULL_SCREEN=1
      shift
      ;;
    --no-focus)
      FOCUS=0
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

if [[ -z "$OUTPUT" ]]; then
  day="$(date -u +%Y-%m-%d)"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out_dir="$ROOT/screenshots/captures/$day"
  mkdir -p "$out_dir"
  OUTPUT="$out_dir/${PREFIX}-${stamp}.png"
else
  mkdir -p "$(dirname "$OUTPUT")"
fi

client_pid="$CLIENT_PID"
if [[ -z "$client_pid" ]]; then
  client_pid="$(ps ax -o pid= -o command= | awk '
    /client-1\.0-jar-with-dependencies\.jar/ {
      cmd = $0
      sub(/^[[:space:]]*[0-9]+[[:space:]]+/, "", cmd)
      if (cmd ~ /^\/.*\/java[[:space:]]+-jar/ && pid == "") {
        pid = $1
      }
    }
    END {print pid}
  ')"
fi
if [[ -z "${client_pid:-}" ]]; then
  echo "no running 2006Scape client jar process found" >&2
  exit 1
fi

warning=""
rect=""

if [[ "$FOCUS" -eq 1 ]]; then
  osascript - "$client_pid" <<'APPLESCRIPT' >/dev/null 2>&1 || true
on run argv
  set targetPid to item 1 of argv as integer
  tell application "System Events"
    set frontmost of (first process whose unix id is targetPid) to true
  end tell
end run
APPLESCRIPT
  sleep 0.25
fi

if [[ "$FULL_SCREEN" -eq 0 ]]; then
  rect="$(osascript - "$client_pid" <<'APPLESCRIPT' 2>/dev/null || true
on run argv
  set targetPid to item 1 of argv as integer
  tell application "System Events"
    tell (first process whose unix id is targetPid)
      if (count of windows) is 0 then return ""
      set p to position of window 1
      set s to size of window 1
      return (item 1 of p as text) & "," & (item 2 of p as text) & "," & (item 1 of s as text) & "," & (item 2 of s as text)
    end tell
  end tell
end run
APPLESCRIPT
)"
fi

if [[ "$FULL_SCREEN" -eq 1 || -z "$rect" ]]; then
  if [[ "$FULL_SCREEN" -eq 0 ]]; then
    warning="client window bounds unavailable; captured full desktop"
  fi
  screencapture -x "$OUTPUT"
  mode="full-screen"
else
  screencapture -x -R "$rect" "$OUTPUT"
  mode="client-window"
fi

if [[ "$NATIVE_SIZE" -eq 1 ]]; then
  sips -z 503 765 "$OUTPUT" >/dev/null 2>&1 || true
elif [[ -n "$MAX_SIZE" ]]; then
  max_w="${MAX_SIZE%x*}"
  max_h="${MAX_SIZE#*x}"
  if [[ "$max_w" =~ ^[0-9]+$ && "$max_h" =~ ^[0-9]+$ ]]; then
    sips -Z "$max_w" "$OUTPUT" >/dev/null 2>&1 || true
    height_after="$(sips -g pixelHeight "$OUTPUT" 2>/dev/null | awk '/pixelHeight:/ {print $2}')"
    if [[ "${height_after:-0}" -gt "$max_h" ]]; then
      sips -Z "$max_h" "$OUTPUT" >/dev/null 2>&1 || true
    fi
  fi
fi

captured_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
dimensions="$(sips -g pixelWidth -g pixelHeight "$OUTPUT" 2>/dev/null | awk '''/pixelWidth:/ {w=$2} /pixelHeight:/ {h=$2} END {if (w && h) print w "x" h}''')"
python3 - "$OUTPUT" "$client_pid" "$mode" "$rect" "$captured_at" "$warning" "$dimensions" <<'PY'
import json
import sys

path, pid, mode, rect, captured_at, warning, dimensions = sys.argv[1:]
payload = {
    "success": True,
    "screenshot": path,
    "clientPid": int(pid),
    "mode": mode,
    "rect": rect or None,
    "capturedAt": captured_at,
}
if dimensions and "x" in dimensions:
    width, height = dimensions.split("x", 1)
    payload["pixelWidth"] = int(width)
    payload["pixelHeight"] = int(height)
if warning:
    payload["warning"] = warning
print(json.dumps(payload, sort_keys=True))
PY
