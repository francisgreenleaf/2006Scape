#!/usr/bin/env python3
import argparse
import datetime as dt
import heapq
import json
import math
import os
import shutil
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCREENSHOTS = ROOT / "screenshots"
SERVER_TRACE_ROOT = ROOT.parent / "2006Scape Server" / "data" / "logs" / "agent-movement-traces"
SERVER_PLAYER_TRACE_ROOT = ROOT.parent / "2006Scape Server" / "data" / "logs" / "player-movement-traces"
TRACE_FAILURE_EVENTS = set([
    "blocked",
    "stalled",
    "oscillation",
    "player_dead",
    "unexpected_combat",
    "max_ticks_reached",
])


def load_json(name):
    with (DATA / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_optional_json(name, default):
    path = DATA / name
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_db():
    return {
        "places": load_json("places.json").get("places", []),
        "routes": load_json("routes.json").get("routes", []),
        "hazards": load_json("hazards.json").get("hazards", []),
    }


def norm(value):
    return " ".join(str(value).strip().lower().replace("_", " ").split())


def profile_key(value):
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def default_trace_profile():
    return os.environ.get("RS_TRACE_PROFILE") or os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or ""


def record_profile_values(record, source=None):
    values = []
    for key in ("playerName", "player", "profile"):
        value = record.get(key)
        if value:
            values.append(value)
    if source:
        path = Path(source)
        if "player-movement-traces" in path.parts:
            values.append(path.stem)
    return [profile_key(value) for value in values if profile_key(value)]


def record_matches_profile(record, profile=None, source=None, include_unscoped=False):
    expected = profile_key(profile)
    if not expected:
        return True
    values = record_profile_values(record, source)
    if not values:
        return include_unscoped
    return expected in values


def tile_from_arg(value):
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("tile must be x,y,height")
    try:
        return {"x": int(parts[0]), "y": int(parts[1]), "height": int(parts[2])}
    except ValueError:
        raise argparse.ArgumentTypeError("tile must contain integers")


def bool_from_arg(value):
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "on", "enabled"):
        return True
    if text in ("0", "false", "no", "n", "off", "disabled"):
        return False
    raise argparse.ArgumentTypeError("boolean must be true or false")


def tile_str(tile):
    return "{},{},{}".format(tile["x"], tile["y"], tile["height"])


def tile_key(tile):
    return tile_str(tile)


def tile_from_key(key):
    return tile_from_arg(key)


def distance(a, b):
    if a.get("height", 0) != b.get("height", 0):
        return math.inf
    return max(abs(a["x"] - b["x"]), abs(a["y"] - b["y"]))


def place_lookup(places):
    lookup = {}
    for place in places:
        keys = [place["id"], place["name"]]
        keys.extend(place.get("aliases", []))
        for key in keys:
            lookup[norm(key)] = place
    return lookup


def find_place(db, query):
    lookup = place_lookup(db["places"])
    exact = lookup.get(norm(query))
    if exact:
        return exact
    matches = [place for key, place in lookup.items() if norm(query) in key]
    if len(matches) == 1:
        return matches[0]
    return None


def place_or_tile_target(db, query):
    if "," in query:
        tile = tile_from_arg(query)
        return {
            "id": tile_str(tile),
            "name": tile_str(tile),
            "tile": tile,
            "arrivalRadius": 1,
            "synthetic": True,
        }
    return find_place(db, query)


def route_walk_tiles(route):
    tiles = []
    for step in route.get("steps", []):
        tile = step.get("to") or step.get("near")
        if tile:
            tiles.append((step, tile))
    return tiles


OBJECT_STEP_TYPES = set([
    "interact_object",
    "object_transition",
    "door_transition",
    "gate_transition",
    "stair_transition",
    "floor_transition",
])


def is_object_step(step):
    step_type = step.get("type")
    if step_type in OBJECT_STEP_TYPES:
        return True
    name = norm(step.get("objectName", ""))
    return any(word in name for word in ("door", "gate", "trapdoor", "ladder", "stair"))


def object_step_has_transition_proof(step):
    if not is_object_step(step):
        return True
    proof = step.get("transitionProof") or {}
    required_tiles = ("preTile", "objectTile", "postTile")
    if all(key in proof for key in required_tiles):
        return True
    if all(key in step for key in required_tiles):
        return True
    state_proof = ("preTile", "objectTile", "postCondition")
    if all(key in proof for key in state_proof):
        return True
    if all(key in step for key in state_proof):
        return True
    return False


def route_transition_warnings(route):
    warnings = []
    for step in route.get("steps", []):
        if is_object_step(step) and not object_step_has_transition_proof(step):
            warnings.append(
                "route {} step {} object transition lacks pre/object/post tile proof".format(
                    route.get("id"), step.get("order")))
    return warnings


def hazards_near(db, tile, radius):
    found = []
    for hazard in db["hazards"]:
        dist = distance(tile, hazard["center"])
        if dist <= radius + hazard.get("radius", 0):
            found.append((dist, hazard))
    return sorted(found, key=lambda item: (item[0], item[1]["id"]))


def requirement_warnings(requirements, combat_level=None, food=None, coins=None,
                         run_energy=None, run_enabled=None):
    warnings = []
    min_combat = requirements.get("minCombatLevel")
    min_food = requirements.get("minFood")
    min_coins = requirements.get("coins")
    min_run_energy = requirements.get("minRunEnergy")
    requires_run = requirements.get("requiresRun")
    if combat_level is not None and min_combat is not None and combat_level < min_combat:
        warnings.append("combat {} < required {}".format(combat_level, min_combat))
    if min_food is not None and min_food > 0:
        if food is None:
            warnings.append("food unknown; required {}".format(min_food))
        elif food < min_food:
            warnings.append("food {} < required {}".format(food, min_food))
    if min_coins is not None and min_coins > 0:
        if coins is None:
            warnings.append("coins unknown; required {}".format(min_coins))
        elif coins < min_coins:
            warnings.append("coins {} < required {}".format(coins, min_coins))
    if min_run_energy is not None and min_run_energy > 0:
        if run_energy is None:
            warnings.append("run energy unknown; required {}".format(min_run_energy))
        elif run_energy < min_run_energy:
            warnings.append("run energy {} < required {}".format(run_energy, min_run_energy))
    if requires_run and run_enabled is False:
        warnings.append("run disabled but required")
    return warnings


