#!/usr/bin/env python3
"""Run a gameplay runner under a conservative process supervisor."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from controller_lease import (
    ControllerBusyError,
    ControllerLeaseError,
    acquire_controller,
    adopt_controller,
    compact_lease,
    LEASE_ENV,
)
from profile_utils import profile_from_argv, resolve_profile
from runner_recovery import (
    check_session,
    classify_failure,
    default_child_pid_path,
    default_log_path,
    default_status_path,
    default_supervisor_pid_path,
    read_log_tail,
    reclaim_profile,
    sanitize_command,
    utc_now,
    write_json_file,
    write_pid_file,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SESSION_RECLAIM_REASONS = {
    "expired_session",
    "missing_session_file",
    "player_offline",
    "claim_not_ready",
    "unauthorized_session",
}


def infer_name(command: list[str]) -> str:
    for arg in command:
        if arg == "--":
            continue
        path = Path(str(arg))
        if path.suffix in (".py", ".sh"):
            return path.stem
    if command:
        return Path(str(command[0])).stem or "runner"
    return "runner"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Supervise a repo-local gameplay runner and restart only on known transient bridge/session failures."
    )
    parser.add_argument("--profile", default=resolve_profile(default=""), help="Selected profile/character.")
    parser.add_argument("--name", default="", help="Stable supervisor name. Defaults to the runner script stem.")
    parser.add_argument("--log", default="", help="Shared child/supervisor log path. Defaults under .local/runners/<profile>.")
    parser.add_argument("--pid-file", default="", help="Child runner pid file. Defaults under .local/runners/<profile>.")
    parser.add_argument("--supervisor-pid-file", default="", help="Supervisor pid file. Defaults under .local/runners/<profile>.")
    parser.add_argument("--status-file", default="", help="Supervisor status JSON file. Defaults under .local/runners/<profile>.")
    parser.add_argument("--append", action="store_true", help="Append to the log instead of truncating it at supervisor start.")
    parser.add_argument("--max-restarts", type=int, default=3, help="Maximum child restarts for transient failures.")
    parser.add_argument("--backoff-initial", type=float, default=15.0, help="Initial retry backoff seconds.")
    parser.add_argument("--backoff-max", type=float, default=300.0, help="Maximum retry backoff seconds.")
    parser.add_argument("--auto-reclaim", default="none",
            choices=["none", "local-runtime-doctor", "remote-existing-client", "remote-manual"],
            help="Optional selected-profile session reclaim policy before retrying.")
    parser.add_argument("--bridge-url", default=os.environ.get("AGENT_BRIDGE_URL") or os.environ.get("RSBRIDGE_URL") or "")
    parser.add_argument("--ssl-cert-file", default=os.environ.get("SSL_CERT_FILE") or "")
    parser.add_argument("--restart-on-unknown", action="store_true",
            help="Restart once-classified unknown failures too. Off by default.")
    parser.add_argument("--replace-controller", action="store_true",
            help="Ask the active controller for this profile to stop, then wait before acquiring ownership.")
    parser.add_argument("--replace-wait", type=float, default=10.0,
            help="Seconds to wait for a cooperative controller replacement.")
    parser.add_argument("--controller-lease-id", default="", help=argparse.SUPPRESS)
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Runner command after '--'.")
    args = parser.parse_args(argv)
    command = list(args.command or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("expected a runner command after '--'")
    if not args.profile:
        args.profile = profile_from_argv(command, default="")
    if args.max_restarts < 0:
        raise SystemExit("--max-restarts must be >= 0")
    if args.backoff_initial < 0 or args.backoff_max < 0:
        raise SystemExit("backoff values must be >= 0")
    args.command = command
    return args


class Supervisor:
    def __init__(self, args):
        self.args = args
        self.profile = resolve_profile(args.profile, default="")
        self.name = args.name or infer_name(args.command)
        self.log_path = Path(args.log).expanduser().resolve() if args.log else default_log_path(self.profile, self.name)
        self.pid_file = Path(args.pid_file).expanduser().resolve() if args.pid_file else default_child_pid_path(self.profile, self.name)
        self.supervisor_pid_file = (
            Path(args.supervisor_pid_file).expanduser().resolve()
            if args.supervisor_pid_file else default_supervisor_pid_path(self.profile, self.name)
        )
        self.status_file = Path(args.status_file).expanduser().resolve() if args.status_file else default_status_path(self.profile, self.name)
        self.started_at = utc_now()
        self.restarts = 0
        self.attempt = 0
        self.child_pid = None
        self.child_proc = None
        self.last_exit_code = None
        self.last_classification = None
        self.last_session_status = None
        self.last_reclaim = None
        self.current_status = "starting"
        self.stop_requested = False
        self.controller_lease = None

    def base_status(self, status, extra=None):
        payload = {
            "ok": status in ("running", "backing_off", "complete"),
            "runner": self.name,
            "supervisor": "supervised_runner.py",
            "profile": self.profile,
            "status": status,
            "startedAt": self.started_at,
            "updatedAt": utc_now(),
            "attempt": self.attempt,
            "restarts": self.restarts,
            "maxRestarts": self.args.max_restarts,
            "childPid": self.child_pid,
            "supervisorPid": os.getpid(),
            "pidFile": str(self.pid_file),
            "supervisorPidFile": str(self.supervisor_pid_file),
            "statusFile": str(self.status_file),
            "log": str(self.log_path),
            "command": sanitize_command(self.args.command),
            "autoReclaim": self.args.auto_reclaim,
            "lastExitCode": self.last_exit_code,
            "lastClassification": self.last_classification.to_dict() if self.last_classification else None,
            "lastSessionStatus": self.last_session_status,
            "lastReclaim": self.last_reclaim,
            "controllerLease": {
                "active": self.controller_lease is not None,
                "path": str(self.controller_lease.paths.active) if self.controller_lease else "",
            },
        }
        if extra:
            payload.update(extra)
        return payload

    def write_status(self, status, extra=None):
        self.current_status = status
        write_json_file(self.status_file, self.base_status(status, extra=extra))

    def log_line(self, message):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write("[{}] supervisor {} {}\n".format(utc_now(), self.name, message))

    def prepare_files(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.args.append:
            self.log_path.write_text("", encoding="utf-8")
        write_pid_file(self.supervisor_pid_file, os.getpid())
        self.write_status("starting")

    def launch_child(self):
        env = os.environ.copy()
        if self.profile:
            env["RS_PROFILE"] = self.profile
            env["RSBRIDGE_PROFILE"] = self.profile
        if self.controller_lease is not None:
            env[LEASE_ENV] = self.controller_lease.lease_id
        log_handle = self.log_path.open("ab", buffering=0)
        try:
            proc = subprocess.Popen(
                self.args.command,
                cwd=str(REPO_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=env,
            )
        finally:
            log_handle.close()
        self.child_pid = proc.pid
        self.child_proc = proc
        write_pid_file(self.pid_file, proc.pid)
        self.log_line("attempt={} child_pid={} started".format(self.attempt, proc.pid))
        self.write_status("running")
        return proc

    def wait_child(self, proc):
        last_refresh = 0.0
        while True:
            try:
                return proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                now = time.monotonic()
                if self.controller_lease is not None and now - last_refresh >= 1.0:
                    try:
                        self.controller_lease.refresh()
                    except ControllerLeaseError as exc:
                        self.log_line("controller ownership lost: {}".format(exc))
                        self.stop_requested = True
                    last_refresh = now
                if self.controller_lease is not None and self.controller_lease.stop_requested():
                    self.stop_requested = True
                if self.stop_requested:
                    return self.stop_child(proc)

    def stop_child(self, proc):
        self.write_status("stopping")
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError:
                proc.terminate()
        deadline = time.monotonic() + 8.0
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                proc.kill()
        return proc.wait()

    def maybe_reclaim(self):
        self.last_session_status = check_session(self.profile)
        if self.last_session_status.get("ok"):
            return True
        if self.last_session_status.get("status") == "gateway_down":
            return True
        if self.args.auto_reclaim == "none":
            return False
        self.last_reclaim = reclaim_profile(
            self.profile,
            bridge_url=self.args.bridge_url,
            ssl_cert_file=self.args.ssl_cert_file,
            claim_mode=self.args.auto_reclaim,
        )
        return bool(self.last_reclaim.get("ok"))

    def should_retry(self, classification):
        if classification.kind == "transient":
            return True
        if classification.kind == "unknown" and self.args.restart_on_unknown:
            return True
        return False

    def needs_session_reclaim(self, classification):
        return classification.reason in SESSION_RECLAIM_REASONS

    def sleep_backoff(self):
        delay = min(float(self.args.backoff_max), float(self.args.backoff_initial) * (2 ** max(0, self.restarts)))
        delay = max(0.0, delay)
        next_retry_at = time.time() + delay
        self.write_status("backing_off", {
            "backoffSeconds": delay,
            "nextRetryEpochSeconds": next_retry_at,
            "lastLogTail": read_log_tail(self.log_path, max_bytes=1200)[-1200:],
        })
        if delay > 0:
            self.log_line("transient failure; backing off {:.1f}s".format(delay))
            deadline = time.monotonic() + delay
            while time.monotonic() < deadline:
                if self.controller_lease is not None:
                    try:
                        self.controller_lease.refresh()
                    except ControllerLeaseError as exc:
                        self.log_line("controller ownership lost during backoff: {}".format(exc))
                        self.stop_requested = True
                        return False
                    if self.controller_lease.stop_requested():
                        self.stop_requested = True
                        return False
                time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
        return True

    def acquire_controller(self):
        if self.args.controller_lease_id:
            self.controller_lease = adopt_controller(
                self.profile,
                self.args.controller_lease_id,
                pid=os.getpid(),
            )
            return
        self.controller_lease = acquire_controller(
            self.profile,
            self.name,
            "supervised_runner",
            replace=bool(self.args.replace_controller),
            replace_wait_seconds=float(self.args.replace_wait),
        )

    def run(self):
        try:
            self.acquire_controller()
        except (ControllerBusyError, ControllerLeaseError) as exc:
            current = compact_lease(exc.current) if isinstance(exc, ControllerBusyError) else {}
            self.write_status("controller_conflict", {"activeController": current, "message": str(exc)})
            print(json.dumps({
                "ok": False,
                "status": "controller_conflict",
                "profile": self.profile,
                "controller": self.name,
                "activeController": current,
                "message": str(exc),
            }, sort_keys=True, separators=(",", ":")), file=sys.stderr)
            return 6

        try:
            self.prepare_files()
            while True:
                self.attempt += 1
                proc = self.launch_child()
                exit_code = self.wait_child(proc)
                if exit_code is None:
                    exit_code = proc.returncode if proc.returncode is not None else 1
                self.last_exit_code = exit_code
                self.child_pid = None
                self.child_proc = None

                if self.stop_requested:
                    self.log_line("controller stop completed")
                    self.write_status("stopped", {"completedAt": utc_now()})
                    return 0

                if exit_code == 0:
                    self.log_line("attempt={} child completed".format(self.attempt))
                    self.write_status("complete", {"completedAt": utc_now()})
                    return 0

                tail = read_log_tail(self.log_path)
                classification = classify_failure(tail, exit_code=exit_code)
                self.last_classification = classification
                self.log_line("attempt={} child_exit={} classification={}:{}".format(
                    self.attempt, exit_code, classification.kind, classification.reason))

                if not self.should_retry(classification):
                    status = "unknown" if classification.kind == "unknown" else "terminal"
                    self.write_status(status, {"lastLogTail": tail[-1200:]})
                    return exit_code or 1

                if self.restarts >= self.args.max_restarts:
                    self.write_status("retries_exhausted", {"lastLogTail": tail[-1200:]})
                    return exit_code or 1

                if self.needs_session_reclaim(classification) and not self.maybe_reclaim():
                    self.write_status("needs_reclaim", {"lastLogTail": tail[-1200:]})
                    return exit_code or 1

                if not self.sleep_backoff():
                    self.write_status("stopped", {"completedAt": utc_now()})
                    return 0
                self.restarts += 1
        finally:
            if self.controller_lease is not None:
                self.controller_lease.release()


def main(argv=None):
    args = parse_args(argv)
    supervisor = Supervisor(args)

    def handle_signal(signum, frame):
        supervisor.stop_requested = True
        supervisor.log_line("received signal {}; waiting for child state".format(signum))
        supervisor.write_status("interrupted", {"signal": signum})
        if supervisor.child_proc is not None and supervisor.child_proc.poll() is None:
            try:
                os.killpg(supervisor.child_proc.pid, signum)
            except OSError:
                pass

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    return supervisor.run()


if __name__ == "__main__":
    raise SystemExit(main())
