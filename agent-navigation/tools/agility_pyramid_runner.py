#!/usr/bin/env python3
"""Run or supervise the Agility Pyramid phase."""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

from agility_course_runner_common import launch_course
from profile_utils import resolve_profile, safe_profile


SCRIPT_DIR = Path(__file__).resolve().parent
NAV_ROOT = SCRIPT_DIR.parent
REPO_ROOT = NAV_ROOT.parent
AGILITY_RUNNER = SCRIPT_DIR / "agility_runner.py"
AGILITY_REPORT = SCRIPT_DIR / "agility_runner_report.py"
RUNNER_NAME = "agility-pyramid"
COURSE_ID = "agility_pyramid_course"


def utc_stamp():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def runner_dir(profile):
    return NAV_ROOT / ".local" / "runners" / safe_profile(profile)


def runner_paths(profile):
    directory = runner_dir(profile)
    return {
        "dir": directory,
        "pid": directory / "{}.pid".format(RUNNER_NAME),
        "logpath": directory / "{}.logpath".format(RUNNER_NAME),
        "stop": directory / "{}.stop".format(RUNNER_NAME),
    }


def read_text(path):
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_pid(path):
    value = read_text(path)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def process_exists(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def tail_lines(path, limit=8):
    if not path or not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return lines[-int(limit):]


def print_json(payload):
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def status_payload(profile, tail=8):
    paths = runner_paths(profile)
    pid = read_pid(paths["pid"])
    log_path_text = read_text(paths["logpath"])
    log_path = Path(log_path_text).expanduser() if log_path_text else None
    return {
        "ok": True,
        "runner": RUNNER_NAME,
        "profile": profile,
        "pid": pid,
        "pidFile": str(paths["pid"]),
        "alive": process_exists(pid),
        "stopRequested": paths["stop"].exists(),
        "stopPath": str(paths["stop"]),
        "logPath": str(log_path) if log_path else "",
        "logPathFile": str(paths["logpath"]),
        "logTail": tail_lines(log_path, tail) if log_path else [],
    }


def readiness_payload(args):
    command = [
        sys.executable,
        str(AGILITY_RUNNER),
        "--profile", args.profile,
        "--course", COURSE_ID,
        "--laps", "1",
        "--target-agility-level", str(args.target_agility_level),
        "--min-run-energy", str(args.min_run_energy),
        "--route-max-batches", str(args.route_max_batches),
        "--no-preposition",
        "--dry-run",
    ]
    proc = subprocess.run(command, cwd=str(REPO_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {
            "readyToRun": False,
            "stdout": proc.stdout.strip()[-800:],
            "stderr": proc.stderr.strip()[-800:],
        }
    payload["returncode"] = proc.returncode
    payload["command"] = command
    if proc.stderr.strip():
        payload["stderr"] = proc.stderr.strip()[-800:]
    return payload


def launch_detached(args):
    paths = runner_paths(args.profile)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    try:
        paths["stop"].unlink()
    except FileNotFoundError:
        pass
    existing_pid = read_pid(paths["pid"])
    if process_exists(existing_pid):
        print_json({
            "ok": False,
            "runner": RUNNER_NAME,
            "profile": args.profile,
            "error": "already_running",
            "pid": existing_pid,
            "pidFile": str(paths["pid"]),
        })
        return 2

    readiness = readiness_payload(args)
    if not readiness.get("readyToRun"):
        print_json({
            "ok": False,
            "runner": RUNNER_NAME,
            "profile": args.profile,
            "error": "not_ready",
            "readyToRun": False,
            "currentState": readiness.get("currentState"),
            "message": "run agent-navigation/tools/agility_pyramid_travel_setup.py first",
        })
        return 3

    log_path = paths["dir"] / "{}-{}.log".format(RUNNER_NAME, utc_stamp())
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--profile", args.profile,
        "--target-agility-level", str(args.target_agility_level),
        "--laps", str(args.laps),
        "--min-run-energy", str(args.min_run_energy),
        "--route-max-batches", str(args.route_max_batches),
    ]
    if args.quiet:
        command.append("--quiet")

    env = os.environ.copy()
    env.update({
        "PROFILE": args.profile,
        "RS_PROFILE": args.profile,
        "RS_TRACE_PROFILE": args.profile,
    })
    with log_path.open("wb", buffering=0) as handle:
        proc = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )
    paths["pid"].write_text(str(proc.pid), encoding="utf-8")
    paths["logpath"].write_text(str(log_path), encoding="utf-8")
    print_json({
        "ok": True,
        "runner": RUNNER_NAME,
        "profile": args.profile,
        "pid": proc.pid,
        "pidFile": str(paths["pid"]),
        "logPath": str(log_path),
        "logPathFile": str(paths["logpath"]),
    })
    return 0


def request_stop(args):
    paths = runner_paths(args.profile)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    paths["stop"].write_text(utc_stamp() + "\n", encoding="utf-8")
    print_json({
        "ok": True,
        "runner": RUNNER_NAME,
        "profile": args.profile,
        "stopRequested": True,
        "stopPath": str(paths["stop"]),
        "status": status_payload(args.profile, tail=args.tail_lines),
    })
    return 0


def clear_stop(args):
    paths = runner_paths(args.profile)
    try:
        paths["stop"].unlink()
    except FileNotFoundError:
        pass
    print_json({
        "ok": True,
        "runner": RUNNER_NAME,
        "profile": args.profile,
        "stopRequested": False,
        "stopPath": str(paths["stop"]),
    })
    return 0


def print_report(args):
    command = [
        sys.executable,
        str(AGILITY_REPORT),
        "--profile", args.profile,
        "--course", COURSE_ID,
    ]
    if args.report_text:
        command.append("--text")
    if args.report_pretty:
        command.append("--pretty")
    proc = subprocess.run(command, cwd=str(REPO_ROOT), text=True)
    return proc.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the Agility Pyramid phase.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--target-agility-level", type=int, default=99)
    parser.add_argument("--laps", type=int, default=20000)
    parser.add_argument("--min-run-energy", type=int, default=8)
    parser.add_argument("--route-max-batches", type=int, default=80)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--status", action="store_true",
                        help="Print compact detached-runner status without starting anything.")
    parser.add_argument("--tail-lines", type=int, default=8)
    parser.add_argument("--launch-detached", action="store_true",
                        help="Start the Pyramid runner detached after proving the character is already on the course.")
    parser.add_argument("--request-stop", action="store_true",
                        help="Ask the detached Pyramid runner to stop at the next lap boundary.")
    parser.add_argument("--clear-stop", action="store_true",
                        help="Clear the Pyramid runner cooperative stop request.")
    parser.add_argument("--report", action="store_true",
                        help="Print the latest compact Agility Pyramid timing report.")
    parser.add_argument("--report-text", action="store_true",
                        help="Use text output for --report.")
    parser.add_argument("--report-pretty", action="store_true",
                        help="Pretty-print JSON output for --report.")
    args = parser.parse_args(argv)
    if args.status:
        print_json(status_payload(args.profile, tail=args.tail_lines))
        return 0
    if args.request_stop:
        return request_stop(args)
    if args.clear_stop:
        return clear_stop(args)
    if args.report:
        return print_report(args)
    if args.launch_detached:
        return launch_detached(args)
    return launch_course("pyramid", args)


if __name__ == "__main__":
    raise SystemExit(main())
