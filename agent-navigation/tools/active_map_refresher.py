#!/usr/bin/env python3
"""Manage the background active-map refresh loop.

This is the user/agent-facing controller for the long-running map refresher.
It intentionally delegates rendering to refresh_active_maps.py so there is one
implementation of the active map cadence, cache handling, and canonical output
replacement behavior.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from profile_utils import profile_from_environment, profile_scoped_dir, resolve_profile


SCRIPT_DIR = Path(__file__).resolve().parent
NAV_ROOT = SCRIPT_DIR.parent
REPO_ROOT = NAV_ROOT.parent
LOCAL = NAV_ROOT / ".local" / "map-refresh"
REFRESHER = SCRIPT_DIR / "refresh_active_maps.py"
PID_FILE = LOCAL / "refresh.pid"


def controller_profile(args) -> str:
    return (
        getattr(args, "profile", "")
        or getattr(args, "trace_profile", "")
        or profile_from_environment(trace=True, default="")
        or ""
    )


def control_paths(profile: str = "") -> dict[str, Path]:
    root = profile_scoped_dir(LOCAL, profile)
    return {
        "root": root,
        "pid": root / "refresh.pid",
        "log": root / "refresh.log",
        "status": root / "status.json",
    }


def read_pid(path=PID_FILE):
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def process_exists(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except ProcessLookupError:
        return False


def status_payload(profile="", pid=None):
    paths = control_paths(profile)
    pid = pid if pid is not None else read_pid(paths["pid"])
    payload = {
        "profile": profile,
        "pidFile": str(paths["pid"]),
        "pid": pid,
        "alive": process_exists(pid),
        "log": str(paths["log"]),
        "statusFile": str(paths["status"]),
    }
    if paths["status"].exists():
        try:
            data = json.loads(paths["status"].read_text(encoding="utf-8"))
            payload["refresherStartedAt"] = data.get("startedAt")
            payload["updatedAt"] = data.get("updatedAt")
            payload["jobs"] = {
                job_id: {
                    "label": job.get("label"),
                    "state": job.get("state"),
                    "continuous": job.get("continuous"),
                    "lastFinishedAt": job.get("lastFinishedAt"),
                    "lastDurationSeconds": job.get("lastDurationSeconds"),
                    "lastReturnCode": job.get("lastReturnCode"),
                    "lastError": job.get("lastError"),
                }
                for job_id, job in sorted((data.get("jobs") or {}).items())
            }
        except Exception as exc:
            payload["statusError"] = str(exc)
    return payload


def print_json(data):
    print(json.dumps(data, sort_keys=True, separators=(",", ":")))


def build_refresh_command(args):
    paths = control_paths(controller_profile(args))
    command = [
        sys.executable,
        str(REFRESHER),
        "--status-file",
        str(paths["status"]),
    ]
    for job_id in args.only or []:
        command.extend(["--only", job_id])
    if args.profile:
        command.extend(["--profile", args.profile])
    if args.trace_profile:
        command.extend(["--trace-profile", args.trace_profile])
    if args.include_unscoped_traces:
        command.append("--include-unscoped-traces")
    if args.interval_seconds is not None:
        command.extend(["--interval-seconds", str(args.interval_seconds)])
    if args.stagger_seconds is not None:
        command.extend(["--stagger-seconds", str(args.stagger_seconds)])
    if args.serial:
        command.append("--serial")
    if args.refresh_world_map:
        command.append("--refresh-world-map")
    if args.no_world_map_check:
        command.append("--no-world-map-check")
    if args.render_timeout_seconds is not None:
        command.extend(["--render-timeout-seconds", str(args.render_timeout_seconds)])
    return command


def launch_detached(command, env, paths):
    paths["root"].mkdir(parents=True, exist_ok=True)
    with paths["log"].open("ab", buffering=0) as log:
        proc = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )
    paths["pid"].write_text(str(proc.pid) + "\n", encoding="utf-8")
    return proc.pid


def cmd_start(args):
    profile = controller_profile(args)
    paths = control_paths(profile)
    existing = read_pid(paths["pid"])
    if existing and process_exists(existing):
        if not args.replace:
            payload = status_payload(profile, existing)
            payload["started"] = False
            payload["reason"] = "already-running"
            print_json(payload)
            return 0
        stop_existing(paths, args.stop_timeout, args.force)

    command = build_refresh_command(args)
    env = os.environ.copy()
    if args.profile:
        env["RS_PROFILE"] = args.profile
    if args.trace_profile:
        env["RS_TRACE_PROFILE"] = args.trace_profile

    pid = launch_detached(command, env, paths)
    time.sleep(args.startup_grace_seconds)
    print_json({
        "started": True,
        "profile": profile,
        "pid": pid,
        "alive": process_exists(pid),
        "log": str(paths["log"]),
        "statusFile": str(paths["status"]),
        "command": command,
    })
    return 0


def stop_existing(paths, timeout, force):
    pid = read_pid(paths["pid"])
    if not pid:
        paths["pid"].unlink(missing_ok=True)
        return False
    if not process_exists(pid):
        paths["pid"].unlink(missing_ok=True)
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except PermissionError:
        raise SystemExit("permission denied stopping active map refresher pid={}".format(pid))
    except ProcessLookupError:
        paths["pid"].unlink(missing_ok=True)
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not process_exists(pid):
            paths["pid"].unlink(missing_ok=True)
            return True
        time.sleep(0.25)

    if force:
        try:
            os.kill(pid, signal.SIGKILL)
        except PermissionError:
            raise SystemExit("permission denied force-stopping active map refresher pid={}".format(pid))
        except ProcessLookupError:
            pass
        paths["pid"].unlink(missing_ok=True)
        return True

    raise SystemExit("active map refresher pid={} did not stop within {:.1f}s".format(pid, timeout))


def cmd_stop(args):
    profile = controller_profile(args)
    paths = control_paths(profile)
    stopped = stop_existing(paths, args.stop_timeout, args.force)
    print_json({"stopped": stopped, "profile": profile, "pidFile": str(paths["pid"])})
    return 0


def cmd_restart(args):
    profile = controller_profile(args)
    paths = control_paths(profile)
    pid = read_pid(paths["pid"])
    if pid and process_exists(pid):
        stop_existing(paths, args.stop_timeout, args.force)
    return cmd_start(args)


def cmd_status(args):
    print_json(status_payload(controller_profile(args)))
    return 0


def cmd_logs(args):
    paths = control_paths(controller_profile(args))
    if not paths["log"].exists():
        raise SystemExit("log file does not exist: {}".format(paths["log"]))
    lines = paths["log"].read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-args.lines:]:
        print(line)
    return 0


def add_start_options(parser):
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--trace-profile",
                        default=resolve_profile(trace=True, default=""))
    parser.add_argument("--include-unscoped-traces", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=300.0)
    parser.add_argument("--stagger-seconds", type=float, default=8.0)
    parser.add_argument("--only", action="append",
                        choices=("profile-map", "heat-map", "profile-fog", "mr-flame", "mr-flame-fog"))
    parser.add_argument("--serial", action="store_true")
    parser.add_argument("--refresh-world-map", action="store_true")
    parser.add_argument("--no-world-map-check", action="store_true")
    parser.add_argument("--render-timeout-seconds", type=float)
    parser.add_argument("--replace", action="store_true", help="Stop an existing refresher before starting a new one.")
    parser.add_argument("--force", action="store_true", help="Use SIGKILL if graceful stop times out during replace/restart.")
    parser.add_argument("--stop-timeout", type=float, default=15.0)
    parser.add_argument("--startup-grace-seconds", type=float, default=0.5)


def add_control_options(parser):
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--trace-profile",
                        default=resolve_profile(trace=True, default=""))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Start, stop, and inspect the background active-map refresher.")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Start the background active-map refresher if it is not already running.")
    add_start_options(start)
    start.set_defaults(func=cmd_start)

    restart = sub.add_parser("restart", help="Stop the existing refresher, then start a new one.")
    add_start_options(restart)
    restart.set_defaults(replace=True, func=cmd_restart)

    status = sub.add_parser("status", help="Print pid/log/status details for the background refresher.")
    add_control_options(status)
    status.set_defaults(func=cmd_status)

    logs = sub.add_parser("logs", help="Print the end of the background refresher log.")
    add_control_options(logs)
    logs.add_argument("--lines", type=int, default=80)
    logs.set_defaults(func=cmd_logs)

    stop = sub.add_parser("stop", help="Stop the background active-map refresher.")
    add_control_options(stop)
    stop.add_argument("--stop-timeout", type=float, default=15.0)
    stop.add_argument("--force", action="store_true", help="Use SIGKILL if graceful stop times out.")
    stop.set_defaults(func=cmd_stop)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
