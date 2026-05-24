#!/usr/bin/env python3
"""Evaluate learned 2006Scape routes before spending gameplay time on them.

This is a deterministic planner-quality check, not a gameplay actor. It uses
the same graph as router.py, then reports rough tick cost, route/direct ratio,
wrong-way movement, and detour hotspots so the agent can decide when to inspect
a bounded context map or test a shortcut.
"""

import argparse
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import navdb  # noqa: E402
import router  # noqa: E402


def tile_str(tile):
    return navdb.tile_str(tile)


def sign(value):
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def edge_tick_estimate(left_tile, right_tile, edge):
    meta = edge.get("meta", {})
    source = edge.get("source")
    if source == router.TRACE_SOURCE and meta.get("averageTicks") is not None:
        return float(meta["averageTicks"])
    if source in (router.ROUTE_SOURCE, router.SNAP_SOURCE):
        return float(meta.get("distance") or navdb.distance(left_tile, right_tile) or 1)
    return float(meta.get("baseCost") or edge.get("cost") or navdb.distance(left_tile, right_tile) or 1)


def path_distance(tiles):
    return sum(navdb.distance(left, right) for left, right in zip(tiles, tiles[1:]))


def path_bounds(tiles):
    if not tiles:
        return None
    return {
        "minX": min(tile["x"] for tile in tiles),
        "maxX": max(tile["x"] for tile in tiles),
        "minY": min(tile["y"] for tile in tiles),
        "maxY": max(tile["y"] for tile in tiles),
    }


def source_summary(edges):
    counts = {}
    for _left, _right, edge in edges:
        source = edge.get("source", "unknown")
        counts[source] = counts.get(source, 0) + 1
    return counts


def route_counts(edges):
    counts = {}
    for _left, _right, edge in edges:
        route_id = edge.get("meta", {}).get("route")
        if route_id:
            counts[route_id] = counts.get(route_id, 0) + 1
    return counts


def wrong_way_flags(tiles, target_tile, max_edges=24):
    if len(tiles) < 2:
        return []
    start = tiles[0]
    target_x_delta = target_tile["x"] - start["x"]
    target_y_delta = target_tile["y"] - start["y"]
    target_dx = sign(target_x_delta) if abs(target_x_delta) >= 32 else 0
    target_dy = sign(target_y_delta) if abs(target_y_delta) >= 32 else 0
    wrong_x = 0
    wrong_y = 0
    sampled = list(zip(tiles, tiles[1:]))[:max_edges]
    for left, right in sampled:
        dx = sign(right["x"] - left["x"])
        dy = sign(right["y"] - left["y"])
        if target_dx and dx and dx != target_dx:
            wrong_x += abs(right["x"] - left["x"])
        if target_dy and dy and dy != target_dy:
            wrong_y += abs(right["y"] - left["y"])
    flags = []
    if wrong_x >= 12:
        flags.append({
            "type": "early_wrong_x",
            "amount": wrong_x,
            "message": "early route moves {} tiles opposite target x direction".format(wrong_x),
        })
    if wrong_y >= 12:
        flags.append({
            "type": "early_wrong_y",
            "amount": wrong_y,
            "message": "early route moves {} tiles opposite target y direction".format(wrong_y),
        })
    return flags


def detour_segments(tiles, target_tile, min_increase=18, max_segments=5):
    if len(tiles) < 3:
        return []
    segments = []
    previous_distance = navdb.distance(tiles[0], target_tile)
    for index, tile in enumerate(tiles[1:], start=1):
        distance_to_target = navdb.distance(tile, target_tile)
        increase = distance_to_target - previous_distance
        if increase >= min_increase:
            segments.append({
                "index": index,
                "tile": tile,
                "distanceToTarget": distance_to_target,
                "increase": increase,
                "message": "distance to target increased by {} at {}".format(increase, tile_str(tile)),
            })
            if len(segments) >= max_segments:
                break
        previous_distance = distance_to_target
    return segments


def quality_level(detour_ratio, distance_increase_count, wrong_way_count):
    if detour_ratio >= 2.4 or (detour_ratio >= 1.8 and distance_increase_count >= 6):
        return "bad"
    if detour_ratio >= 1.65 or (detour_ratio >= 1.35 and distance_increase_count >= 3) or wrong_way_count >= 1:
        return "suspicious"
    if detour_ratio >= 1.25 or distance_increase_count >= 1:
        return "watch"
    return "ok"


