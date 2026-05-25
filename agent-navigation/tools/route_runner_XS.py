#!/usr/bin/env python3
"""Extra-slim wrapper around route_runner.py output."""

import sys
from pathlib import Path

from xs_common import ROOT, compact_route_runner, compact_text_output, emit_process_result, run_command
from usage_log import log_usage


SCRIPT_DIR = Path(__file__).resolve().parent
ROUTE_RUNNER = SCRIPT_DIR / "route_runner.py"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    log_usage("route_runner_XS", surface="xs", argv=argv)
    proc = run_command([sys.executable, str(ROUTE_RUNNER)] + argv, cwd=ROOT)
    return emit_process_result(proc, compact_route_runner, lambda text: compact_text_output(text, limit_lines=10))


if __name__ == "__main__":
    raise SystemExit(main())