def risk_warnings(hazard, combat_level, food, coins=None, run_energy=None, run_enabled=None):
    return requirement_warnings(
        hazard.get("requirements", {}), combat_level, food, coins, run_energy, run_enabled)


def route_requirement_warnings(route, combat_level=None, food=None, coins=None,
                               run_energy=None, run_enabled=None):
    warnings = []
    for warning in requirement_warnings(
            route.get("requirements", {}), combat_level, food, coins, run_energy, run_enabled):
        warnings.append("route wants " + warning)
    run_policy = route.get("runPolicy", {})
    policy_requirements = {}
    if run_policy.get("minEnergy") is not None:
        policy_requirements["minRunEnergy"] = run_policy.get("minEnergy")
    if run_policy.get("requiresRun"):
        policy_requirements["requiresRun"] = True
    for warning in requirement_warnings(policy_requirements, run_energy=run_energy, run_enabled=run_enabled):
        warnings.append("route wants " + warning)
    return warnings


def route_hazards(db, route, buffer_radius=0):
    tiles = route_walk_tiles(route)
    hits = []
    if not tiles:
        return hits
    for hazard in db["hazards"]:
        best = None
        for step, tile in tiles:
            dist = distance(tile, hazard["center"])
            if best is None or dist < best[0]:
                best = (dist, step, tile)
        if best and best[0] <= hazard.get("radius", 0) + buffer_radius:
            hits.append((best[0], hazard, best[1], best[2]))
    return sorted(hits, key=lambda item: (item[0], item[1]["id"]))


def env_enabled(name):
    return str(os.environ.get(name, "")).strip().lower() in ("1", "true", "yes", "on")


def trace_path_candidates(root):
    if not root.exists():
        return []
    return sorted(root.rglob("*.jsonl"))


def trace_paths(extra_paths=None, include_agent_batch=None, include_legacy_recorder=None):
    seen = set()
    candidates = []
    if extra_paths:
        candidates.extend(Path(path).expanduser() for path in extra_paths)
    player_traces = trace_path_candidates(SERVER_PLAYER_TRACE_ROOT)
    agent_traces = trace_path_candidates(SERVER_TRACE_ROOT)
    legacy_traces = sorted(DATA.glob("movement_traces*.jsonl"))

    if include_agent_batch is None:
        include_agent_batch = env_enabled("NAVDB_INCLUDE_AGENT_BATCH_TRACES") or not player_traces
    if include_legacy_recorder is None:
        include_legacy_recorder = env_enabled("NAVDB_INCLUDE_LEGACY_RECORDER_TRACES") or (
            not player_traces and not agent_traces)

    # Passive server player telemetry is the canonical route-learning stream.
    # Agent batch and legacy polling traces are useful diagnostics/fallbacks,
    # but including them by default double-counts movement already captured by
    # AgentPassiveTraceLog.
    candidates.extend(player_traces)
    if include_agent_batch:
        candidates.extend(agent_traces)
    if include_legacy_recorder:
        candidates.extend(legacy_traces)
    for path in candidates:
        nested = sorted(path.rglob("*.jsonl")) if path.is_dir() else [path]
        for item in nested:
            item = item.resolve()
            if item in seen or not item.exists():
                continue
            seen.add(item)
            yield item


def iter_jsonl(path):
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            text = line.strip()
            if not text:
                continue
            try:
                yield json.loads(text), str(path), line_no
            except json.JSONDecodeError:
                continue


def tile_from_record(record, name):
    value = record.get(name)
    if not isinstance(value, dict):
        return None
    try:
        return {
            "x": int(value["x"]),
            "y": int(value["y"]),
            "height": int(value.get("height", 0)),
        }
    except (KeyError, TypeError, ValueError):
        return None


def is_stationary_state_record(record):
    event = str(record.get("event") or record.get("batchStatus") or "").strip()
    if event != "state" or record.get("moved") is True:
        return False
    tile = tile_from_record(record, "tile")
    previous = tile_from_record(record, "previousTile")
    if tile is None:
        return False
    if previous is not None and tile_key(tile) != tile_key(previous):
        return False
    return not (
        record.get("isDead") is True
        or record.get("isInCombat") is True
        or int(record.get("hitpointsLost") or 0) > 0
    )


def target_tile_from_record(record):
    tile = tile_from_record(record, "target")
    if tile is not None:
        return tile
    arguments = record.get("arguments") if isinstance(record.get("arguments"), dict) else {}
    try:
        if "x" in arguments and "y" in arguments:
            return {
                "x": int(arguments["x"]),
                "y": int(arguments["y"]),
                "height": int(arguments.get("height", 0)),
            }
    except (TypeError, ValueError):
        return None
    return None


def iter_movement_traces(extra_paths=None, profile=None, include_unscoped=False,
                         include_agent_batch=None, include_legacy_recorder=None):
    for path in trace_paths(extra_paths, include_agent_batch, include_legacy_recorder):
        for record, source, line_no in iter_jsonl(path):
            if tile_from_record(record, "tile") is None:
                continue
            if is_stationary_state_record(record) and not env_enabled("NAVDB_INCLUDE_IDLE_STATE_TRACES"):
                continue
            if not record_matches_profile(record, profile, source, include_unscoped):
                continue
            record["_sourcePath"] = source
            record["_sourceLine"] = line_no
            yield record


def is_trace_failure(record):
    event = str(record.get("event") or record.get("batchStatus") or "").strip()
    batch_status = str(record.get("batchStatus") or "").strip()
    return event in TRACE_FAILURE_EVENTS or batch_status in TRACE_FAILURE_EVENTS or record.get("isDead") is True


def new_graph_edge(from_key, to_key):
    return {
        "from": from_key,
        "to": to_key,
        "attempts": 0,
        "successes": 0,
        "failures": 0,
        "ticks": 0,
        "runTicks": 0,
        "walkTicks": 0,
        "energySpent": 0,
        "hitpointsLost": 0,
        "combatTicks": 0,
        "tools": {},
        "events": {},
        "traceIds": {},
        "objectInteractions": 0,
        "objects": {},
        "objectOptions": {},
        "objectPhases": {},
        "lastSeen": "",
    }


