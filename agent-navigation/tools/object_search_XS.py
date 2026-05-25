#!/usr/bin/env python3
"""Compact object search wrapper with failure candidates."""

import argparse
import json
import os
from pathlib import Path

from usage_log import log_usage
from xs_common import ROOT, compact_bridge, dump, game_object, run_command


RS_TOOL = Path(__file__).resolve().parent / "rs-tool.sh"


def norm(value):
    return str(value or "").strip().lower().replace("_", " ")


def parse_object_ids(text):
    if not text:
        return []
    values = []
    for part in str(text).replace(",", " ").split():
        try:
            values.append(int(part))
        except ValueError:
            continue
    return values


def matches(entry, name, resource, object_ids):
    if not isinstance(entry, dict):
        return False
    if object_ids and int(entry.get("objectId", entry.get("id", -1)) or -1) not in object_ids:
        return False
    if name and name not in norm(entry.get("name")):
        return False
    if resource and resource not in norm(entry.get("resource")) and resource not in norm(entry.get("name")):
        return False
    return bool(object_ids or name or resource)


def observe_candidates(name, resource, object_ids, limit):
    proc = run_command([str(RS_TOOL), "observe_state", "{}"], cwd=ROOT, env=os.environ.copy())
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    objects = data.get("nearbyObjects") if isinstance(data, dict) else []
    if not isinstance(objects, list):
        return []
    exact = [entry for entry in objects if matches(entry, name, resource, object_ids)]
    source = exact or objects
    source = sorted(source, key=lambda entry: entry.get("distance", entry.get("dist", 999)))
    return [game_object(entry) for entry in source[:limit]]


def main():
    parser = argparse.ArgumentParser(description="Find a nearby object with compact output and fallback candidates.")
    parser.add_argument("--name", default="")
    parser.add_argument("--resource", default="")
    parser.add_argument("--object-id", type=int, action="append", default=[])
    parser.add_argument("--object-ids", default="")
    parser.add_argument("--max-distance", type=int, default=60)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    object_ids = list(args.object_id) + parse_object_ids(args.object_ids)
    payload = {"maxDistance": args.max_distance}
    if args.name:
        payload["name"] = args.name
    if args.resource:
        payload["resource"] = args.resource
    if object_ids:
        payload["objectIds"] = object_ids
    log_usage("object_search_XS", surface="xs", argv=vars(args))
    proc = run_command([str(RS_TOOL), "find_nearest_object", json.dumps(payload, separators=(",", ":"))],
                       cwd=ROOT, env=os.environ.copy())
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        dump({"ok": False, "error": "find_nearest_object returned invalid JSON", "stderr": proc.stderr.strip()[-300:]})
        return proc.returncode or 2
    out = compact_bridge(data, "find_nearest_object")
    if isinstance(out, dict) and not out.get("ok", out.get("success", False)):
        out["candidates"] = observe_candidates(norm(args.name), norm(args.resource), object_ids, max(1, args.limit))
    dump(out)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