def common_router_namespace(args, from_tile, to):
    return SimpleNamespace(
        from_tile=from_tile,
        to=to,
        combat_level=args.combat_level,
        food=args.food,
        coins=args.coins,
        run_energy=args.run_energy,
        run_enabled=args.run_enabled,
        allow_lethal=args.allow_lethal,
        allow_failed_traces=args.allow_failed_traces,
        include_partial=args.include_partial,
        include_derived=args.include_derived,
        include_unverified=args.include_unverified,
        trace_file=args.trace_file,
        trace_profile=args.trace_profile,
        include_unscoped_traces=args.include_unscoped_traces,
        graph_snap_distance=args.graph_snap_distance,
        hazard_buffer=args.hazard_buffer,
        failure_buffer=args.failure_buffer,
        max_static_leg=args.max_static_leg,
        max_batch_distance=args.max_batch_distance,
        compress_gap=args.compress_gap,
        max_warnings=args.max_warnings,
        json=False,
    )


def evaluate(args, from_value=None, to_value=None):
    from_value = from_value or args.from_tile
    to_value = to_value or args.to
    db = navdb.load_db()
    plan_args = common_router_namespace(args, from_value, to_value)
    start_tile, start_label = router.parse_tile_or_place(db, plan_args.from_tile)
    target_place = router.target_place_from_arg(db, plan_args.to)
    graph = router.build_hybrid_graph(db, plan_args)
    start_key = router.connect_virtual_start(graph, start_tile, plan_args.graph_snap_distance)
    target_keys = router.target_keys_for_place(graph, target_place)
    end_key, dist, previous, settled = router.dijkstra(graph, start_key, target_keys)

    base = {
        "from": start_label,
        "to": target_place["id"],
        "targetTile": target_place["tile"],
        "traceRecords": graph["traceRecordCount"],
        "traceSessions": graph["traceSessionCount"],
        "connectedNodes": len(settled),
    }
    if end_key is None:
        frontier = router.nearest_reachable_frontier(
            graph,
            target_place["tile"],
            dist,
            start_tile=start_tile,
            previous=previous,
            max_batch_distance=plan_args.max_batch_distance,
        )
        base["status"] = "no-learned-route"
        if frontier:
            _score, frontier_key, frontier_tile, frontier_score_details = frontier
            keys, edges = router.reconstruct(previous, frontier_key)
            tiles = [graph["nodes"][key] for key in keys]
            base.update({
                "frontierTile": frontier_tile,
                "frontierDistanceToTarget": navdb.distance(frontier_tile, target_place["tile"]),
                "reachableCost": round(dist.get(frontier_key, math.inf), 2),
                "reachableDistance": path_distance(tiles),
                "next": router.first_batch_target(graph, keys, plan_args.max_batch_distance) if len(keys) > 1 else frontier_tile,
                "frontierScore": frontier_score_details,
                "edgeSources": source_summary(edges),
            })
        return base

    keys, edges = router.reconstruct(previous, end_key)
    tiles = [graph["nodes"][key] for key in keys]
    direct_distance = navdb.distance(start_tile, target_place["tile"])
    route_distance = path_distance(tiles)
    tick_estimate = 0.0
    target_distance_increases = 0
    previous_distance = navdb.distance(tiles[0], target_place["tile"]) if tiles else 0
    for left_key, right_key, edge in edges:
        left_tile = graph["nodes"][left_key]
        right_tile = graph["nodes"][right_key]
        tick_estimate += edge_tick_estimate(left_tile, right_tile, edge)
        next_distance = navdb.distance(right_tile, target_place["tile"])
        if next_distance > previous_distance:
            target_distance_increases += 1
        previous_distance = next_distance
    wrong_way = wrong_way_flags(tiles, target_place["tile"])
    suspects = detour_segments(tiles, target_place["tile"], max_segments=args.max_suspects)
    detour_ratio = route_distance / max(1, direct_distance)
    base.update({
        "status": "ok",
        "cost": round(dist[end_key], 2),
        "estimatedTicks": round(tick_estimate, 1),
        "directDistance": direct_distance,
        "routeDistance": route_distance,
        "detourRatio": round(detour_ratio, 3),
        "quality": quality_level(detour_ratio, target_distance_increases, len(wrong_way)),
        "edgeCount": len(edges),
        "edgeSources": source_summary(edges),
        "routesUsed": route_counts(edges),
        "targetDistanceIncreases": target_distance_increases,
        "bounds": path_bounds(tiles),
        "next": router.first_batch_target(graph, keys, args.max_batch_distance) if len(keys) > 1 else tiles[0],
        "waypoints": router.compress_waypoints(graph, keys, args.compress_gap),
        "wrongWayFlags": wrong_way,
        "detourSegments": suspects,
    })
    if base["quality"] in ("suspicious", "bad"):
        center = suspects[0]["tile"] if suspects else base["next"]
        base["recommendedMapCommand"] = (
            "python3 agent-navigation/tools/render_agent_context_map.py "
            "--center {} --radius-tiles 80 --pixels-per-tile 4"
        ).format(tile_str(center))
    return base


