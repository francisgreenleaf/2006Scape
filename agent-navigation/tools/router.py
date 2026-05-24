#!/usr/bin/env python3
"""Compact route planner over live movement traces, places, routes, and hazards.

This is intentionally a planner, not a gameplay actor.  It answers:

  - What is the best learned path from A to B?
  - What is the next low-token waypoint?
  - If B is not connected yet, what frontier gets us closest?

The planner defaults to evidence-backed movement traces plus verified route DB
segments.  Derived/static route hints are opt-in because they are useful for
frontier discovery but dangerous as navigation truth.
"""

import argparse
import heapq
import json
import math
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import navdb  # noqa: E402


SAFE_ROUTE_STATUSES = set(["verified", "learned-graph"])
PARTIAL_ROUTE_STATUSES = set(["learned-partial"])
DERIVED_ROUTE_STATUSES = set(["derived-from-existing-landmark"])
UNVERIFIED_ROUTE_STATUSES = set(["needs-verification"])
BLOCKED_ROUTE_STATUSES = set(["blocked", "failed"])

TRACE_SOURCE = "trace"
ROUTE_SOURCE = "route"
SNAP_SOURCE = "snap"


def parse_tile_or_place(db, value):
    if "," in value:
        return navdb.tile_from_arg(value), value
    place = navdb.find_place(db, value)
    if not place:
        raise SystemExit("unknown place or tile: {}".format(value))
    return place["tile"], place["id"]


def target_place_from_arg(db, value):
    target = navdb.place_or_tile_target(db, value)
    if not target:
        raise SystemExit("target place or tile not found: {}".format(value))
    return target


def tile_key(tile):
    return navdb.tile_key(tile)


def tile_str(tile):
    return navdb.tile_str(tile)


def distance(a, b):
    return navdb.distance(a, b)


def sign(value):
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def path_distance_for_keys(graph, keys):
    nodes = graph["nodes"]
    total = 0
    for left_key, right_key in zip(keys, keys[1:]):
        total += distance(nodes[left_key], nodes[right_key])
    return total


def directional_progress(start_tile, candidate_tile, target_tile, min_axis_delta=16):
    """Return target-axis progress and wrong-way travel from start to candidate."""
    progress = 0
    wrong = 0
    active_axes = 0
    for axis in ("x", "y"):
        target_delta = target_tile[axis] - start_tile[axis]
        if abs(target_delta) < min_axis_delta:
            continue
        active_axes += 1
        aligned = (candidate_tile[axis] - start_tile[axis]) * sign(target_delta)
        if aligned >= 0:
            progress += aligned
        else:
            wrong += -aligned
    return progress, wrong, active_axes


def hazard_severity(hazard):
    risk = navdb.norm(hazard.get("risk", ""))
    if any(word in risk for word in ("death", "lethal", "deadly")):
        return 10000.0
    if any(word in risk for word in ("high", "combat contact")):
        return 650.0
    if "medium" in risk:
        return 120.0
    if "low" in risk:
        return 15.0
    return 60.0


def hazard_penalty(db, tile, args):
    penalty = 0.0
    warnings = []
    for dist, hazard in navdb.hazards_near(db, tile, args.hazard_buffer):
        risk_warnings = navdb.risk_warnings(
            hazard,
            args.combat_level,
            args.food,
            coins=args.coins,
            run_energy=args.run_energy,
            run_enabled=args.run_enabled,
        )
        if not risk_warnings:
            continue
        severity = hazard_severity(hazard)
        penalty += severity
        warnings.append({
            "id": hazard["id"],
            "risk": hazard.get("risk", "unknown"),
            "distance": dist,
            "warnings": risk_warnings,
        })
    return penalty, warnings


