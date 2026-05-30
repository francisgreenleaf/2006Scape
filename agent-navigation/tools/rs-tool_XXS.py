#!/usr/bin/env python3
"""Minimal wrapper around a single rs bridge tool call."""

import argparse
import json
import os
from pathlib import Path

from usage_log import log_usage
from xs_common import ROOT, dump, run_command


RS_TOOL = Path(__file__).resolve().parent / "rs-tool.sh"


def xxs_tool_name(tool):
    if tool.endswith("_XXS"):
        return tool
    if tool.endswith("_XS"):
        return tool[:-3] + "_XXS"
    return tool + "_XXS"


def main():
    parser = argparse.ArgumentParser(description="Call an rs bridge tool and emit a minimal XXS response.")
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

    tool = xxs_tool_name(args.tool)
    env = os.environ.copy()
    env["AGENT_NAV_XS_PARENT"] = "xxs"
    log_usage("rs-tool_XXS", surface="xxs", argv=[tool, parsed])
    proc = run_command([str(RS_TOOL), tool, json.dumps(parsed, separators=(",", ":"))], cwd=ROOT, env=env)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        dump({"ok": False, "tool": tool, "stderr": proc.stderr.strip()[-500:], "stdout": proc.stdout.strip()[-500:]})
        return proc.returncode or 2

    if isinstance(data, dict):
        data.setdefault("tool", tool)
    dump(data)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