def object_info_from_record(record):
    object_value = record.get("object") if isinstance(record.get("object"), dict) else {}
    object_id = record.get("objectId", object_value.get("objectId"))
    if object_id is None and record.get("event") != "object_interaction":
        return None
    try:
        object_id = int(object_id)
    except (TypeError, ValueError):
        object_id = None
    object_tile = tile_from_record(record, "objectTile")
    if object_tile is None and object_value:
        try:
            object_tile = {
                "x": int(object_value["x"]),
                "y": int(object_value["y"]),
                "height": int(object_value.get("height", 0)),
            }
        except (KeyError, TypeError, ValueError):
            object_tile = None
    name = str(record.get("objectName") or object_value.get("name") or "")
    return {
        "objectId": object_id,
        "name": name,
        "option": str(record.get("option") or ""),
        "phase": str(record.get("objectInteractionPhase") or ""),
        "tile": object_tile,
    }


def object_info_key(info):
    object_id = "unknown" if info.get("objectId") is None else str(info.get("objectId"))
    name = info.get("name") or ""
    tile = info.get("tile")
    suffix = "@" + tile_key(tile) if tile is not None else ""
    return "{}:{}{}".format(object_id, name, suffix)


def add_trace_edge(edges, previous_key, current_key, record, trace_id, inferred_reverse=False):
    edge_key = (previous_key, current_key)
    edge = edges.get(edge_key)
    if edge is None:
        edge = new_graph_edge(previous_key, current_key)
        edges[edge_key] = edge
    edge["attempts"] += 1
    if is_trace_failure(record):
        edge["failures"] += 1
    else:
        edge["successes"] += 1
    edge["ticks"] += 1
    if record.get("runEnabled") is True:
        edge["runTicks"] += 1
    else:
        edge["walkTicks"] += 1
    edge["energySpent"] += max(0, int(record.get("runEnergySpent") or 0))
    edge["hitpointsLost"] += max(0, int(record.get("hitpointsLost") or 0))
    if record.get("isInCombat") is True:
        edge["combatTicks"] += 1
    tool = str(record.get("tool") or "")
    if tool:
        edge["tools"][tool] = edge["tools"].get(tool, 0) + 1
    event = str(record.get("event") or record.get("batchStatus") or "tick")
    if inferred_reverse:
        event = "inferred-reverse-" + event
        edge["inferredReverse"] = edge.get("inferredReverse", 0) + 1
    edge["events"][event] = edge["events"].get(event, 0) + 1
    if trace_id:
        edge["traceIds"][trace_id] = edge["traceIds"].get(trace_id, 0) + 1
    if not inferred_reverse:
        object_info = object_info_from_record(record)
        if object_info is not None:
            edge["objectInteractions"] += 1
            object_key = object_info_key(object_info)
            edge["objects"][object_key] = edge["objects"].get(object_key, 0) + 1
            option = object_info.get("option")
            if option:
                edge["objectOptions"][option] = edge["objectOptions"].get(option, 0) + 1
            phase = object_info.get("phase")
            if phase:
                edge["objectPhases"][phase] = edge["objectPhases"].get(phase, 0) + 1
    edge["lastSeen"] = str(record.get("timestamp") or record.get("_sourcePath") or "")


def reversible_trace_record(record, previous, tile):
    if object_info_from_record(record) is not None:
        return False
    if is_trace_failure(record):
        return False
    if record.get("isDead") is True or record.get("isInCombat") is True:
        return False
    if int(record.get("hitpointsLost") or 0) > 0:
        return False
    if previous.get("height", 0) != tile.get("height", 0):
        return False
    return distance(previous, tile) <= 2


def build_trace_graph(extra_paths=None, profile=None, include_unscoped=False,
                      include_agent_batch=None, include_legacy_recorder=None):
    nodes = {}
    edges = {}
    blockers = {}
    record_count = 0
    trace_ids = set()
    for record in iter_movement_traces(
            extra_paths, profile, include_unscoped, include_agent_batch, include_legacy_recorder):
        record_count += 1
        trace_id = str(record.get("traceId") or "")
        if trace_id:
            trace_ids.add(trace_id)
        tile = tile_from_record(record, "tile")
        previous = tile_from_record(record, "previousTile")
        current_key = tile_key(tile)
        nodes[current_key] = tile

        target = target_tile_from_record(record)
        if is_trace_failure(record) and target is not None:
            blocker_key = (current_key, tile_key(target))
            blockers[blocker_key] = blockers.get(blocker_key, 0) + 1

        if previous is None:
            continue
        previous_key = tile_key(previous)
        nodes[previous_key] = previous
        if previous_key == current_key:
            continue
        add_trace_edge(edges, previous_key, current_key, record, trace_id)
        if reversible_trace_record(record, previous, tile):
            add_trace_edge(edges, current_key, previous_key, record, trace_id, inferred_reverse=True)
    adjacency = {}
    for (from_key, to_key), edge in edges.items():
        adjacency.setdefault(from_key, []).append((to_key, edge))
    return {
        "nodes": nodes,
        "edges": edges,
        "adjacency": adjacency,
        "blockers": blockers,
        "recordCount": record_count,
        "traceCount": len(trace_ids),
    }


def edge_cost(edge):
    successes = max(1, edge.get("successes", 0))
    failure_penalty = edge.get("failures", 0) * 25
    combat_penalty = edge.get("combatTicks", 0) * 8
    hp_penalty = edge.get("hitpointsLost", 0) * 40
    energy_penalty = edge.get("energySpent", 0) * 0.2
    return (float(edge.get("ticks", 0)) / successes) + failure_penalty + combat_penalty + hp_penalty + energy_penalty


def graph_target_keys(graph, target_place):
    radius = target_place.get("arrivalRadius", 1)
    target_tile = target_place["tile"]
    return set(key for key, tile in graph["nodes"].items() if distance(tile, target_tile) <= radius)


