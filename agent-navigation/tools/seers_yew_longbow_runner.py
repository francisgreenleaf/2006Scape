#!/usr/bin/env python3
"""Seers yew longbow runner.

This entrypoint reuses the proven Seers fletching loop while keeping it
separate from the willow runner: independent status/stop files, independent
logs, a yew chop anchor, and compact XS observations only.
"""

import sys
import time

import seers_fletching_runner as base
from profile_utils import is_default_profile, run_evidence_path, safe_profile


SEERS_YEW = "seers_yew_trees"
YEW_ANCHOR = {"x": 2705, "y": 3464, "height": 0}
YEW_ROUTE_FROM_BANK = [
    {"x": 2723, "y": 3486, "height": 0},
    {"x": 2716, "y": 3476, "height": 0},
    {"x": 2708, "y": 3467, "height": 0},
    YEW_ANCHOR,
]

_ORIGINAL_ROUTE_TO = base.route_to
_ORIGINAL_CHOP_ANCHOR_FOR_TREE = base.chop_anchor_for_tree


def runner_stem():
    if is_default_profile(base.RUN_PROFILE):
        return "seers-yew-longbow"
    return "seers-yew-longbow-{}".format(safe_profile(base.RUN_PROFILE))


def status_path():
    return base.ROOT / ".local" / "runners" / "{}.status.json".format(runner_stem())


def stop_path():
    return base.ROOT / ".local" / "runners" / "{}.stop".format(runner_stem())


