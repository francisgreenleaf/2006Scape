#!/usr/bin/env python3
"""Out-of-band local usage logging for agent-facing navigation tools."""

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
USAGE_DIR = ROOT / ".local" / "usage"
SENSITIVE_PARTS = ("token", "secret", "password", "passwd", "api_key", "apikey", "nonce")


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def disabled():
    return os.environ.get("AGENT_NAV_USAGE_LOG", "").lower() in ("0", "false", "no", "off")


def profile_name():
    return (
        os.environ.get("RS_PROFILE")
        or os.environ.get("RSBRIDGE_PROFILE")
        or os.environ.get("RS_TRACE_PROFILE")
        or ""
    )


def _sensitive_key(key):
    text = str(key).lower().replace("-", "_")
    return any(part in text for part in SENSITIVE_PARTS)


def redact(value, depth=0):
    if depth > 5:
        return "..."
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            out[str(key)] = "<redacted>" if _sensitive_key(key) else redact(item, depth + 1)
        return out
    if isinstance(value, list):
        items = [redact(item, depth + 1) for item in value[:24]]
        if len(value) > 24:
            items.append({"more": len(value) - 24})
        return items
    if isinstance(value, str):
        return value if len(value) <= 500 else value[:500] + "...<truncated>"
    return value


def sanitize_arg(value):
    if isinstance(value, (dict, list)):
        return redact(value)
    text = str(value)
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return redact(json.loads(stripped))
        except json.JSONDecodeError:
            pass
    return text if len(text) <= 500 else text[:500] + "...<truncated>"


def log_usage(tool, surface="full", argv=None, cwd=None, returncode=None, extra=None):
    if disabled():
        return
    delegated_by = os.environ.get("AGENT_NAV_XS_PARENT", "")
    record = {
        "event": "agent_tool_used",
        "timestamp": utc_now(),
        "tool": tool,
        "surface": surface,
        "profile": profile_name(),
        "cwd": str(cwd or Path.cwd()),
        "argv": [sanitize_arg(arg) for arg in (argv or [])],
        "pid": os.getpid(),
    }
    if delegated_by:
        record["delegatedBy"] = delegated_by
    if returncode is not None:
        record["returncode"] = int(returncode)
    if extra:
        record["extra"] = redact(extra)
    try:
        USAGE_DIR.mkdir(parents=True, exist_ok=True)
        path = USAGE_DIR / (dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d") + ".jsonl")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Append one local agent tool usage event.")
    parser.add_argument("--tool", required=True)
    parser.add_argument("--surface", default="full")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--returncode", type=int)
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    log_usage(
        args.tool,
        surface=args.surface,
        argv=args.argv,
        cwd=args.cwd or None,
        returncode=args.returncode,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