def graph_path(graph, current, target_place, max_snap_distance=0):
    if not graph["edges"]:
        return None
    current_key = tile_key(current)
    start_keys = []
    if current_key in graph["nodes"]:
        start_keys.append((0.0, current_key))
    elif max_snap_distance > 0:
        for key, tile in graph["nodes"].items():
            dist = distance(current, tile)
            if dist <= max_snap_distance:
                start_keys.append((float(dist) + 5.0, key))
        start_keys.sort(key=lambda item: item[0])
    target_keys = graph_target_keys(graph, target_place)
    if not start_keys or not target_keys:
        return None

    queue = []
    best = {}
    previous = {}
    for cost, key in start_keys:
        best[key] = cost
        heapq.heappush(queue, (cost, key))
    found = None
    while queue:
        cost, key = heapq.heappop(queue)
        if cost != best.get(key):
            continue
        if key in target_keys:
            found = key
            break
        for to_key, edge in graph["adjacency"].get(key, []):
            if edge.get("successes", 0) <= 0:
                continue
            next_cost = cost + edge_cost(edge)
            if next_cost < best.get(to_key, math.inf):
                best[to_key] = next_cost
                previous[to_key] = (key, edge)
                heapq.heappush(queue, (next_cost, to_key))
    if found is None:
        return None

    path = [found]
    edges = []
    while path[-1] in previous:
        prev_key, edge = previous[path[-1]]
        edges.append(edge)
        path.append(prev_key)
    path.reverse()
    edges.reverse()
    return {"path": path, "edges": edges, "cost": best[found]}


def graph_next_step_decision(db, current, target_place, combat_level=None, food=None, coins=None,
                             run_energy=None, run_enabled=None, hazard_radius=20, max_snap_distance=0,
                             trace_profile=None, include_unscoped_traces=False):
    graph = build_trace_graph(profile=trace_profile, include_unscoped=include_unscoped_traces)
    path = graph_path(graph, current, target_place, max_snap_distance=max_snap_distance)
    if not path or len(path["path"]) < 2:
        return None
    next_key = path["path"][1]
    next_tile = tile_from_key(next_key)
    first_edge = path["edges"][0] if path["edges"] else None
    avg_energy = 0.0
    avg_ticks = 0.0
    if first_edge:
        successes = max(1, first_edge.get("successes", 0))
        avg_energy = float(first_edge.get("energySpent", 0)) / successes
        avg_ticks = float(first_edge.get("ticks", 0)) / successes

    warnings = []
    if run_energy is not None and avg_energy > run_energy:
        warnings.append("learned edge wants run energy {:.1f} > available {}".format(avg_energy, run_energy))
    nearby_hazards = hazards_near(db, current, hazard_radius)
    for _, hazard in nearby_hazards:
        for warning in risk_warnings(hazard, combat_level, food, coins, run_energy, run_enabled):
            warnings.append("{}: {}".format(hazard["id"], warning))

    run_note = "Learned edge avgTicks={:.1f}, avgRunEnergySpent={:.1f}.".format(avg_ticks, avg_energy)
    route = {
        "id": "learned_tile_graph",
        "status": "learned-graph",
        "confidence": min(0.99, 0.55 + 0.04 * len(path["edges"])),
        "runPolicy": {
            "preferRun": avg_energy > 0,
            "minEnergy": int(math.ceil(avg_energy)),
            "notes": run_note,
        },
        "requirements": {},
        "safety": {"risk": "learned", "notes": "Derived from movement traces."},
    }
    next_step = {
        "type": "walk",
        "instruction": "Follow learned graph edge {} -> {} toward {}.".format(
            path["path"][0], next_key, target_place["id"]),
    }
    return {
        "arrived": False,
        "targetPlace": target_place,
        "route": route,
        "nextStep": next_step,
        "nextTile": next_tile,
        "hazards": nearby_hazards,
        "warnings": warnings,
        "graphPath": path,
    }


def validate(db):
    errors = []
    place_ids = set()
    route_ids = set()
    hazard_ids = set()

    for place in db["places"]:
        if place["id"] in place_ids:
            errors.append("duplicate place id: {}".format(place["id"]))
        place_ids.add(place["id"])
        for key in ("x", "y", "height"):
            if key not in place.get("tile", {}):
                errors.append("place {} missing tile.{}".format(place["id"], key))

    for route in db["routes"]:
        if route["id"] in route_ids:
            errors.append("duplicate route id: {}".format(route["id"]))
        route_ids.add(route["id"])
        if route.get("from") not in place_ids:
            errors.append("route {} has unknown from place {}".format(route["id"], route.get("from")))
        if route.get("to") not in place_ids:
            errors.append("route {} has unknown to place {}".format(route["id"], route.get("to")))
        orders = [step.get("order") for step in route.get("steps", [])]
        if orders != sorted(orders):
            errors.append("route {} steps are not sorted by order".format(route["id"]))
        for step in route.get("steps", []):
            target = step.get("to") or step.get("near")
            if not target:
                errors.append("route {} step {} missing to/near tile".format(route["id"], step.get("order")))
                continue
            for key in ("x", "y", "height"):
                if key not in target:
                    errors.append("route {} step {} missing tile.{}".format(route["id"], step.get("order"), key))

    for hazard in db["hazards"]:
        if hazard["id"] in hazard_ids:
            errors.append("duplicate hazard id: {}".format(hazard["id"]))
        hazard_ids.add(hazard["id"])
        for key in ("x", "y", "height"):
            if key not in hazard.get("center", {}):
                errors.append("hazard {} missing center.{}".format(hazard["id"], key))

    return errors


def validate_route_tests(db):
    errors = []
    test_data = load_optional_json("route_tests.json", {"tests": []})
    route_ids = set(route["id"] for route in db["routes"])
    names = set()
    for index, test in enumerate(test_data.get("tests", []), 1):
        name = test.get("name", "test_{}".format(index))
        if name in names:
            errors.append("duplicate route test name: {}".format(name))
        names.add(name)
        if "from" not in test:
            errors.append("route test {} missing from".format(name))
        else:
            try:
                tile_from_arg(test["from"])
            except Exception as exc:
                errors.append("route test {} has invalid from tile: {}".format(name, exc))
        if "to" not in test or not find_place(db, test.get("to", "")):
            errors.append("route test {} has unknown target {}".format(name, test.get("to")))
        if test.get("expectRoute") and test["expectRoute"] not in route_ids:
            errors.append("route test {} expects unknown route {}".format(name, test["expectRoute"]))
        if test.get("expectNext"):
            try:
                tile_from_arg(test["expectNext"])
            except Exception as exc:
                errors.append("route test {} has invalid expected next tile: {}".format(name, exc))
    return errors


def cmd_validate(args):
    db = load_db()
    errors = validate(db) + validate_route_tests(db)
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    print("navigation database ok: {} places, {} routes, {} hazards".format(
        len(db["places"]), len(db["routes"]), len(db["hazards"])))
    return 0