def failure_tiles(args):
    tiles = []
    for record in navdb.iter_movement_traces(
            args.trace_file, args.trace_profile, args.include_unscoped_traces):
        if (navdb.is_trace_failure(record)
                or record.get("isInCombat") is True
                or int(record.get("hitpointsLost") or 0) > 0):
            tile = navdb.tile_from_record(record, "tile")
            if tile:
                tiles.append({
                    "tile": tile,
                    "event": record.get("event") or record.get("batchStatus") or "failure",
                    "target": navdb.target_tile_from_record(record),
                })
    return tiles


def failure_penalty(failures, tile, args):
    if args.allow_failed_traces:
        return 0.0, []
    warnings = []
    penalty = 0.0
    for failure in failures:
        dist = distance(tile, failure["tile"])
        if dist <= args.failure_buffer:
            penalty += 8000.0
            warning = {
                "id": "trace_failure_zone",
                "risk": "recent-failure",
                "distance": dist,
                "warnings": [
                    "near {} at {}".format(failure["event"], tile_str(failure["tile"]))
                ],
            }
            if failure.get("target"):
                warning["warnings"].append("failed target {}".format(tile_str(failure["target"])))
            warnings.append(warning)
    return penalty, warnings


def clean_trace_edge(trace_edge):
    return (
        trace_edge.get("successes", 0) > 0
        and trace_edge.get("failures", 0) == 0
        and trace_edge.get("combatTicks", 0) == 0
        and trace_edge.get("hitpointsLost", 0) == 0
    )


def evidence_adjusted_penalty(trace_edge, hazard_cost, failure_cost, args):
    if not clean_trace_edge(trace_edge):
        return hazard_cost, failure_cost, False
    adjusted = False
    if hazard_cost >= 8000.0 and not args.allow_lethal:
        hazard_cost = 25.0
        adjusted = True
    if failure_cost >= 8000.0 and not args.allow_failed_traces:
        failure_cost = 100.0
        adjusted = True
    return hazard_cost, failure_cost, adjusted


def edge_record(to_key, cost, source, meta=None):
    return {"to": to_key, "cost": float(cost), "source": source, "meta": meta or {}}


def add_edge(adjacency, from_key, to_key, cost, source, meta=None):
    if from_key == to_key:
        return
    adjacency.setdefault(from_key, []).append(edge_record(to_key, cost, source, meta))


def trace_edge_meta(trace_edge, evidence_adjusted):
    meta = {
        "successes": trace_edge.get("successes", 0),
        "failures": trace_edge.get("failures", 0),
        "combatTicks": trace_edge.get("combatTicks", 0),
        "hitpointsLost": trace_edge.get("hitpointsLost", 0),
        "ticks": trace_edge.get("ticks", 0),
        "averageTicks": float(trace_edge.get("ticks", 0)) / max(1, trace_edge.get("successes", 0)),
        "baseCost": navdb.edge_cost(trace_edge),
        "evidenceAdjustedRisk": evidence_adjusted,
    }
    if trace_edge.get("objectInteractions", 0) > 0:
        meta["objectInteractions"] = trace_edge.get("objectInteractions", 0)
        meta["objects"] = trace_edge.get("objects", {})
        meta["objectOptions"] = trace_edge.get("objectOptions", {})
        meta["objectPhases"] = trace_edge.get("objectPhases", {})
    return meta


def allowed_route_statuses(args):
    statuses = set(SAFE_ROUTE_STATUSES)
    if args.include_partial:
        statuses.update(PARTIAL_ROUTE_STATUSES)
    if args.include_derived:
        statuses.update(DERIVED_ROUTE_STATUSES)
    if args.include_unverified:
        statuses.update(UNVERIFIED_ROUTE_STATUSES)
    return statuses


def route_status_penalty(status):
    if status in SAFE_ROUTE_STATUSES:
        return 0.0
    if status in PARTIAL_ROUTE_STATUSES:
        return 80.0
    if status in DERIVED_ROUTE_STATUSES:
        return 300.0
    if status in UNVERIFIED_ROUTE_STATUSES:
        return 900.0
    return 2000.0


