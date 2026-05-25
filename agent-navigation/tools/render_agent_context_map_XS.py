#!/usr/bin/env python3
"""Extra-slim wrapper around render_agent_context_map.py output."""

import sys
from pathlib import Path

from xs_common import ROOT, compact_context_map, emit_process_result, run_command
from usage_log import log_usage


SCRIPT_DIR = Path(__file__).resolve().parent
CONTEXT_MAP = SCRIPT_DIR / "render_agent_context_map.py"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    log_usage("render_agent_context_map_XS", surface="xs", argv=argv)
    proc = run_command([sys.executable, str(CONTEXT_MAP)] + argv, cwd=ROOT)
    return emit_process_result(proc, compact_context_map)


if __name__ == "__main__":
    raise SystemExit(main())