def cmd_places(args):
    db = load_db()
    query = norm(args.query) if args.query else None
    for place in db["places"]:
        haystack = norm(" ".join([place["id"], place["name"]] + place.get("aliases", []) + place.get("tags", [])))
        if query and query not in haystack:
            continue
        safety = place.get("safety", {})
        print("{} | {} | {} | risk={} | {}".format(
            place["id"], place["name"], tile_str(place["tile"]), safety.get("risk", "unknown"),
            ", ".join(place.get("tags", []))))
    return 0


def cmd_place(args):
    db = load_db()
    place = find_place(db, args.place)
    if not place:
        print("place not found: {}".format(args.place), file=sys.stderr)
        return 1
    print(json.dumps(place, indent=2, sort_keys=True))
    return 0


def cmd_routes(args):
    db = load_db()
    to_place = find_place(db, args.to) if args.to else None
    from_place = find_place(db, args.from_place) if args.from_place else None
    for route in db["routes"]:
        if to_place and route.get("to") != to_place["id"]:
            continue
        if from_place and route.get("from") != from_place["id"]:
            continue
        if args.status and route.get("status") != args.status:
            continue
        req = route.get("requirements", {})
        if args.combat_level is not None and req.get("minCombatLevel", 1) > args.combat_level:
            continue
        print("{} | {} -> {} | {} | confidence={}".format(
            route["id"], route.get("from"), route.get("to"), route.get("status"), route.get("confidence")))
    return 0


def cmd_route(args):
    db = load_db()
    route = next((item for item in db["routes"] if item["id"] == args.route), None)
    if not route:
        print("route not found: {}".format(args.route), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(route, indent=2, sort_keys=True))
        return 0
    print("{} ({})".format(route["name"], route["status"]))
    print(route.get("summary", ""))
    print("requirements:", json.dumps(route.get("requirements", {}), sort_keys=True))
    print("run:", route.get("runPolicy", {}).get("notes", "no run policy"))
    for step in route.get("steps", []):
        target = step.get("to") or step.get("near")
        target_text = " @ {}".format(tile_str(target)) if target else ""
        print("{:>2}. {}{} - {}".format(step["order"], step["type"], target_text, step["instruction"]))
        if step.get("blocker"):
            print("    blocker:", step["blocker"])
    return 0


def reversed_route_walk_tiles(db, route):
    forward = route_walk_tiles(route)
    if not forward:
        return []
    from_place = find_place(db, route.get("from", ""))
    if not from_place:
        return []
    reversed_tiles = []
    for index, (_step, tile) in enumerate(reversed(forward[:-1]), 1):
        reversed_tiles.append(({
            "order": index,
            "type": "walk",
            "to": tile,
            "instruction": "Reverse bidirectional route via {}.".format(tile_str(tile)),
        }, tile))
    final_step = {
        "order": len(reversed_tiles) + 1,
        "type": "walk",
        "to": from_place["tile"],
        "instruction": "Reverse bidirectional route to {}.".format(from_place.get("name", route.get("from"))),
    }
    reversed_tiles.append((final_step, from_place["tile"]))
    return reversed_tiles


def route_direction_candidates(db, route, target_place):
    if route.get("to") == target_place["id"]:
        return [(route, route_walk_tiles(route))]
    if route.get("bidirectional") is True and route.get("from") == target_place["id"]:
        reverse = dict(route)
        reverse["id"] = route.get("id", "") + "__reverse"
        reverse["name"] = route.get("name", "") + " (reverse)"
        reverse["from"], reverse["to"] = route.get("to"), route.get("from")
        reverse["_reversedFromRoute"] = route.get("id")
        return [(reverse, reversed_route_walk_tiles(db, route))]
    return []


def choose_route(db, current, target_place):
    candidates = []
    for route in db["routes"]:
        for candidate_route, tiles in route_direction_candidates(db, route, target_place):
            if not tiles:
                continue
            start_place = find_place(db, candidate_route.get("from", ""))
            start_dist = distance(current, start_place["tile"]) if start_place else 999
            min_dist = min(distance(current, tile) for _, tile in tiles)
            if start_dist <= 4:
                anchor_dist = start_dist
            elif min_dist <= 4:
                anchor_dist = 6 + min_dist
            else:
                anchor_dist = min(start_dist, min_dist + 12)
            status_penalty = 0
            if candidate_route.get("status") == "derived-from-existing-landmark":
                status_penalty = 15
            elif candidate_route.get("status") == "learned-graph":
                status_penalty = 4
            elif candidate_route.get("status") == "learned-partial":
                status_penalty = 18
            elif candidate_route.get("status") == "needs-verification":
                status_penalty = 25
            elif candidate_route.get("status") in ("blocked", "failed"):
                status_penalty = 100
            transition_penalty = 12 * len(route_transition_warnings(route))
            score = anchor_dist + status_penalty - (2 * float(candidate_route.get("confidence", 0)))
            if candidate_route.get("_reversedFromRoute"):
                score += 0.5
            score += transition_penalty
            candidates.append((score, anchor_dist, candidate_route, tiles))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item[0], item[2]["id"]))[0]


def next_step_decision(db, current, target_query, combat_level=None, food=None, coins=None,
                       run_energy=None, run_enabled=None, hazard_radius=20, use_graph=True,
                       graph_snap_distance=0, trace_profile=None, include_unscoped_traces=False):
    target_place = place_or_tile_target(db, target_query)
    if not target_place:
        return {"error": "target place or tile not found: {}".format(target_query)}
    if distance(current, target_place["tile"]) <= target_place.get("arrivalRadius", 1):
        return {"arrived": True, "targetPlace": target_place}

    if use_graph:
        graph_decision = graph_next_step_decision(
            db, current, target_place, combat_level, food, coins, run_energy, run_enabled,
            hazard_radius, graph_snap_distance, trace_profile, include_unscoped_traces)
        if graph_decision:
            return graph_decision

    choice = choose_route(db, current, target_place)
    if not choice:
        return {"error": "no route to {}".format(target_place["id"]), "targetPlace": target_place}
    _, _, route, tiles = choice
    closest_index = min(range(len(tiles)), key=lambda i: distance(current, tiles[i][1]))
    if distance(current, tiles[closest_index][1]) <= 4 and closest_index + 1 < len(tiles):
        next_step, next_tile = tiles[closest_index + 1]
    else:
        next_step, next_tile = tiles[closest_index]

    warnings = route_requirement_warnings(route, combat_level, food, coins, run_energy, run_enabled)
    warnings.extend(route_transition_warnings(route))
    nearby_hazards = hazards_near(db, current, hazard_radius)
    for _, hazard in nearby_hazards:
        for warning in risk_warnings(hazard, combat_level, food, coins, run_energy, run_enabled):
            warnings.append("{}: {}".format(hazard["id"], warning))

    return {
        "arrived": False,
        "targetPlace": target_place,
        "route": route,
        "nextStep": next_step,
        "nextTile": next_tile,
        "hazards": nearby_hazards,
        "warnings": warnings,
    }


