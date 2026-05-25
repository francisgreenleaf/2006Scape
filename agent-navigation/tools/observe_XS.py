#!/usr/bin/env python3
"""Extra-slim wrapper around rs.observe_state."""

import json
import os
from pathlib import Path

from xs_common import ROOT, compact_observe, dump, run_command
from usage_log import log_usage


RS_TOOL = Path(__file__).resolve().parent / "rs-tool.sh"


def main():
    env = os.environ.copy()
    log_usage("observe_XS", surface="xs")
    proc = run_command([str(RS_TOOL), "observe_state", "{}"], cwd=ROOT, env=env)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        dump({"ok": False, "error": "observe_state returned invalid JSON", "stderr": proc.stderr.strip()[-300:]})
        return proc.returncode or 2
    if not data.get("success"):
        dump({"ok": False, "msg": data.get("message", "observe_state failed")})
        return proc.returncode or 1
    dump(compact_observe(data, npc_limit=8, object_limit=12))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
