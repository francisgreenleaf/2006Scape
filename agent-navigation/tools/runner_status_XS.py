#!/usr/bin/env python3
"""Compact status reader for cooperative gameplay runners."""

import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path

from usage_log import log_usage
from xs_common import ROOT, dump, parse_json


RUNNER_DIR = ROOT / "agent-navigation" / ".local" / "runners"
CATHERBY = ROOT / "agent-navigation" / "tools" / "catherby_food_runner.py"


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def parse_time(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def age_seconds(value):
    parsed = parse_time(value)
    if parsed is None:
        return None
    return round((utcnow() - parsed).total_seconds(), 1)


def run_json(command):
    proc = subprocess.run(command, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    data = parse_json(proc.stdout)
    if data is None:
        return {"ok": False, "returncode": proc.returncode, "stderr": proc.stderr.strip()[-400:], "stdout": proc.stdout.strip()[-400:]}
    data.setdefault("ok", proc.returncode == 0)
    return data


def compact_status(data):
    status = data.get("status") if isinstance(data.get("status"), dict) else {}
    player = status.get("player") if isinstance(status.get("player"), dict) else {}
    return {
        "ok": bool(data.get("ok")),
        "runner": data.get("runner") or status.get("runner"),
        "profile": data.get("profile") or status.get("profile"),
        "state": status.get("status"),
        "reason": status.get("reason"),
        "cycle": status.get("cycle"),
        "updatedAt": status.get("updatedAt"),
        "age": data.get("statusAgeSeconds") if data.get("statusAgeSeconds") is not None else age_seconds(status.get("updatedAt")),
        "stopRequested": bool(data.get("stopRequested") or status.get("stopRequested")),
        "stopFiles": data.get("stopFiles") or status.get("stopFiles"),
        "runPath": status.get("runPath"),
        "routeEvidence": status.get("routeEvidencePath"),
        "player": player,
        "args": status.get("args"),
        "error": data.get("error") or status.get("error"),
    }


def compact_efficiency(data):
    if not isinstance(data, dict):
        return {}
    last = data.get("last") if isinstance(data.get("last"), dict) else {}
    return {
        "ok": bool(data.get("ok")),
        "records": data.get("records"),
        "windowMinutes": data.get("windowMinutes"),
        "activeSeconds": data.get("activeSeconds"),
        "idlePct": data.get("idlePct"),
        "idleSeconds": data.get("idleSeconds"),
        "activitySeconds": data.get("activitySeconds"),
        "last": {
            "timestamp": last.get("timestamp"),
            "tile": last.get("tile"),
            "freeInventorySlots": last.get("freeInventorySlots"),
            "activity": {
                key: value for key, value in (last.get("activity") or {}).items() if value
            },
        } if last else {},
    }


def catherby_status(profile, include_efficiency=True):
    status = run_json(["python3", str(CATHERBY), "--profile", profile, "--status"])
    out = compact_status(status)
    if include_efficiency:
        efficiency = run_json(["python3", str(CATHERBY), "--profile", profile, "--efficiency-report", "--quiet"])
        out["efficiency"] = compact_efficiency(efficiency)
        if out["efficiency"].get("ok") and not out.get("ok"):
            out["ok"] = True
            out["state"] = out.get("state") or "no_status_file"
    return out


def list_status_files():
    files = []
    if RUNNER_DIR.exists():
        for path in sorted(RUNNER_DIR.glob("*.status.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            files.append({
                "path": str(path),
                "runner": data.get("runner"),
                "profile": data.get("profile"),
                "status": data.get("status"),
                "reason": data.get("reason"),
                "updatedAt": data.get("updatedAt"),
                "age": age_seconds(data.get("updatedAt")),
            })
    return files


def main():
    parser = argparse.ArgumentParser(description="Read compact cooperative runner status.")
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE", "MrFlame"))
    parser.add_argument("--runner", default="catherby-food", choices=["catherby-food"])
    parser.add_argument("--no-efficiency", action="store_true")
    parser.add_argument("--list", action="store_true", help="List known runner status files instead of a runner-specific summary.")
    args = parser.parse_args()
    log_usage("runner_status_XS", surface="xs", argv=vars(args))
    if args.list:
        dump({"ok": True, "statusFiles": list_status_files()})
        return 0
    dump(catherby_status(args.profile, include_efficiency=not args.no_efficiency))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