def cmd_next_step(args):
    db = load_db()
    current = args.from_tile
    decision = next_step_decision(
        db, current, args.to, args.combat_level, args.food, args.coins,
        args.run_energy, args.run_enabled, args.hazard_radius, not args.no_graph,
        args.graph_snap_distance, args.trace_profile, args.include_unscoped_traces)
    if decision.get("error"):
        print(decision["error"], file=sys.stderr)
        return 1
    if decision.get("arrived"):
        target_place = decision["targetPlace"]
        print("arrived at {} ({})".format(target_place["name"], tile_str(target_place["tile"])))
        return 0

    route = decision["route"]
    next_step = decision["nextStep"]
    next_tile = decision["nextTile"]
    nearby_hazards = decision["hazards"]
    warnings = decision["warnings"]

    print("route:", route["id"], "status={}".format(route.get("status")))
    print("next:", next_step["type"], tile_str(next_tile))
    print("instruction:", next_step["instruction"])
    if decision.get("graphPath"):
        graph_path_data = decision["graphPath"]
        print("graphPath:", " -> ".join(graph_path_data["path"]))
        print("graphCost:", "{:.2f}".format(graph_path_data["cost"]))
    run_policy = route.get("runPolicy", {})
    if run_policy:
        print("runPolicy:", run_policy.get("notes", "preferRun={}".format(run_policy.get("preferRun"))))
        if run_policy.get("requiresRun"):
            print("runRequired: true")
    if nearby_hazards:
        print("hazards:")
        for dist, hazard in nearby_hazards:
            print("  {} dist={} risk={} - {}".format(hazard["id"], dist, hazard.get("risk"), hazard.get("notes", "")))
    if warnings:
        print("warnings:")
        for warning in warnings:
            print("  " + warning)
    return 0


def cmd_hazards(args):
    db = load_db()
    found = hazards_near(db, args.near, args.radius)
    for dist, hazard in found:
        warnings = risk_warnings(
            hazard, args.combat_level, args.food, args.coins, args.run_energy, args.run_enabled)
        warning_text = " | warnings: " + "; ".join(warnings) if warnings else ""
        print("{} | dist={} | risk={}{}".format(hazard["id"], dist, hazard.get("risk"), warning_text))
        print("  " + hazard.get("notes", ""))
    if not found:
        print("no hazards within radius {}".format(args.radius))
    return 0


def cmd_route_risk(args):
    db = load_db()
    route = next((item for item in db["routes"] if item["id"] == args.route), None)
    if not route:
        print("route not found: {}".format(args.route), file=sys.stderr)
        return 1

    print("{} | {} -> {} | status={} | risk={}".format(
        route["id"], route.get("from"), route.get("to"), route.get("status"),
        route.get("safety", {}).get("risk", "unknown")))
    route_warnings = route_requirement_warnings(
        route, args.combat_level, args.food, args.coins, args.run_energy, args.run_enabled)
    if route_warnings:
        print("requirements:")
        for warning in route_warnings:
            print("  " + warning)

    hits = route_hazards(db, route, args.buffer)
    if not hits:
        print("no known hazards intersect route with buffer {}".format(args.buffer))
        return 0

    print("hazards:")
    for dist, hazard, step, tile in hits:
        warnings = risk_warnings(
            hazard, args.combat_level, args.food, args.coins, args.run_energy, args.run_enabled)
        print("  {} dist={} near step {} @ {} risk={}".format(
            hazard["id"], dist, step.get("order"), tile_str(tile), hazard.get("risk")))
        if warnings:
            for warning in warnings:
                print("    warning: " + warning)
        notes = hazard.get("notes")
        if notes:
            print("    " + notes)
    return 0


def cmd_run_areas(args):
    db = load_db()
    query = norm(args.query) if args.query else None
    for route in db["routes"]:
        run_policy = route.get("runPolicy", {})
        haystack = norm(" ".join([route["id"], route.get("name", ""), route.get("summary", "")] + route.get("tags", [])))
        if query and query not in haystack:
            continue
        prefer = run_policy.get("preferRun")
        min_energy = run_policy.get("minEnergy")
        print("{} | preferRun={} | minEnergy={} | status={}".format(
            route["id"], prefer, min_energy, route.get("status")))
        notes = run_policy.get("notes")
        if notes:
            print("  " + notes)
    return 0


def cmd_coverage(args):
    db = load_db()
    by_status = {}
    for route in db["routes"]:
        status = route.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1

    print("places:", len(db["places"]))
    print("routes:", len(db["routes"]))
    print("hazards:", len(db["hazards"]))
    print("routes by status:")
    for status in sorted(by_status):
        print("  {}: {}".format(status, by_status[status]))

    blockers = []
    for route in db["routes"]:
        if route.get("knownBlockers"):
            blockers.append(route)
        elif any(step.get("blocker") for step in route.get("steps", [])):
            blockers.append(route)
    if blockers:
        print("routes with blockers or verification steps:")
        for route in blockers:
            print("  {} | {}".format(route["id"], route.get("summary", "")))
    else:
        print("routes with blockers or verification steps: none")
    return 0


