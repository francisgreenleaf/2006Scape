#!/usr/bin/env python3
"""Compact status and cooperative stop commands for gameplay controllers."""

from __future__ import annotations

import argparse
import json
import os
import signal
import time
from typing import Any

from controller_lease import all_controller_statuses, controller_status, request_controller_stop
from profile_utils import resolve_profile


def emit(payload: Any) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def selected_profiles(args: argparse.Namespace) -> list[str]:
    if args.all:
        return [str(item.get("profile") or "") for item in all_controller_statuses()]
    return [resolve_profile(args.profile, default="")]


def status_command(args: argparse.Namespace) -> int:
    if args.all:
        controllers = all_controller_statuses()
        emit({"ok": True, "activeCount": len(controllers), "controllers": controllers})
        return 0
    emit(controller_status(args.profile))
    return 0


def stop_one(profile: str, wait_seconds: float, force: bool) -> dict[str, Any]:
    requested = request_controller_stop(profile)
    if not requested.get("active"):
        return requested
    deadline = time.monotonic() + max(0.0, float(wait_seconds))
    while time.monotonic() < deadline:
        current = controller_status(profile)
        if not current.get("active"):
            current["status"] = "stopped"
            return current
        time.sleep(0.1)
    current = controller_status(profile)
    if force and current.get("active"):
        pid = int(current.get("pid") or 0)
        if pid > 0:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        forced_deadline = time.monotonic() + max(1.0, float(wait_seconds))
        while time.monotonic() < forced_deadline:
            current = controller_status(profile)
            if not current.get("active"):
                current["status"] = "stopped"
                current["forced"] = True
                return current
            time.sleep(0.1)
    current["ok"] = False
    current["status"] = "stop_pending"
    current["message"] = "cooperative stop requested; controller is still active"
    return current


def stop_command(args: argparse.Namespace) -> int:
    profiles = selected_profiles(args)
    results = [stop_one(profile, args.wait, args.force) for profile in profiles]
    if args.all:
        ok = all(result.get("ok") for result in results)
        emit({"ok": ok, "controllerCount": len(results), "controllers": results})
        return 0 if ok else 4
    emit(results[0])
    return 0 if results[0].get("ok") else 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or stop profile-scoped gameplay controllers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Show one profile controller or every active controller.")
    status.add_argument("--profile", default=resolve_profile(default=""))
    status.add_argument("--all", action="store_true")
    status.set_defaults(handler=status_command)

    stop = subparsers.add_parser("stop", help="Request a cooperative stop at the next controller boundary.")
    stop.add_argument("--profile", default=resolve_profile(default=""))
    stop.add_argument("--all", action="store_true", help="Request a stop for every active profile controller.")
    stop.add_argument("--wait", type=float, default=3.0, help="Seconds to wait for cooperative release.")
    stop.add_argument("--force", action="store_true",
                      help="After the wait, send SIGTERM to the exact pid recorded by the lease; never uses process-name matching.")
    stop.set_defaults(handler=stop_command)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
