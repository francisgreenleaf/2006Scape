#!/usr/bin/env python3
"""Launch a repo-local runner in a detached session with log capture."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from controller_lease import (
    ControllerBusyError,
    ControllerLeaseError,
    LEASE_ENV,
    acquire_controller,
    compact_lease,
)
from profile_utils import profile_from_argv, resolve_profile


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SUPERVISED_RUNNER = SCRIPT_DIR / "supervised_runner.py"


def infer_name(command):
    for arg in command:
        path = Path(str(arg))
        if path.suffix in (".py", ".sh"):
            return path.stem
    return Path(str(command[0])).stem or "runner"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Launch a detached repo-local runner with stdout/stderr redirected to a log.")
    parser.add_argument("--log", required=True, help="Path to the output log file.")
    parser.add_argument("--pid-file", default="", help="Optional path to write the spawned pid.")
    parser.add_argument("--append", action="store_true", help="Append to the log instead of truncating it first.")
    parser.add_argument("--supervise", action="store_true",
            help="Launch supervised_runner.py detached and let it manage the child runner lifecycle.")
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or "",
            help="Profile passed to the supervised child through RS_PROFILE/RSBRIDGE_PROFILE.")
    parser.add_argument("--name", default="", help="Stable supervisor name. Defaults to the runner script stem.")
    parser.add_argument("--supervisor-pid-file", default="", help="Optional path to write the supervisor pid.")
    parser.add_argument("--status-file", default="", help="Optional supervisor status JSON path.")
    parser.add_argument("--max-restarts", type=int, default=3, help="Maximum supervised restarts for transient failures.")
    parser.add_argument("--backoff-initial", type=float, default=15.0, help="Initial supervised retry backoff seconds.")
    parser.add_argument("--backoff-max", type=float, default=300.0, help="Maximum supervised retry backoff seconds.")
    parser.add_argument("--auto-reclaim", default="none",
            choices=["none", "local-runtime-doctor", "remote-existing-client", "remote-manual"],
            help="Selected-profile reclaim policy for supervised transient session failures.")
    parser.add_argument("--bridge-url", default=os.environ.get("AGENT_BRIDGE_URL") or os.environ.get("RSBRIDGE_URL") or "",
            help="Remote bridge URL for supervised remote reclaim status.")
    parser.add_argument("--ssl-cert-file", default=os.environ.get("SSL_CERT_FILE") or "",
            help="SSL_CERT_FILE for supervised remote bridge checks.")
    parser.add_argument("--restart-on-unknown", action="store_true",
            help="Let the supervisor restart unknown child failures. Off by default.")
    parser.add_argument("--replace-controller", action="store_true",
            help="Ask the selected profile's active controller to stop before launching this one.")
    parser.add_argument("--replace-wait", type=float, default=10.0,
            help="Seconds to wait for a cooperative controller replacement.")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run after '--'.")
    args = parser.parse_args(argv)

    command = list(args.command or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("expected a command after '--'")

    profile = resolve_profile(args.profile or profile_from_argv(command, default=""), default="")
    name = args.name or infer_name(command)
    try:
        controller_lease = acquire_controller(
            profile,
            name,
            "supervised_runner" if args.supervise else "detached_runner",
            replace=bool(args.replace_controller),
            replace_wait_seconds=float(args.replace_wait),
        )
    except ControllerBusyError as exc:
        print(json.dumps({
            "ok": False,
            "status": "controller_conflict",
            "profile": profile,
            "controller": name,
            "activeController": compact_lease(exc.current),
            "message": str(exc),
        }, sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 6

    child_env = os.environ.copy()
    child_env[LEASE_ENV] = controller_lease.lease_id
    if profile:
        child_env["RS_PROFILE"] = profile
        child_env["RSBRIDGE_PROFILE"] = profile

    if args.supervise:
        supervised_command = [sys.executable, str(SUPERVISED_RUNNER)]
        if profile:
            supervised_command.extend(["--profile", profile])
        supervised_command.extend(["--name", name])
        supervised_command.extend(["--controller-lease-id", controller_lease.lease_id])
        supervised_command.extend(["--log", args.log])
        if args.pid_file:
            supervised_command.extend(["--pid-file", args.pid_file])
        if args.supervisor_pid_file:
            supervised_command.extend(["--supervisor-pid-file", args.supervisor_pid_file])
        if args.status_file:
            supervised_command.extend(["--status-file", args.status_file])
        if args.append:
            supervised_command.append("--append")
        supervised_command.extend(["--max-restarts", str(args.max_restarts)])
        supervised_command.extend(["--backoff-initial", str(args.backoff_initial)])
        supervised_command.extend(["--backoff-max", str(args.backoff_max)])
        supervised_command.extend(["--auto-reclaim", args.auto_reclaim])
        if args.bridge_url:
            supervised_command.extend(["--bridge-url", args.bridge_url])
        if args.ssl_cert_file:
            supervised_command.extend(["--ssl-cert-file", args.ssl_cert_file])
        if args.restart_on_unknown:
            supervised_command.append("--restart-on-unknown")
        supervised_command.append("--")
        supervised_command.extend(command)

        try:
            proc = subprocess.Popen(
                supervised_command,
                cwd=str(REPO_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=child_env,
            )
        except Exception:
            controller_lease.release()
            raise
        adopted = False
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            try:
                adopted = int(controller_lease.current().get("pid") or 0) == proc.pid
            except ControllerLeaseError:
                adopted = True
                break
            if adopted or proc.poll() is not None:
                break
            time.sleep(0.02)
        if not adopted and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            controller_lease.release()
            print(json.dumps({
                "ok": False,
                "status": "controller_adoption_timeout",
                "profile": profile,
                "controller": name,
            }, sort_keys=True, separators=(",", ":")), file=sys.stderr)
            return 6
        if not adopted and proc.poll() is not None and proc.returncode:
            controller_lease.release()
            print(json.dumps({
                "ok": False,
                "status": "launch_failed",
                "profile": profile,
                "controller": name,
                "returncode": proc.returncode,
            }, sort_keys=True, separators=(",", ":")), file=sys.stderr)
            return int(proc.returncode or 1)
        if args.supervisor_pid_file:
            pid_path = Path(args.supervisor_pid_file).expanduser().resolve()
            pid_path.parent.mkdir(parents=True, exist_ok=True)
            pid_path.write_text(str(proc.pid), encoding="utf-8")
        print(proc.pid)
        return 0

    log_path = Path(args.log).expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_mode = "ab" if args.append else "wb"
    log_handle = log_path.open(log_mode, buffering=0)
    try:
        try:
            proc = subprocess.Popen(
                command,
                cwd=str(REPO_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=child_env,
            )
            controller_lease.transfer_pid(proc.pid)
        except Exception:
            controller_lease.release()
            raise
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