def cmd_self_test(args):
    db = load_db()
    tests = load_optional_json("route_tests.json", {"tests": []}).get("tests", [])
    if not tests:
        print("no route tests found")
        return 0

    failures = []
    for test in tests:
        name = test.get("name", "unnamed")
        try:
            current = tile_from_arg(test["from"])
        except Exception as exc:
            failures.append("{}: invalid from tile: {}".format(name, exc))
            print("FAIL", name)
            continue

        decision = next_step_decision(
            db,
            current,
            test["to"],
            test.get("combatLevel"),
            test.get("food"),
            test.get("coins"),
            test.get("runEnergy"),
            test.get("runEnabled"),
            test.get("hazardRadius", 20),
            test.get("useGraph", False),
            test.get("graphSnapDistance", 0),
        )
        if decision.get("error"):
            failures.append("{}: {}".format(name, decision["error"]))
            print("FAIL", name)
            continue

        messages = []
        if "expectArrived" in test and bool(decision.get("arrived")) != bool(test["expectArrived"]):
            messages.append("arrived expected {} got {}".format(test["expectArrived"], decision.get("arrived")))
        if not decision.get("arrived"):
            route = decision["route"]
            next_step = decision["nextStep"]
            next_tile = decision["nextTile"]
            if test.get("expectRoute") and route["id"] != test["expectRoute"]:
                messages.append("route expected {} got {}".format(test["expectRoute"], route["id"]))
            if test.get("expectType") and next_step["type"] != test["expectType"]:
                messages.append("type expected {} got {}".format(test["expectType"], next_step["type"]))
            if test.get("expectNext") and tile_str(next_tile) != test["expectNext"]:
                messages.append("next expected {} got {}".format(test["expectNext"], tile_str(next_tile)))
            for expected in test.get("expectWarningContains", []):
                if not any(expected in warning for warning in decision.get("warnings", [])):
                    messages.append("missing warning containing {!r}".format(expected))

        if messages:
            failures.append("{}: {}".format(name, "; ".join(messages)))
            print("FAIL", name)
        elif args.verbose:
            route_id = decision["route"]["id"] if not decision.get("arrived") else "arrived"
            print("PASS {} | {}".format(name, route_id))
        else:
            print("PASS", name)

    if failures:
        print("failures:")
        for failure in failures:
            print("  " + failure)
        return 1
    print("route self-tests ok: {} tests".format(len(tests)))
    return 0