def route_tiles(db, route):
    tiles = []
    from_place = navdb.find_place(db, route.get("from", ""))
    to_place = navdb.find_place(db, route.get("to", ""))
    if from_place:
        tiles.append(from_place["tile"])
    for _step, tile in navdb.route_walk_tiles(route):
        if not tiles or tile_key(tiles[-1]) != tile_key(tile):
            tiles.append(tile)
    if to_place and (not tiles or tile_key(tiles[-1]) != tile_key(to_place["tile"])):
        tiles.append(to_place["tile"])
    return tiles


def build_hybrid_graph(db, args):
    trace_graph = navdb.build_trace_graph(
        args.trace_file, args.trace_profile, args.include_unscoped_traces)
    failures = failure_tiles(args)
    nodes = dict(trace_graph["nodes"])
    adjacency = {}
    skipped_routes = []
    hazard_warnings_by_key = {}

    for (from_key, to_key), trace_edge in trace_graph["edges"].items():
        if trace_edge.get("successes", 0) <= 0:
            continue
        to_tile = nodes[to_key]
        hazard_cost, warnings = hazard_penalty(db, to_tile, args)
        failure_cost, failure_warnings = failure_penalty(failures, to_tile, args)
        hazard_cost, failure_cost, evidence_adjusted = evidence_adjusted_penalty(
            trace_edge, hazard_cost, failure_cost, args)
        penalty = hazard_cost + failure_cost
        warnings.extend(failure_warnings)
        if warnings:
            hazard_warnings_by_key.setdefault(to_key, []).extend(warnings)
        if penalty >= 8000.0 and not args.allow_lethal:
            continue
        add_edge(
            adjacency,
            from_key,
            to_key,
            navdb.edge_cost(trace_edge) + penalty,
            TRACE_SOURCE,
            trace_edge_meta(trace_edge, evidence_adjusted),
        )

    statuses = allowed_route_statuses(args)
    for route in db["routes"]:
        status = route.get("status", "unknown")
        if status in BLOCKED_ROUTE_STATUSES or status not in statuses:
            skipped_routes.append({"id": route["id"], "status": status})
            continue
        tiles = route_tiles(db, route)
        if len(tiles) < 2:
            continue
        base_penalty = route_status_penalty(status)
        for left, right in zip(tiles, tiles[1:]):
            if distance(left, right) > args.max_static_leg:
                skipped_routes.append({
                    "id": route["id"],
                    "status": status,
                    "reason": "static leg too long",
                    "from": tile_str(left),
                    "to": tile_str(right),
                    "distance": distance(left, right),
                })
                continue
            left_key = tile_key(left)
            right_key = tile_key(right)
            nodes[left_key] = left
            nodes[right_key] = right
            penalty, warnings = hazard_penalty(db, right, args)
            if status not in SAFE_ROUTE_STATUSES:
                failure_cost, failure_warnings = failure_penalty(failures, right, args)
                penalty += failure_cost
                warnings.extend(failure_warnings)
            if warnings:
                hazard_warnings_by_key.setdefault(right_key, []).extend(warnings)
            if penalty >= 8000.0 and not args.allow_lethal:
                continue
            cost = max(1.0, distance(left, right)) + base_penalty + penalty
            add_edge(
                adjacency,
                left_key,
                right_key,
                cost,
                ROUTE_SOURCE,
                {
                    "route": route["id"],
                    "status": status,
                    "distance": distance(left, right),
                    "baseCost": max(1.0, distance(left, right)),
                },
            )
            if route.get("bidirectional"):
                add_edge(
                    adjacency,
                    right_key,
                    left_key,
                    cost,
                    ROUTE_SOURCE,
                    {
                        "route": route["id"],
                        "status": status,
                        "distance": distance(left, right),
                        "baseCost": max(1.0, distance(left, right)),
                    },
                )

    return {
        "nodes": nodes,
        "adjacency": adjacency,
        "traceRecordCount": trace_graph["recordCount"],
        "traceSessionCount": trace_graph["traceCount"],
        "skippedRoutes": skipped_routes,
        "hazardWarningsByKey": hazard_warnings_by_key,
    }


