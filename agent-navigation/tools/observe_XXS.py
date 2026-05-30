#!/usr/bin/env python3
"""Minimal wrapper around rs.observe_state_XXS."""

import os
from pathlib import Path

from xs_common import ROOT, dump, run_command
from usage_log import log_usage


RS_TOOL_XXS = Path(__file__).resolve().parent / "rs-tool_XXS.sh"


def main():
    log_usage("observe_XXS", surface="xxs")
    env = os.environ.copy()
    env["AGENT_NAV_XS_PARENT"] = "xxs"
    proc = run_command([str(RS_TOOL_XXS), "observe_state", "{}"], cwd=ROOT, env=env)
    if proc.returncode != 0:
        dump({"ok": False, "error": "observe_state_XXS failed", "stderr": proc.stderr.strip()[-300:]})
        return proc.returncode
    print(proc.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