def copy_screenshot(path, observation_id):
    if not path:
        return None
    source = Path(path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(str(source))
    day = dt.datetime.utcnow().strftime("%Y-%m-%d")
    dest_dir = SCREENSHOTS / day
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "{}{}".format(observation_id, source.suffix.lower() or ".png")
    shutil.copy2(str(source), str(dest))
    return str(dest.relative_to(ROOT))


def load_state_json(value):
    if not value:
        return None
    if value.strip().startswith(("{", "[")):
        return json.loads(value)
    with Path(value).expanduser().open("r", encoding="utf-8") as handle:
        return json.load(handle)


def cmd_record_observation(args):
    db = load_db()
    place = find_place(db, args.place) if args.place else None
    if args.place and not place:
        print("place not found: {}".format(args.place), file=sys.stderr)
        return 1
    if args.route and not any(route["id"] == args.route for route in db["routes"]):
        print("route not found: {}".format(args.route), file=sys.stderr)
        return 1

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    observation_id = "obs_{}_{}".format(now.strftime("%Y_%m_%dT%H_%M_%SZ"), uuid.uuid4().hex[:8])
    screenshot = None
    try:
        screenshot = copy_screenshot(args.screenshot, observation_id)
    except Exception as exc:
        print("could not copy screenshot: {}".format(exc), file=sys.stderr)
        return 1

    state = load_state_json(args.state_json)

    record = {
        "schemaVersion": 1,
        "id": observation_id,
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "source": args.source,
        "player": args.player,
        "place": place["id"] if place else None,
        "route": args.route,
        "tile": {"x": args.x, "y": args.y, "height": args.height},
        "screenshot": screenshot,
        "state": state,
        "notes": args.note or ""
    }
    with (DATA / "observations.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    print(observation_id)
    return 0


def cmd_graph_summary(args):
    graph = build_trace_graph(args.trace_file, args.trace_profile, args.include_unscoped_traces)
    print("trace records:", graph["recordCount"])
    print("trace sessions:", graph["traceCount"])
    print("graph nodes:", len(graph["nodes"]))
    print("graph edges:", len(graph["edges"]))
    print("blocked target attempts:", len(graph["blockers"]))
    edges = sorted(graph["edges"].values(),
                   key=lambda edge: (-edge.get("successes", 0), edge.get("failures", 0), edge["from"], edge["to"]))
    for edge in edges[:args.limit]:
        successes = edge.get("successes", 0)
        avg_energy = float(edge.get("energySpent", 0)) / max(1, successes)
        object_note = ""
        if edge.get("objectInteractions", 0) > 0:
            object_note = " objects={}".format(edge.get("objectInteractions", 0))
        print("{} -> {} | success={} fail={} ticks={} runTicks={} avgEnergy={:.1f} hpLost={}{}".format(
            edge["from"], edge["to"], successes, edge.get("failures", 0), edge.get("ticks", 0),
            edge.get("runTicks", 0), avg_energy, edge.get("hitpointsLost", 0), object_note))
    return 0


def cmd_graph_route(args):
    db = load_db()
    target_place = place_or_tile_target(db, args.to)
    if not target_place:
        print("target place or tile not found: {}".format(args.to), file=sys.stderr)
        return 1
    graph = build_trace_graph(args.trace_file, args.trace_profile, args.include_unscoped_traces)
    path = graph_path(graph, args.from_tile, target_place, args.graph_snap_distance)
    if not path:
        print("no learned graph route to {}".format(target_place["id"]), file=sys.stderr)
        return 1
    if args.json:
        data = {
            "targetPlace": target_place["id"],
            "cost": path["cost"],
            "path": path["path"],
            "edges": path["edges"],
        }
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0
    print("graph route to {} cost={:.2f}".format(target_place["id"], path["cost"]))
    for index, key in enumerate(path["path"]):
        print("{:>3}. {}".format(index + 1, key))
    return 0


def trace_target_place(db, record):
    target = tile_from_record(record, "target")
    args = record.get("arguments") if isinstance(record.get("arguments"), dict) else {}
    landmark = record.get("landmark") or args.get("name")
    if landmark:
        place = find_place(db, landmark)
        if place:
            return place
    if target:
        matches = []
        for place in db["places"]:
            if distance(target, place["tile"]) <= place.get("arrivalRadius", 1):
                matches.append(place)
        if len(matches) == 1:
            return matches[0]
    return None


def cmd_trace_tests(args):
    db = load_db()
    grouped = {}
    for record in iter_movement_traces(args.trace_file, args.trace_profile, args.include_unscoped_traces):
        trace_id = str(record.get("traceId") or "")
        if not trace_id:
            continue
        grouped.setdefault(trace_id, []).append(record)
    generated = []
    for trace_id, records in sorted(grouped.items()):
        records.sort(key=lambda item: item.get("tickIndex", 0))
        terminal = next((item for item in reversed(records)
                         if str(item.get("event") or item.get("batchStatus") or "") == "arrived"), None)
        if terminal is None:
            continue
        start = tile_from_record(records[0], "tile")
        target_place = trace_target_place(db, terminal)
        if not start or not target_place:
            continue
        generated.append({
            "name": "trace_{}_to_{}".format(trace_id[:8], target_place["id"]),
            "from": tile_str(start),
            "to": target_place["id"],
            "useGraph": True,
            "expectType": "walk",
        })
    output = {"schemaVersion": 1, "tests": generated[:args.limit]}
    if args.output:
        Path(args.output).expanduser().write_text(json.dumps(output, indent=2, sort_keys=True) + "\n",
                                                  encoding="utf-8")
        print("wrote {} graph route tests to {}".format(len(output["tests"]), args.output))
    else:
        print(json.dumps(output, indent=2, sort_keys=True))
    return 0


def add_trace_filter_args(parser):
    parser.add_argument("--trace-file", action="append")
    parser.add_argument("--trace-profile", default=default_trace_profile(),
                        help="Only use traces recorded by this player/profile. Defaults to RS_TRACE_PROFILE or RS_PROFILE.")
    parser.add_argument("--include-unscoped-traces", action="store_true",
                        help="When filtering by profile, also include legacy traces with no player name.")


def build_parser():
    parser = argparse.ArgumentParser(description="Query and update the 2006Scape agent navigation database.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate")
    validate_parser.set_defaults(func=cmd_validate)

    places_parser = sub.add_parser("places")
    places_parser.add_argument("--query")
    places_parser.set_defaults(func=cmd_places)

    place_parser = sub.add_parser("place")
    place_parser.add_argument("place")
    place_parser.set_defaults(func=cmd_place)

    routes_parser = sub.add_parser("routes")
    routes_parser.add_argument("--from", dest="from_place")
    routes_parser.add_argument("--to")
    routes_parser.add_argument("--status")
    routes_parser.add_argument("--combat-level", type=int)
    routes_parser.set_defaults(func=cmd_routes)

    route_parser = sub.add_parser("route")
    route_parser.add_argument("route")
    route_parser.add_argument("--json", action="store_true")
    route_parser.set_defaults(func=cmd_route)

    next_parser = sub.add_parser("next-step")
    next_parser.add_argument("--from", dest="from_tile", required=True, type=tile_from_arg)
    next_parser.add_argument("--to", required=True)
    next_parser.add_argument("--combat-level", type=int)
    next_parser.add_argument("--food", type=int)
    next_parser.add_argument("--coins", type=int)
    next_parser.add_argument("--run-energy", type=int)
    next_parser.add_argument("--run-enabled", type=bool_from_arg)
    next_parser.add_argument("--hazard-radius", type=int, default=20)
    next_parser.add_argument("--no-graph", action="store_true")
    next_parser.add_argument("--graph-snap-distance", type=int, default=0)
    add_trace_filter_args(next_parser)
    next_parser.set_defaults(func=cmd_next_step)

    hazards_parser = sub.add_parser("hazards")
    hazards_parser.add_argument("--near", required=True, type=tile_from_arg)
    hazards_parser.add_argument("--radius", type=int, default=20)
    hazards_parser.add_argument("--combat-level", type=int)
    hazards_parser.add_argument("--food", type=int)
    hazards_parser.add_argument("--coins", type=int)
    hazards_parser.add_argument("--run-energy", type=int)
    hazards_parser.add_argument("--run-enabled", type=bool_from_arg)
    hazards_parser.set_defaults(func=cmd_hazards)

    route_risk_parser = sub.add_parser("route-risk")
    route_risk_parser.add_argument("route")
    route_risk_parser.add_argument("--combat-level", type=int)
    route_risk_parser.add_argument("--food", type=int)
    route_risk_parser.add_argument("--coins", type=int)
    route_risk_parser.add_argument("--run-energy", type=int)
    route_risk_parser.add_argument("--run-enabled", type=bool_from_arg)
    route_risk_parser.add_argument("--buffer", type=int, default=0)
    route_risk_parser.set_defaults(func=cmd_route_risk)

    run_parser = sub.add_parser("run-areas")
    run_parser.add_argument("--query")
    run_parser.set_defaults(func=cmd_run_areas)

    coverage_parser = sub.add_parser("coverage")
    coverage_parser.set_defaults(func=cmd_coverage)

    self_test_parser = sub.add_parser("self-test")
    self_test_parser.add_argument("--verbose", action="store_true")
    self_test_parser.set_defaults(func=cmd_self_test)

    record_parser = sub.add_parser("record-observation")
    record_parser.add_argument("--player", required=True)
    record_parser.add_argument("--x", required=True, type=int)
    record_parser.add_argument("--y", required=True, type=int)
    record_parser.add_argument("--height", required=True, type=int)
    record_parser.add_argument("--place")
    record_parser.add_argument("--route")
    record_parser.add_argument("--screenshot")
    record_parser.add_argument("--state-json")
    record_parser.add_argument("--source", default="manual")
    record_parser.add_argument("--note")
    record_parser.set_defaults(func=cmd_record_observation)

    graph_summary_parser = sub.add_parser("graph-summary")
    add_trace_filter_args(graph_summary_parser)
    graph_summary_parser.add_argument("--limit", type=int, default=20)
    graph_summary_parser.set_defaults(func=cmd_graph_summary)

    graph_route_parser = sub.add_parser("graph-route")
    graph_route_parser.add_argument("--from", dest="from_tile", required=True, type=tile_from_arg)
    graph_route_parser.add_argument("--to", required=True)
    add_trace_filter_args(graph_route_parser)
    graph_route_parser.add_argument("--graph-snap-distance", type=int, default=0)
    graph_route_parser.add_argument("--json", action="store_true")
    graph_route_parser.set_defaults(func=cmd_graph_route)

    trace_tests_parser = sub.add_parser("trace-tests")
    add_trace_filter_args(trace_tests_parser)
    trace_tests_parser.add_argument("--output")
    trace_tests_parser.add_argument("--limit", type=int, default=50)
    trace_tests_parser.set_defaults(func=cmd_trace_tests)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
