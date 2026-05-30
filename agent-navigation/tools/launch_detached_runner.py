#!/usr/bin/env python3
"""Launch a repo-local runner in a detached session with log capture."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Launch a detached repo-local runner with stdout/stderr redirected to a log.")
    parser.add_argument("--log", required=True, help="Path to the output log file.")
    parser.add_argument("--pid-file", default="", help="Optional path to write the spawned pid.")
    parser.add_argument("--append", action="store_true", help="Append to the log instead of truncating it first.")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run after '--'.")
    args = parser.parse_args(argv)

    command = list(args.command or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("expected a command after '--'")

    log_path = Path(args.log).expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_mode = "ab" if args.append else "wb"
    log_handle = log_path.open(log_mode, buffering=0)
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=os.environ.copy(),
        )
    finally:
        log_handle.close()

    if args.pid_file:
        pid_path = Path(args.pid_file).expanduser().resolve()
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(proc.pid), encoding="utf-8")

    print(proc.pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