def connect_virtual_start(graph, start_tile, snap_distance):
    nodes = graph["nodes"]
    adjacency = graph["adjacency"]
    start_key = tile_key(start_tile)
    nodes[start_key] = start_tile
    if adjacency.get(start_key):
        return start_key
    for key, tile in list(nodes.items()):
        if key == start_key:
            continue
        dist = distance(start_tile, tile)
        if dist <= snap_distance:
            add_edge(adjacency, start_key, key, max(1.0, dist), SNAP_SOURCE, {"distance": dist})
    return start_key


def target_keys_for_place(graph, target_place):
    radius = target_place.get("arrivalRadius", 1)
    target_tile = target_place["tile"]
    keys = set()
    for key, tile in graph["nodes"].items():
        if distance(tile, target_tile) <= radius:
            keys.add(key)
    return keys


def dijkstra(graph, start_key, target_keys=None):
    adjacency = graph["adjacency"]
    frontier = [(0.0, start_key)]
    dist = {start_key: 0.0}
    previous = {}
    settled = set()
    while frontier:
        cost, key = heapq.heappop(frontier)
        if key in settled:
            continue
        settled.add(key)
        if target_keys and key in target_keys:
            return key, dist, previous, settled
        for edge in adjacency.get(key, []):
            next_key = edge["to"]
            next_cost = cost + edge["cost"]
            if next_cost >= dist.get(next_key, math.inf):
                continue
            dist[next_key] = next_cost
            previous[next_key] = (key, edge)
            heapq.heappush(frontier, (next_cost, next_key))
    return None, dist, previous, settled


def reconstruct(previous, end_key):
    edges = []
    key = end_key
    while key in previous:
        prev_key, edge = previous[key]
        edges.append((prev_key, key, edge))
        key = prev_key
    edges.reverse()
    if not edges:
        return [end_key], []
    keys = [edges[0][0]]
    for _prev, to_key, _edge in edges:
        keys.append(to_key)
    return keys, edges


def direction(a, b):
    dx = b["x"] - a["x"]
    dy = b["y"] - a["y"]
    if dx:
        dx = 1 if dx > 0 else -1
    if dy:
        dy = 1 if dy > 0 else -1
    return dx, dy, b.get("height", 0) - a.get("height", 0)


def compress_waypoints(graph, keys, max_gap):
    if not keys:
        return []
    nodes = graph["nodes"]
    kept = [keys[0]]
    last_dir = None
    last_keep = keys[0]
    for prev_key, key in zip(keys, keys[1:]):
        step_dir = direction(nodes[prev_key], nodes[key])
        gap = distance(nodes[last_keep], nodes[key])
        if last_dir is None:
            last_dir = step_dir
        if step_dir != last_dir or gap >= max_gap:
            if kept[-1] != prev_key:
                kept.append(prev_key)
            last_keep = prev_key
            last_dir = step_dir
    if kept[-1] != keys[-1]:
        kept.append(keys[-1])
    return [nodes[key] for key in kept]


def first_batch_target(graph, keys, max_distance):
    if len(keys) <= 1:
        return graph["nodes"][keys[0]]
    start = graph["nodes"][keys[0]]
    best = graph["nodes"][keys[1]]
    for key in keys[1:]:
        tile = graph["nodes"][key]
        if distance(start, tile) > max_distance:
            break
        best = tile
    return best


def source_summary(edges):
    counts = {}
    route_counts = {}
    for _left, _right, edge in edges:
        counts[edge["source"]] = counts.get(edge["source"], 0) + 1
        route_id = edge.get("meta", {}).get("route")
        if route_id:
            route_counts[route_id] = route_counts.get(route_id, 0) + 1
    return counts, route_counts


