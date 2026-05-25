#!/usr/bin/env python3
"""Compact food, inventory, equipment, and bank summary for gameplay decisions."""

import json
import os
from pathlib import Path

from usage_log import log_usage
from xs_common import ROOT, compact_food_bank, dump, run_command


RS_TOOL = Path(__file__).resolve().parent / "rs-tool.sh"


def main():
    env = os.environ.copy()
    log_usage("food_bank_XS", surface="xs")
    proc = run_command([str(RS_TOOL), "observe_state", "{}"], cwd=ROOT, env=env)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        dump({"ok": False, "error": "observe_state returned invalid JSON", "stderr": proc.stderr.strip()[-300:]})
        return proc.returncode or 2
    if not data.get("success"):
        dump({"ok": False, "msg": data.get("message", "observe_state failed")})
        return proc.returncode or 1
    dump(compact_food_bank(data))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
