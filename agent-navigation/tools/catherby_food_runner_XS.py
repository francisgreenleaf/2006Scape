#!/usr/bin/env python3
"""Extra-slim status/control wrapper for the Catherby food runner."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from runner_status_XS import catherby_status
from usage_log import log_usage
from xs_common import ROOT, compact_text_output, dump, parse_json


RUNNER = Path(__file__).resolve().parent / "catherby_food_runner.py"


def run_runner(args):
    proc = subprocess.run(["python3", str(RUNNER)] + args, cwd=str(ROOT),
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    data = parse_json(proc.stdout)
    if data is None:
        payload = compact_text_output(proc.stdout, limit_lines=10)
        if proc.stderr.strip():
            payload["stderr"] = proc.stderr.strip()[-600:]
        payload["ok"] = proc.returncode == 0
        return proc.returncode, payload
    data.setdefault("ok", proc.returncode == 0)
    return proc.returncode, data


def main(argv=None):
    raw_args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Compact Catherby food runner status/control wrapper.")
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE", "MrFlame"))
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--efficiency-report", action="store_true")
    parser.add_argument("--request-stop", action="store_true")
    parser.add_argument("--clear-stop", action="store_true")
    parser.add_argument("--no-efficiency", action="store_true")
    known, rest = parser.parse_known_args(raw_args)
    log_usage("catherby_food_runner_XS", surface="xs", argv=raw_args)

    if known.request_stop or known.clear_stop:
        passthrough = ["--profile", known.profile]
        passthrough.append("--request-stop" if known.request_stop else "--clear-stop")
        code, payload = run_runner(passthrough + rest)
        dump(payload)
        return code

    if not rest or known.status or known.efficiency_report:
        dump(catherby_status(known.profile, include_efficiency=not known.no_efficiency))
        return 0

    # Deliberate run mode: delegate to the real runner, but keep terminal output compact.
    code, payload = run_runner(["--profile", known.profile] + rest)
    dump(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
