#!/usr/bin/env python3
"""Extra-slim wrapper around route_ml.py output."""

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from xs_common import ROOT, compact_route_ml, emit_process_result, run_command  # noqa: E402
from usage_log import log_usage  # noqa: E402


ROUTE_ML = Path(__file__).resolve().parent / "route_ml.py"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    log_usage("route_ml_XS", surface="xs", argv=argv)
    proc = run_command([sys.executable, str(ROUTE_ML)] + argv, cwd=ROOT)
    return emit_process_result(proc, compact_route_ml)


if __name__ == "__main__":
    raise SystemExit(main())
