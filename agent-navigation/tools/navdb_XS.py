#!/usr/bin/env python3
"""Extra-slim wrapper around navdb.py diagnostics."""

import sys
from pathlib import Path

from xs_common import ROOT, compact_navdb_text, compact_route_ml, emit_process_result, run_command
from usage_log import log_usage


SCRIPT_DIR = Path(__file__).resolve().parent
NAVDB = SCRIPT_DIR / "navdb.py"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    log_usage("navdb_XS", surface="xs", argv=argv)
    proc = run_command([sys.executable, str(NAVDB)] + argv, cwd=ROOT)
    return emit_process_result(proc, compact_route_ml, lambda text: compact_navdb_text(argv, text))


if __name__ == "__main__":
    raise SystemExit(main())