def write_status(args, phase, player, extra=None):
    path = status_path()
    stop = stop_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": True,
        "runner": "seers_yew_longbow_runner",
        "updatedAt": base.utc_now(),
        "phase": phase,
        "profile": base.RUN_PROFILE or "default",
        "pid": base.os.getpid(),
        "stopRequested": stop.exists(),
        "player": base.compact_player(player),
        "logs": base.fletchable_log_count(player),
        "products": base.product_count(player),
        "notedProducts": base.noted_product_count(player),
        "bankedProducts": sum(base.total_item_count(player, item_id) for item_id in base.FLETCHING_PRODUCT_IDS),
        "bankedLowTierFish": sum(base.total_item_count(player, item_id) for item_id in base.LOW_TIER_FISH_IDS),
        "birdNests": sum(base.total_item_count(player, item_id) for item_id in base.BIRD_NEST_IDS),
        "args": base.jsonable(vars(args)) if args is not None else {},
    }
    if extra:
        payload.update(extra)
    path.write_text(base.json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def print_status():
    path = status_path()
    if path.exists():
        print(path.read_text(encoding="utf-8").strip())
        return 0
    print(base.json.dumps({
        "ok": False,
        "runner": "seers_yew_longbow_runner",
        "error": "no_status",
        "statusPath": str(path),
    }, sort_keys=True, separators=(",", ":")))
    return 1


def print_shutdown_status():
    path = status_path()
    stop = stop_path()
    if not path.exists():
        print(base.json.dumps({
            "ok": False,
            "runner": "seers_yew_longbow_runner",
            "error": "no_status",
            "profile": base.RUN_PROFILE or "default",
            "stopRequested": stop.exists(),
            "shutdownComplete": False,
        }, sort_keys=True, separators=(",", ":")))
        return 1
    try:
        status = base.json.loads(path.read_text(encoding="utf-8"))
    except base.json.JSONDecodeError:
        print(base.json.dumps({
            "ok": False,
            "runner": "seers_yew_longbow_runner",
            "error": "invalid_status",
            "profile": base.RUN_PROFILE or "default",
            "stopRequested": stop.exists(),
            "shutdownComplete": False,
        }, sort_keys=True, separators=(",", ":")))
        return 1
    phase = str(status.get("phase") or "")
    stop_requested = bool(status.get("stopRequested")) or stop.exists()
    print(base.json.dumps({
        "ok": True,
        "runner": status.get("runner") or "seers_yew_longbow_runner",
        "profile": status.get("profile") or base.RUN_PROFILE or "default",
        "phase": phase,
        "stopRequested": stop_requested,
        "shutdownComplete": phase in base.TERMINAL_PHASES,
        "pid": status.get("pid"),
        "updatedAt": status.get("updatedAt"),
    }, sort_keys=True, separators=(",", ":")))
    return 0


def request_stop():
    path = stop_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(base.utc_now() + "\n", encoding="utf-8")
    print(base.json.dumps({
        "ok": True,
        "runner": "seers_yew_longbow_runner",
        "stopRequested": True,
        "stopPath": str(path),
    }, sort_keys=True, separators=(",", ":")))
    return 0


def observe_compact():
    return base.observe_xs()


def close_interfaces_if_needed(player, handle, reason, force=False):
    if not force and not base.interface_open(player):
        return player
    result = base.call_tool("close_interfaces", {})
    updated = base.bridge._player_from_or(result, player)
    base.write_event(handle, "close_interfaces", {
        "reason": reason,
        "before": base.compact_player(player),
        "after": base.compact_player(updated),
        "success": bool(result.get("success", True)),
    })
    return updated


def chop_anchor_for_tree(tree):
    if str(tree or "").lower() == "yew":
        return SEERS_YEW
    return _ORIGINAL_CHOP_ANCHOR_FOR_TREE(tree)


def route_to_yew(args, handle, reason, player=None):
    if player is None:
        player = base.observe_xs()
    current = base.tile_from_player(player)
    if base.tile_distance(current, YEW_ANCHOR) <= 4:
        base.write_event(handle, "yew_route_skip", {
            "reason": reason,
            "target": SEERS_YEW,
            "player": base.compact_player(player),
        })
        return player

    base.write_event(handle, "yew_route_start", {
        "reason": reason,
        "target": SEERS_YEW,
        "waypoints": YEW_ROUTE_FROM_BANK,
        "player": base.compact_player(player),
    })
    for index, tile in enumerate(YEW_ROUTE_FROM_BANK, start=1):
        current = base.tile_from_player(player)
        stop_distance = 4 if index == len(YEW_ROUTE_FROM_BANK) else 1
        if base.tile_distance(current, tile) <= stop_distance:
            continue
        step_started = time.monotonic()
        base.write_event(handle, "yew_route_step_start", {
            "reason": reason,
            "target": SEERS_YEW,
            "step": index,
            "tile": tile,
            "stopDistance": stop_distance,
            "player": base.compact_player(player),
        })
        result = base.call_tool("walk_to_tile_until_arrived_XS", {
            "x": int(tile["x"]),
            "y": int(tile["y"]),
            "height": int(tile.get("height", 0)),
            "maxTicks": args.local_route_ticks,
            "maxWalkDistance": args.local_route_distance,
            "stopOnStall": True,
            "stopDistance": stop_distance,
        })
        player = base.bridge._player_from_or(result, player)
        base.write_event(handle, "yew_route_step", {
            "reason": reason,
            "target": SEERS_YEW,
            "step": index,
            "tile": tile,
            "success": bool(result.get("success")),
            "batchStatus": result.get("batchStatus"),
            "batchTicks": result.get("batchTicks"),
            "stopDistance": stop_distance,
            "durationMs": int((time.monotonic() - step_started) * 1000),
            "player": base.compact_player(player),
        })
        if not result.get("success", False):
            raise RuntimeError("yew route stalled at {}".format(base.compact_player(player)["tile"]))
    base.write_status(args, "routed", player, {"target": SEERS_YEW})
    return player


def route_to(target, args, handle, reason, player=None):
    if str(target) == SEERS_YEW:
        return route_to_yew(args, handle, reason, player=player)
    return _ORIGINAL_ROUTE_TO(target, args, handle, reason, player=player)


def with_default(argv, flag, value=None):
    argv = list(argv)
    if any(arg == flag or arg.startswith(flag + "=") for arg in argv):
        return argv
    if value is None:
        argv.append(flag)
    else:
        argv.extend([flag, str(value)])
    return argv


def yew_argv(argv):
    args = list(argv or [])
    args = with_default(args, "--tree", "Yew")
    args = with_default(args, "--chop-anchor", SEERS_YEW)
    args = with_default(args, "--target-woodcutting-level", 99)
    args = with_default(args, "--target-fletching-level", 99)
    args = with_default(args, "--target-coins", 0)
    args = with_default(args, "--max-cycles", 1000000)
    args = with_default(args, "--tree-max-distance", 20)
    args = with_default(args, "--chop-ticks", 2400)
    args = with_default(args, "--chop-round-ticks", 250)
    args = with_default(args, "--sell-every-trips", 0)
    args = with_default(args, "--sell-at-free-slots", 0)
    args = with_default(args, "--bank-products")
    args = with_default(args, "--no-final-sell")
    args = with_default(args, "--pickup-bird-nests")
    args = with_default(args, "--quiet")
    return args


def apply_overrides():
    base.RUNS_DIR = base.ROOT / "data" / "fletching" / "seers-yew-runs"
    base.RS_TOOL = base.SCRIPT_DIR / "rs-tool_XS.sh"
    base.SEERS_TILES[SEERS_YEW] = YEW_ANCHOR
    base.runner_stem = runner_stem
    base.status_path = status_path
    base.stop_path = stop_path
    base.write_status = write_status
    base.print_status = print_status
    base.print_shutdown_status = print_shutdown_status
    base.request_stop = request_stop
    base.observe = observe_compact
    base.close_interfaces_if_needed = close_interfaces_if_needed
    base.chop_anchor_for_tree = chop_anchor_for_tree
    base.route_to = route_to


def main(argv=None):
    apply_overrides()
    argv = yew_argv(sys.argv[1:] if argv is None else argv)
    if "--route-evidence-jsonl" not in argv:
        profile = ""
        for index, arg in enumerate(argv):
            if arg == "--profile" and index + 1 < len(argv):
                profile = argv[index + 1]
                break
            if arg.startswith("--profile="):
                profile = arg.split("=", 1)[1]
                break
        if profile:
            path = run_evidence_path(profile, "seers-yew-longbow-runner")
            argv.extend(["--route-evidence-jsonl", str(path)])
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
