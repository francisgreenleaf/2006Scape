#!/usr/bin/env python3
"""Compact food, inventory, equipment, and bank summary for gameplay decisions."""

import argparse
import json
import os
from pathlib import Path

from profile_utils import resolve_profile
from usage_log import log_usage
from xs_common import ROOT, compact_food_bank, dump, run_command


RS_TOOL = Path(__file__).resolve().parent / "rs-tool.sh"


def main():
    parser = argparse.ArgumentParser(description="Compact food, inventory, equipment, and bank summary for one selected profile.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    args = parser.parse_args()
    env = os.environ.copy()
    if args.profile:
        env["RS_PROFILE"] = args.profile
    log_usage("food_bank_XS", surface="xs", argv=vars(args))
    proc = run_command([str(RS_TOOL), "food_bank_XS", "{}"], cwd=ROOT, env=env)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        dump({"ok": False, "error": "food_bank_XS returned invalid JSON", "stderr": proc.stderr.strip()[-300:]})
        return proc.returncode or 2
    if not data.get("success"):
        dump({"ok": False, "msg": data.get("message", "food_bank_XS failed")})
        return proc.returncode or 1
    dump(compact_food_bank(data))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