def combine_via(args, via):
    first = evaluate(args, args.from_tile, via)
    second = evaluate(args, via, args.to)
    ok = first.get("status") == "ok" and second.get("status") == "ok"
    combined = {
        "via": via,
        "status": "ok" if ok else "incomplete",
        "first": first,
        "second": second,
    }
    if ok:
        combined.update({
            "estimatedTicks": round(first["estimatedTicks"] + second["estimatedTicks"], 1),
            "routeDistance": first["routeDistance"] + second["routeDistance"],
            "cost": round(first["cost"] + second["cost"], 2),
            "quality": quality_level(
                (first["routeDistance"] + second["routeDistance"]) / max(1, first["directDistance"] + second["directDistance"]),
                first["targetDistanceIncreases"] + second["targetDistanceIncreases"],
                len(first["wrongWayFlags"]) + len(second["wrongWayFlags"]),
            ),
        })
    return combined


def print_eval(result):
    print("route-eval: {} -> {} | status={}".format(result["from"], result["to"], result["status"]))
    print("data: traces={} sessions={} connectedNodes={}".format(
        result["traceRecords"], result["traceSessions"], result["connectedNodes"]))
    if result["status"] != "ok":
        if "frontierTile" in result:
            print("frontier: {} remainingDistance={} reachableCost={}".format(
                tile_str(result["frontierTile"]), result["frontierDistanceToTarget"], result["reachableCost"]))
        return
    print("quality={} cost={} estTicks={} direct={} routeDistance={} detourRatio={}".format(
        result["quality"], result["cost"], result["estimatedTicks"],
        result["directDistance"], result["routeDistance"], result["detourRatio"]))
    print("next:", tile_str(result["next"]))
    if result.get("edgeSources"):
        print("sources:", " ".join("{}={}".format(key, value) for key, value in sorted(result["edgeSources"].items())))
    if result.get("routesUsed"):
        routes = ", ".join("{}:{}".format(key, value) for key, value in sorted(result["routesUsed"].items())[:8])
        print("routes:", routes)
    flags = [flag["message"] for flag in result.get("wrongWayFlags", [])]
    flags.extend(segment["message"] for segment in result.get("detourSegments", []))
    if flags:
        print("flags:")
        for flag in flags[:8]:
            print("  {}".format(flag))
    if result.get("recommendedMapCommand"):
        print("map:", result["recommendedMapCommand"])


def print_via(result):
    print("via {} | status={}".format(result["via"], result["status"]))
    if result["status"] == "ok":
        print("  quality={} cost={} estTicks={} routeDistance={}".format(
            result["quality"], result["cost"], result["estimatedTicks"], result["routeDistance"]))
    else:
        print("  first={} second={}".format(result["first"].get("status"), result["second"].get("status")))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Score learned route quality before live movement.")
    router.add_common_args(parser)
    parser.add_argument("--via", action="append", help="Compare route through this tile/place.")
    parser.add_argument("--max-suspects", type=int, default=5)
    args = parser.parse_args(argv)
    result = evaluate(args)
    via_results = [combine_via(args, via) for via in (args.via or [])]
    if args.json:
        payload = dict(result)
        if via_results:
            payload["viaComparisons"] = via_results
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_eval(result)
        for via_result in via_results:
            print_via(via_result)
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
