#!/usr/bin/env python3
"""Extra-slim wrapper around a single rs bridge tool call."""

import argparse
import json
import os
from pathlib import Path

from xs_common import ROOT, compact_bridge, dump, run_command
from usage_log import log_usage


RS_TOOL = Path(__file__).resolve().parent / "rs-tool.sh"


def main():
    parser = argparse.ArgumentParser(description="Call an rs bridge tool and emit an extra-slim response.")
    parser.add_argument("tool")
    parser.add_argument("arguments", nargs="?", default="{}")
    args = parser.parse_args()

    try:
        parsed = json.loads(args.arguments)
    except json.JSONDecodeError as exc:
        dump({"ok": False, "error": "invalid JSON arguments: {}".format(exc)})
        return 2
    if not isinstance(parsed, dict):
        dump({"ok": False, "error": "arguments must be a JSON object"})
        return 2

    env = os.environ.copy()
    log_usage("rs-tool_XS", surface="xs", argv=[args.tool, parsed])
    proc = run_command([str(RS_TOOL), args.tool, json.dumps(parsed, separators=(",", ":"))], cwd=ROOT, env=env)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        dump({"ok": False, "tool": args.tool, "stderr": proc.stderr.strip()[-500:], "stdout": proc.stdout.strip()[-500:]})
        return proc.returncode or 2

    payload = compact_bridge(data, args.tool)
    if isinstance(payload, dict):
        payload.setdefault("tool", args.tool)
    dump(payload)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