def compact_counter(counter, limit=5):
    return [
        {"key": key, "count": value}
        for key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def object_steps_for_path(graph, edges):
    steps = []
    for from_key, to_key, edge in edges:
        meta = edge.get("meta", {})
        if meta.get("objectInteractions", 0) <= 0:
            continue
        steps.append({
            "from": graph["nodes"].get(from_key),
            "to": graph["nodes"].get(to_key),
            "source": edge.get("source"),
            "objectInteractions": meta.get("objectInteractions", 0),
            "objects": compact_counter(meta.get("objects", {})),
            "options": compact_counter(meta.get("objectOptions", {})),
            "phases": compact_counter(meta.get("objectPhases", {})),
        })
    return steps


def frontier_score(graph, target_tile, dist, key, start_tile=None, previous=None, max_batch_distance=24):
    tile = graph["nodes"][key]
    rem = distance(tile, target_tile)
    cost = dist.get(key, math.inf)
    score = float(rem) + (min(cost, 10000.0) * 0.05)
    details = {
        "remainingDistance": rem,
        "reachableCost": round(cost, 2) if math.isfinite(cost) else None,
    }
    if not start_tile or start_tile.get("height", 0) != target_tile.get("height", 0):
        details["score"] = round(score, 2)
        return (score, rem, cost, key), details

    keys = [key]
    if previous is not None:
        keys, _edges = reconstruct(previous, key)
    next_tile = first_batch_target(graph, keys, max_batch_distance) if keys else tile
    start_remaining = distance(start_tile, target_tile)
    distance_progress = start_remaining - rem
    first_step_progress = start_remaining - distance(next_tile, target_tile)
    direct_frontier_distance = distance(start_tile, tile)
    route_distance = path_distance_for_keys(graph, keys)
    directional, wrong_way, active_axes = directional_progress(start_tile, tile, target_tile)
    first_directional, first_wrong_way, _active_axes = directional_progress(
        start_tile, next_tile, target_tile)

    details.update({
        "startDistanceToTarget": start_remaining,
        "distanceProgress": distance_progress,
        "directionalProgress": directional,
        "wrongWayDistance": wrong_way,
        "firstStepDistanceProgress": first_step_progress,
        "firstStepDirectionalProgress": first_directional,
        "firstStepWrongWayDistance": first_wrong_way,
        "firstStepTile": next_tile,
        "routeDistance": route_distance,
        "directFrontierDistance": direct_frontier_distance,
    })

    if distance_progress <= 0:
        score += 5000.0 + (abs(distance_progress) * 80.0)
    if active_axes and directional <= 0:
        score += 2500.0 + (abs(directional) * 80.0)
    score += wrong_way * 40.0
    if first_step_progress < -2:
        score += 400.0 + (abs(first_step_progress) * 40.0)
    elif first_step_progress <= 0:
        score += 100.0
    score += first_wrong_way * 60.0
    if route_distance and direct_frontier_distance:
        score += max(0.0, route_distance - (direct_frontier_distance * 1.8)) * 0.25
    if route_distance and directional > 0:
        efficiency = float(route_distance) / max(1.0, float(directional))
        if efficiency > 4.0:
            score += (efficiency - 4.0) * 25.0
            details["directionalEfficiency"] = round(efficiency, 2)

    details["score"] = round(score, 2)
    return (score, rem, cost, key), details


def nearest_reachable_frontier(graph, target_tile, dist, start_tile=None, previous=None, max_batch_distance=24):
    best = None
    for key, cost in dist.items():
        tile = graph["nodes"].get(key)
        if not tile or tile.get("height", 0) != target_tile.get("height", 0):
            continue
        score, details = frontier_score(
            graph,
            target_tile,
            dist,
            key,
            start_tile=start_tile,
            previous=previous,
            max_batch_distance=max_batch_distance,
        )
        if best is None or score < best[0]:
            best = (score, key, tile, details)
    return best


def build_plan(args):
    db = navdb.load_db()
    start_tile, start_label = parse_tile_or_place(db, args.from_tile)
    target_place = target_place_from_arg(db, args.to)

    graph = build_hybrid_graph(db, args)
    start_key = connect_virtual_start(graph, start_tile, args.graph_snap_distance)
    target_keys = target_keys_for_place(graph, target_place)
    end_key, dist, previous, settled = dijkstra(graph, start_key, target_keys)

    plan = {
        "from": start_label,
        "to": target_place["id"],
        "targetTile": target_place["tile"],
        "traceRecords": graph["traceRecordCount"],
        "traceSessions": graph["traceSessionCount"],
        "traceProfile": args.trace_profile or "",
        "connectedNodes": len(settled),
        "mode": "safe" if not args.allow_lethal else "allow-lethal",
        "includes": {
            "partialRoutes": args.include_partial,
            "derivedRoutes": args.include_derived,
            "unverifiedRoutes": args.include_unverified,
        },
    }

    if end_key is None:
        best = nearest_reachable_frontier(
            graph,
            target_place["tile"],
            dist,
            start_tile=start_tile,
            previous=previous,
            max_batch_distance=args.max_batch_distance,
        )
        plan["status"] = "no-learned-route"
        if best:
            _score, frontier_key, frontier_tile, frontier_score_details = best
            keys, edges = reconstruct(previous, frontier_key)
            waypoints = compress_waypoints(graph, keys, args.compress_gap)
            plan.update({
                "frontierTile": frontier_tile,
                "frontierDistanceToTarget": distance(frontier_tile, target_place["tile"]),
                "frontierCost": round(dist.get(frontier_key, math.inf), 2),
                "frontierScore": frontier_score_details,
                "next": first_batch_target(graph, keys, args.max_batch_distance) if len(keys) > 1 else frontier_tile,
                "waypoints": waypoints,
                "edgeSources": source_summary(edges)[0],
                "objectSteps": object_steps_for_path(graph, edges),
            })
        return plan

    keys, edges = reconstruct(previous, end_key)
    warnings = []
    for _prev_key, to_key, edge in edges:
        for warning in graph["hazardWarningsByKey"].get(to_key, []):
            if (warning.get("id") == "trace_failure_zone"
                    and edge.get("source") == ROUTE_SOURCE
                    and edge.get("meta", {}).get("status") in SAFE_ROUTE_STATUSES):
                continue
            warnings.append(warning)
    source_counts, route_counts = source_summary(edges)
    plan.update({
        "status": "ok",
        "cost": round(dist[end_key], 2),
        "endTile": graph["nodes"][end_key],
        "next": first_batch_target(graph, keys, args.max_batch_distance),
        "waypoints": compress_waypoints(graph, keys, args.compress_gap),
        "edgeSources": source_counts,
        "routesUsed": route_counts,
        "hazardWarnings": warnings[:args.max_warnings],
        "objectSteps": object_steps_for_path(graph, edges),
    })
    return plan


def print_text(plan):
    print("route-plan: {} -> {} | status={}".format(plan["from"], plan["to"], plan["status"]))
    print("data: traces={} sessions={} connectedNodes={}".format(
        plan["traceRecords"], plan["traceSessions"], plan["connectedNodes"]))
    print("mode: {} includes={}".format(plan["mode"], ",".join(
        key for key, enabled in plan["includes"].items() if enabled) or "verified-traces-only"))
    if plan["status"] == "ok":
        print("cost:", plan["cost"])
        print("next:", tile_str(plan["next"]))
        print("end:", tile_str(plan["endTile"]))
    else:
        if "frontierTile" not in plan:
            print("no reachable frontier from current learned graph")
            return
        print("next:", tile_str(plan["next"]))
        print("frontier:", tile_str(plan["frontierTile"]),
              "remainingDistance={}".format(plan["frontierDistanceToTarget"]))
    if plan.get("edgeSources"):
        print("sources:", " ".join("{}={}".format(k, v) for k, v in sorted(plan["edgeSources"].items())))
    if plan.get("routesUsed"):
        route_text = ", ".join("{}:{}".format(k, v) for k, v in sorted(plan["routesUsed"].items()))
        print("routes:", route_text)
    if plan.get("waypoints"):
        print("waypoints:", " ".join(tile_str(tile) for tile in plan["waypoints"][:20]))
    if plan.get("objectSteps"):
        print("object steps:")
        for step in plan["objectSteps"][:5]:
            objects = ", ".join("{}x {}".format(item["count"], item["key"]) for item in step.get("objects", []))
            options = ", ".join("{}x {}".format(item["count"], item["key"]) for item in step.get("options", []))
            print("  {} -> {} | {} {}".format(
                tile_str(step["from"]), tile_str(step["to"]), objects, ("option=" + options) if options else ""))
    if plan.get("hazardWarnings"):
        print("warnings:")
        seen = set()
        for warning in plan["hazardWarnings"]:
            key = warning["id"]
            if key in seen:
                continue
            seen.add(key)
            print("  {} risk={} dist={} {}".format(
                warning["id"], warning["risk"], warning["distance"], "; ".join(warning["warnings"])))


def cmd_plan(args):
    plan = build_plan(args)
    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print_text(plan)
    return 0 if plan["status"] == "ok" else 2


def add_common_args(parser):
    parser.add_argument("--from", dest="from_tile", required=True,
                        help="Start tile x,y,h or place id/name.")
    parser.add_argument("--to", required=True, help="Target place id/name or x,y,h tile.")
    parser.add_argument("--combat-level", type=int, default=3)
    parser.add_argument("--food", type=int, default=0)
    parser.add_argument("--coins", type=int, default=0)
    parser.add_argument("--run-energy", type=int, default=0)
    parser.add_argument("--run-enabled", action="store_true")
    parser.add_argument("--allow-lethal", action="store_true",
                        help="Allow lethal/death-confirmed hazard edges into the graph.")
    parser.add_argument("--allow-failed-traces", action="store_true",
                        help="Allow edges near recent failed/combat trace terminals.")
    parser.add_argument("--include-partial", action="store_true", default=False,
                        help="Include learned-partial routes as high-penalty hints.")
    parser.add_argument("--no-include-partial", dest="include_partial", action="store_false")
    parser.add_argument("--include-derived", action="store_true",
                        help="Include derived/static route hints. Useful for frontier planning, not proof.")
    parser.add_argument("--include-unverified", action="store_true",
                        help="Include needs-verification route hints at very high cost.")
    parser.add_argument("--trace-file", action="append")
    parser.add_argument("--trace-profile",
                        default=os.environ.get("RS_TRACE_PROFILE") or os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or "",
                        help="Only use traces recorded by this player/profile. Defaults to RS_TRACE_PROFILE or RS_PROFILE.")
    parser.add_argument("--include-unscoped-traces", action="store_true",
                        help="When filtering by profile, also include legacy traces with no player name.")
    parser.add_argument("--graph-snap-distance", type=int, default=3)
    parser.add_argument("--hazard-buffer", type=int, default=10)
    parser.add_argument("--failure-buffer", type=int, default=8)
    parser.add_argument("--max-static-leg", type=int, default=32,
                        help="Skip static route legs longer than this many tiles.")
    parser.add_argument("--max-batch-distance", type=int, default=24,
                        help="Emit a next waypoint no farther than this from the start.")
    parser.add_argument("--compress-gap", type=int, default=18)
    parser.add_argument("--max-warnings", type=int, default=8)
    parser.add_argument("--json", action="store_true")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Plan compact safe routes from learned movement data.")
    sub = parser.add_subparsers(dest="command")
    plan = sub.add_parser("plan", help="Compute an A-to-B route or nearest learned frontier.")
    add_common_args(plan)
    plan.set_defaults(func=cmd_plan)
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
