#!/usr/bin/env python3
"""Adaptive bridge-backed mining runner.

This runner keeps mining out of the AI token loop. It discovers nearby mine
clusters from the cache map, scores them against verified banks, routes to the
best site through route_runner.py, mines the highest-value ready ore through the
bridge, and banks ores when the inventory fills.
"""

import argparse
import datetime as dt
import json
import math
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
RS_TOOL = SCRIPT_DIR / "rs-tool.sh"
ROUTE_RUNNER = SCRIPT_DIR / "route_runner.py"
PLACES_PATH = ROOT / "data" / "places.json"
MINING_DIR = ROOT / "data" / "mining"
RUNS_DIR = MINING_DIR / "runs"
RUN_PROFILE = ""

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import cache_world_map  # noqa: E402


ORE_DEFS = {
    "clay": {
        "itemId": 434,
        "level": 1,
        "xp": 5,
        "respawnTicks": 2,
        "rockIds": {2108, 2109, 11189, 11190, 11191, 9713, 9711, 14905, 14904},
    },
    "copper": {
        "itemId": 436,
        "level": 1,
        "xp": 18,
        "respawnTicks": 4,
        "rockIds": {3042, 2091, 2090, 9708, 9709, 9710, 11960, 14906, 14907},
    },
    "tin": {
        "itemId": 438,
        "level": 1,
        "xp": 18,
        "respawnTicks": 4,
        "rockIds": {2094, 2095, 3043, 9716, 9714, 11958, 11957, 11959, 11933, 11934, 11935, 14903, 14902},
    },
    "iron": {
        "itemId": 440,
        "level": 15,
        "xp": 35,
        "respawnTicks": 9,
        "rockIds": {450, 2093, 2092, 9717, 9718, 9719, 11962, 11956, 11954, 14856, 14857, 14858, 14914, 14913},
    },
    "silver": {
        "itemId": 442,
        "level": 20,
        "xp": 40,
        "respawnTicks": 100,
        "rockIds": {2101, 11186, 11187, 11188, 2100},
    },
    "coal": {
        "itemId": 453,
        "level": 30,
        "xp": 50,
        "respawnTicks": 50,
        "rockIds": {2096, 2097, 11963, 11964, 14850, 14851, 14852, 11930, 11931, 11932},
    },
    "gold": {
        "itemId": 444,
        "level": 40,
        "xp": 65,
        "respawnTicks": 100,
        "rockIds": {2099, 2098, 11183, 11184, 11185, 9720, 9722},
    },
}

PICKAXES = [
    {"itemId": 1275, "level": 41, "tier": 6, "name": "Rune pickaxe"},
    {"itemId": 1271, "level": 31, "tier": 5, "name": "Adamant pickaxe"},
    {"itemId": 1273, "level": 21, "tier": 4, "name": "Mithril pickaxe"},
    {"itemId": 1269, "level": 6, "tier": 3, "name": "Steel pickaxe"},
    {"itemId": 1267, "level": 1, "tier": 2, "name": "Iron pickaxe"},
    {"itemId": 1265, "level": 1, "tier": 1, "name": "Bronze pickaxe"},
]


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def log(message):
    print(message, flush=True)


def normalize_ore(value):
    ore = str(value or "").strip().lower().replace("_", " ")
    if ore.endswith(" ore"):
        ore = ore[:-4]
    if ore not in ORE_DEFS:
        raise ValueError("unknown ore '{}'".format(value))
    return ore


def parse_ores(value):
    ores = [normalize_ore(part) for part in str(value or "").split(",") if part.strip()]
    if not ores:
        raise ValueError("at least one ore is required")
    return list(dict.fromkeys(ores))


def tile(x, y, height=0):
    return {"x": int(x), "y": int(y), "height": int(height)}


def tile_from_player(player):
    return tile(player["x"], player["y"], player.get("height", player.get("h", 0)))


def tile_string(t):
    return "{},{},{}".format(int(t["x"]), int(t["y"]), int(t.get("height", 0)))


def parse_tile(value):
    parts = [part.strip() for part in str(value).split(",")]
    if len(parts) not in (2, 3):
        raise argparse.ArgumentTypeError("expected X,Y or X,Y,H")
    return tile(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) == 3 else 0)


def chebyshev(a, b):
    if int(a.get("height", 0)) != int(b.get("height", 0)):
        return 100000
    return max(abs(int(a["x"]) - int(b["x"])), abs(int(a["y"]) - int(b["y"])))


def manhattan(a, b):
    if int(a.get("height", 0)) != int(b.get("height", 0)):
        return 100000
    return abs(int(a["x"]) - int(b["x"])) + abs(int(a["y"]) - int(b["y"]))


def compact_player(player):
    skills = player.get("skills") or {}
    mining = skills.get("mining") or {}
    readiness = player.get("combatReadiness") or {}
    return {
        "tile": tile_from_player(player),
        "hitpoints": int(player.get("hitpoints", player.get("hp", 0)) or 0),
        "maxHitpoints": int(player.get("maxHitpoints", player.get("maxHp", 0)) or 0),
        "runEnergy": int(player.get("runEnergy", 0) or 0),
        "runEnabled": bool(player.get("runEnabled", False)),
        "isDead": bool(player.get("isDead", False)),
        "isInCombat": bool(player.get("isInCombat", False)),
        "inBankArea": bool(player.get("inBankArea", False)),
        "freeSlots": int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0),
        "miningLevel": int(mining.get("level", 0) or 0),
        "miningXp": int(float(mining.get("xp", 0) or 0)),
        "coins": int(readiness.get("inventoryCoins", 0) or count_inventory_item(player, 995)),
    }


def call_tool(tool_name, arguments=None):
    args_json = json.dumps(arguments or {}, separators=(",", ":"))
    env = os.environ.copy()
    if RUN_PROFILE:
        env["RS_PROFILE"] = RUN_PROFILE
    proc = subprocess.run(
        [str(RS_TOOL), tool_name, args_json],
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError("{} failed: {}".format(tool_name, proc.stderr.strip() or proc.stdout.strip()))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("{} returned invalid JSON: {}".format(tool_name, exc))


def player_from(result):
    player = result.get("player")
    if not isinstance(player, dict):
        raise RuntimeError("bridge response did not include player state")
    return player


def observe():
    return player_from(call_tool("observe_state", {}))


def ensure_run(player, args):
    if args.no_enable_run:
        return player
    if bool(player.get("runEnabled", False)):
        return player
    if int(player.get("runEnergy", 0) or 0) < args.min_run_energy:
        return player
    result = call_tool("set_run", {"enabled": True})
    return player_from(result)


def count_inventory_item(player, item_id):
    total = 0
    for item in player.get("inventory", []) or []:
        if int(item.get("id", -1)) == int(item_id):
            total += int(item.get("amount", 0) or 0)
    return total


def count_bank_item(player, item_id):
    total = 0
    for item in player.get("bank", []) or []:
        if int(item.get("id", -1)) == int(item_id):
            total += int(item.get("amount", 0) or 0)
    return total


def inventory_ore_count(player, ores=None):
    wanted = set(ores or ORE_DEFS.keys())
    total = 0
    for ore in wanted:
        total += count_inventory_item(player, ORE_DEFS[ore]["itemId"])
    return total


def best_usable_pickaxe(player, in_bank=False):
    skills = player.get("skills") or {}
    mining = int((skills.get("mining") or {}).get("level", 1) or 1)
    for pickaxe in PICKAXES:
        if mining < pickaxe["level"]:
            continue
        count = count_bank_item(player, pickaxe["itemId"]) if in_bank else count_inventory_item(player, pickaxe["itemId"])
        if count > 0:
            return pickaxe
    return None


def mining_level(player):
    return int(((player.get("skills") or {}).get("mining") or {}).get("level", 0) or 0)


def mining_xp(player):
    return int(float(((player.get("skills") or {}).get("mining") or {}).get("xp", 0) or 0))


def write_event(handle, event, data):
    if handle is None:
        return
    record = {"event": event, "timestamp": utc_now()}
    record.update(data)
    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def load_places():
    with PLACES_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get("places", [])


def bank_places():
    banks = []
    for place in load_places():
        tags = set(place.get("tags") or [])
        if place.get("kind") != "bank" and "bank" not in tags:
            continue
        t = place.get("tile") or {}
        if "x" not in t or "y" not in t:
            continue
        banks.append(place)
    return banks


def object_ore(object_id):
    for ore, definition in ORE_DEFS.items():
        if int(object_id) in definition["rockIds"]:
            return ore
    return None


def bounds_around(center, radius):
    return {
        "minX": int(center["x"]) - int(radius),
        "maxX": int(center["x"]) + int(radius),
        "minY": int(center["y"]) - int(radius),
        "maxY": int(center["y"]) + int(radius),
    }


def rock_objects(bounds, ores, max_level):
    world_map = cache_world_map.load_cache_world_map(bounds)
    wanted = set(ores)
    rocks = []
    for obj in world_map.get("objects", []):
        ore = object_ore(obj.get("id", -1))
        if ore is None or ore not in wanted:
            continue
        if ORE_DEFS[ore]["level"] > max_level:
            continue
        rocks.append({
            "ore": ore,
            "objectId": int(obj["id"]),
            "tile": tile(obj["x"], obj["y"], obj.get("height", 0)),
            "type": int(obj.get("type", 10)),
        })
    return rocks


def cluster_rocks(rocks, cluster_radius):
    clusters = []
    for rock in sorted(rocks, key=lambda item: (item["tile"]["x"], item["tile"]["y"], item["ore"])):
        best = None
        best_dist = None
        for cluster in clusters:
            distance = min(chebyshev(rock["tile"], other["tile"]) for other in cluster)
            if distance <= cluster_radius and (best_dist is None or distance < best_dist):
                best = cluster
                best_dist = distance
        if best is None:
            clusters.append([rock])
        else:
            best.append(rock)
    return clusters


def approach_tile_for_cluster(cluster, bank_tile):
    candidates = []
    for rock in cluster:
        r = rock["tile"]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                candidate = tile(r["x"] + dx, r["y"] + dy, r.get("height", 0))
                candidates.append((manhattan(candidate, bank_tile), manhattan(candidate, r), candidate))
    if not candidates:
        r = cluster[0]["tile"]
        return tile(r["x"], r["y"], r.get("height", 0))
    candidates.sort(key=lambda item: (item[0], item[1], item[2]["x"], item[2]["y"]))
    return candidates[0][2]


def site_from_cluster(bank, cluster, args, player_tile=None):
    bank_tile = tile(bank["tile"]["x"], bank["tile"]["y"], bank["tile"].get("height", 0))
    site_tile = approach_tile_for_cluster(cluster, bank_tile)
    ore_counts = {}
    for rock in cluster:
        ore_counts[rock["ore"]] = ore_counts.get(rock["ore"], 0) + 1
    max_rock_distance = max(chebyshev(site_tile, rock["tile"]) for rock in cluster)
    bank_distance = chebyshev(site_tile, bank_tile)
    current_distance = chebyshev(site_tile, player_tile) if player_tile else 0
    unlocked_xp = sum(ORE_DEFS[ore]["xp"] * count for ore, count in ore_counts.items())
    density_bonus = min(35.0, len(cluster) * 2.5)
    current_penalty = current_distance * args.current_distance_weight
    score = bank_distance * args.bank_distance_weight + current_penalty - density_bonus - unlocked_xp / 20.0
    return {
        "id": "cache_{}_{}_{}".format(bank["id"], site_tile["x"], site_tile["y"]),
        "source": "cache",
        "bankPlace": bank["id"],
        "bankName": bank.get("name", bank["id"]),
        "bankTile": bank_tile,
        "tile": site_tile,
        "arrivalRadius": max(3, min(8, max_rock_distance + 1)),
        "rockScanDistance": max(args.rock_scan_distance, max_rock_distance + 3),
        "oreCounts": ore_counts,
        "rockCount": len(cluster),
        "bankDistance": bank_distance,
        "currentDistance": current_distance,
        "score": round(score, 3),
        "rocks": sorted(cluster, key=lambda item: (item["ore"], item["tile"]["x"], item["tile"]["y"])),
    }


def discover_sites(ores, args, player_tile=None, max_level=99):
    sites = []
    banks = bank_places()
    if args.bank:
        wanted_bank = args.bank.lower()
        banks = [
            bank for bank in banks
            if bank.get("id", "").lower() == wanted_bank
            or bank.get("name", "").lower() == wanted_bank
            or wanted_bank in [str(alias).lower() for alias in bank.get("aliases", [])]
        ]
    for bank in banks:
        center = bank.get("tile") or {}
        if "x" not in center or "y" not in center:
            continue
        rocks = rock_objects(bounds_around(center, args.site_search_radius), ores, max_level)
        for cluster in cluster_rocks(rocks, args.cluster_radius):
            if len(cluster) < args.min_rocks:
                continue
            site = site_from_cluster(bank, cluster, args, player_tile)
            if site["bankDistance"] > args.max_bank_distance:
                continue
            sites.append(site)
    sites.sort(key=lambda item: (item["score"], item["bankDistance"], -item["rockCount"], item["id"]))
    return sites[:args.max_site_candidates]


def route_to_target(target, args, handle, reason):
    command = [
        sys.executable,
        str(ROUTE_RUNNER),
        "--to",
        target,
        "--allow-frontier",
        "--direct-if-preview",
        "--probe-toward-target",
        "--run-reserve",
        str(args.run_reserve),
        "--max-batches",
        str(args.max_batches_per_leg),
        "--max-walk-distance",
        str(args.max_walk_distance),
        "--max-ticks",
        str(args.route_max_ticks),
    ]
    if args.profile:
        command.extend(["--profile", args.profile])
    if args.no_enable_run:
        command.append("--no-enable-run")
    write_event(handle, "route_start", {"reason": reason, "target": target, "command": command[1:]})
    proc = subprocess.Popen(
        command,
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout_lines = []
    if proc.stdout is not None:
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                stdout_lines.append(line)
                log(line)
                write_event(handle, "route_output", {"reason": reason, "line": line})
    stderr = proc.stderr.read().strip() if proc.stderr is not None else ""
    code = proc.wait()
    write_event(handle, "route_finish", {
        "reason": reason,
        "target": target,
        "returncode": code,
        "stdoutTail": stdout_lines[-8:],
        "stderr": stderr[:1000],
    })
    return code == 0


def route_to_tile(target_tile, args, handle, reason):
    return route_to_target(tile_string(target_tile), args, handle, reason)


def route_to_bank(site, args, handle):
    target = site.get("bankPlace") or tile_string(site["bankTile"])
    return route_to_target(target, args, handle, "bank")


def ensure_pickaxe(player, site, args, handle):
    carried = best_usable_pickaxe(player, in_bank=False)
    if carried:
        return player
    banked = best_usable_pickaxe(player, in_bank=True)
    if banked:
        if not player.get("inBankArea"):
            if not route_to_bank(site, args, handle):
                raise RuntimeError("could not route to bank to withdraw {}".format(banked["name"]))
            player = observe()
        result = call_tool("withdraw_bank_items", {"itemId": banked["itemId"], "amount": 1})
        write_event(handle, "withdraw_pickaxe", {
            "pickaxe": banked,
            "result": compact_player(player_from(result)),
        })
        return player_from(result)
    if args.auto_buy_bronze_pickaxe:
        return buy_bronze_pickaxe(player, args, handle)
    raise RuntimeError("no usable pickaxe is carried or banked; rerun with --auto-buy-bronze-pickaxe if a seller is reachable")


def buy_bronze_pickaxe(player, args, handle):
    if count_inventory_item(player, 995) < 1 and count_bank_item(player, 995) > 0:
        if not player.get("inBankArea"):
            raise RuntimeError("coins are banked but no bank/site is available before buying a pickaxe")
        player = player_from(call_tool("withdraw_bank_items", {"itemId": 995, "amount": 1}))
    if count_inventory_item(player, 995) < 1:
        raise RuntimeError("buying a bronze pickaxe requires at least 1 coin")
    shop_tile = parse_tile(args.pickaxe_shop_tile)
    if chebyshev(tile_from_player(player), shop_tile) > 4:
        if not route_to_tile(shop_tile, args, handle, "pickaxe_shop"):
            raise RuntimeError("could not route to bronze pickaxe seller at {}".format(tile_string(shop_tile)))
        player = observe()
    opened = call_tool("open_nearest_shop", {"name": args.pickaxe_shop_name, "maxDistance": 8})
    bought = call_tool("buy_shop_item", {"itemId": 1265, "amount": 1})
    write_event(handle, "buy_pickaxe", {
        "shop": opened.get("player", {}).get("shop", {}).get("name"),
        "result": compact_player(player_from(bought)),
    })
    return player_from(bought)


def route_to_site_if_needed(player, site, args, handle):
    if chebyshev(tile_from_player(player), site["tile"]) <= int(site.get("arrivalRadius", 4)):
        return player
    if not route_to_tile(site["tile"], args, handle, "mine_site"):
        raise RuntimeError("could not route to mine site {}".format(site["id"]))
    return observe()


def choose_live_ore(player, site, ores, args, handle):
    level = mining_level(player)
    candidates = [
        ore for ore in ores
        if ORE_DEFS[ore]["level"] <= level and site["oreCounts"].get(ore, 0) > 0
    ]
    if not candidates:
        raise RuntimeError("no requested ore is available at mining level {} in site {}".format(level, site["id"]))
    if args.strategy == "bronze-balanced" and "copper" in candidates and "tin" in candidates:
        copper = count_inventory_item(player, ORE_DEFS["copper"]["itemId"])
        tin = count_inventory_item(player, ORE_DEFS["tin"]["itemId"])
        preferred = "copper" if copper <= tin else "tin"
        candidates = [preferred] + [ore for ore in candidates if ore != preferred]
    live = []
    for ore in candidates:
        result = call_tool("find_nearest_rock", {
            "resource": ore,
            "maxDistance": int(site["rockScanDistance"]),
        })
        if not result.get("success"):
            continue
        obj = result.get("object") or {}
        distance = int(obj.get("distance", 999) or 999)
        definition = ORE_DEFS[ore]
        score = definition["xp"] * args.xp_weight
        score -= distance * args.rock_distance_weight
        score -= definition["respawnTicks"] * args.respawn_weight
        score += site["oreCounts"].get(ore, 0) * args.same_ore_density_weight
        live.append((score, ore, obj))
    if live:
        live.sort(key=lambda item: (-item[0], item[2].get("distance", 999), item[1]))
        chosen = live[0]
        write_event(handle, "ore_choice", {
            "ore": chosen[1],
            "score": round(chosen[0], 3),
            "object": chosen[2],
            "candidates": [{"ore": ore, "score": round(score, 3)} for score, ore, _obj in live],
        })
        return chosen[1]
    fallback = sorted(
        candidates,
        key=lambda ore: (-ORE_DEFS[ore]["xp"], ORE_DEFS[ore]["respawnTicks"], ore),
    )[0]
    write_event(handle, "ore_choice", {"ore": fallback, "reason": "no ready matching rock found"})
    return fallback


def mine_batch(ore, site, args, handle):
    payload = {
        "ore": ore,
        "maxDistance": int(site["rockScanDistance"]),
        "waitForLocalRespawn": bool(args.wait_for_local_respawn),
        "maxTicks": int(args.mine_max_ticks),
    }
    started = time.monotonic()
    result = call_tool("mine_ore_until_inventory_full", payload)
    elapsed = round(time.monotonic() - started, 3)
    player = player_from(result)
    write_event(handle, "mine_batch", {
        "ore": ore,
        "siteId": site["id"],
        "payload": payload,
        "success": bool(result.get("success")),
        "batchStatus": result.get("batchStatus"),
        "elapsedSeconds": elapsed,
        "player": compact_player(player),
        "message": result.get("message"),
    })
    status = result.get("batchStatus", "")
    log("mined {} status={} level={} xp={} freeSlots={} hp={} run={}".format(
        ore,
        status,
        mining_level(player),
        mining_xp(player),
        player.get("freeInventorySlots"),
        player.get("hitpoints"),
        player.get("runEnergy"),
    ))
    return result


def bank_ores(player, site, ores, args, handle):
    if inventory_ore_count(player, ORE_DEFS.keys()) <= 0:
        return player
    if not player.get("inBankArea"):
        if not route_to_bank(site, args, handle):
            raise RuntimeError("could not route to bank to deposit ores")
        player = observe()
    item_ids = [ORE_DEFS[ore]["itemId"] for ore in (ORE_DEFS.keys() if args.bank_all_ores else ores)]
    result = call_tool("deposit_inventory_items", {"itemIds": item_ids})
    player = player_from(result)
    write_event(handle, "bank_ores", {
        "itemIds": item_ids,
        "deposited": result.get("deposited"),
        "depositedAmount": result.get("depositedAmount"),
        "player": compact_player(player),
    })
    log("banked ores depositedAmount={} level={} xp={}".format(
        result.get("depositedAmount"),
        mining_level(player),
        mining_xp(player),
    ))
    return player


def choose_site(ores, args, player):
    if args.site and args.site != "auto":
        site_tile = parse_tile(args.site)
        bank_tile = parse_tile(args.bank_tile) if args.bank_tile else site_tile
        return {
            "id": "manual_{}".format(tile_string(site_tile).replace(",", "_")),
            "source": "manual",
            "bankPlace": args.bank,
            "bankName": args.bank or tile_string(bank_tile),
            "bankTile": bank_tile,
            "tile": site_tile,
            "arrivalRadius": args.arrival_radius,
            "rockScanDistance": args.rock_scan_distance,
            "oreCounts": {ore: 1 for ore in ores},
            "rockCount": len(ores),
            "bankDistance": chebyshev(site_tile, bank_tile),
            "currentDistance": chebyshev(site_tile, tile_from_player(player)),
            "score": 0,
            "rocks": [],
        }
    current_level = mining_level(player)
    max_level = max(current_level, args.target_mining_level or current_level)
    sites = discover_sites(ores, args, tile_from_player(player), max_level=max_level)
    sites = [
        site for site in sites
        if any(site["oreCounts"].get(ore, 0) > 0 and ORE_DEFS[ore]["level"] <= current_level for ore in ores)
    ]
    if not sites:
        raise RuntimeError("no cache mine sites found for ores {} near known banks".format(",".join(ores)))
    return sites[0]


def print_sites(sites, as_json=False):
    if as_json:
        print(json.dumps(sites, indent=2, sort_keys=True))
        return
    for site in sites:
        ores = ",".join("{}:{}".format(k, v) for k, v in sorted(site["oreCounts"].items()))
        print("{score:7.2f} {id} bank={bankPlace} bankDist={bankDistance} rocks={rockCount} ores={ores} tile={tile}".format(
            score=float(site["score"]),
            id=site["id"],
            bankPlace=site["bankPlace"],
            bankDistance=site["bankDistance"],
            rockCount=site["rockCount"],
            ores=ores,
            tile=tile_string(site["tile"]),
        ))


def open_run_log(args):
    if args.no_log:
        return None, None
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = "{}-{}".format(dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:8])
    path = RUNS_DIR / "{}.jsonl".format(run_id)
    handle = path.open("a", encoding="utf-8")
    return handle, str(path)


def run(args):
    global RUN_PROFILE
    RUN_PROFILE = args.profile or ""
    ores = parse_ores(args.ores)
    if args.list_sites:
        max_level = args.max_static_ore_level
        sites = discover_sites(ores, args, player_tile=args.current_tile, max_level=max_level)
        print_sites(sites, args.json)
        return 0

    handle, log_path = open_run_log(args)
    try:
        write_event(handle, "run_start", {
            "args": vars(args),
            "ores": ores,
            "logPath": log_path,
        })
        player = observe()
        player = ensure_run(player, args)
        site = choose_site(ores, args, player)
        write_event(handle, "site_selected", {"site": site, "player": compact_player(player)})
        log("selected mining site {} bank={} tile={} ores={}".format(
            site["id"], site.get("bankPlace"), tile_string(site["tile"]), site["oreCounts"]))
        player = ensure_pickaxe(player, site, args, handle)
        loads_done = 0
        batches_done = 0
        while True:
            if args.target_mining_level and mining_level(player) >= args.target_mining_level:
                log("target mining level reached: {}".format(mining_level(player)))
                write_event(handle, "target_reached", {"player": compact_player(player)})
                break
            if args.max_loads is not None and loads_done >= args.max_loads:
                log("max loads reached: {}".format(loads_done))
                break
            if args.max_mining_batches is not None and batches_done >= args.max_mining_batches:
                log("max mining batches reached: {}".format(batches_done))
                break
            if bool(player.get("isDead")) or bool(player.get("isInCombat")):
                write_event(handle, "safety_stop", {"player": compact_player(player)})
                raise RuntimeError("stopping because the player is dead or in combat")
            site = choose_site(ores, args, player)
            player = route_to_site_if_needed(player, site, args, handle)
            ore = choose_live_ore(player, site, ores, args, handle)
            result = mine_batch(ore, site, args, handle)
            player = player_from(result)
            batches_done += 1
            if args.target_mining_level and mining_level(player) >= args.target_mining_level:
                player = bank_ores(player, site, ores, args, handle)
                log("target mining level reached: {}".format(mining_level(player)))
                write_event(handle, "target_reached", {"player": compact_player(player)})
                break
            if int(player.get("freeInventorySlots", 0) or 0) < 1:
                player = bank_ores(player, site, ores, args, handle)
                loads_done += 1
            elif result.get("batchStatus") == "blocked":
                write_event(handle, "blocked", {"resultMessage": result.get("message"), "player": compact_player(player)})
                if args.stop_on_blocked:
                    raise RuntimeError("mining blocked: {}".format(result.get("message")))
            else:
                time.sleep(max(0.0, args.loop_delay))
        write_event(handle, "run_finish", {
            "loadsDone": loads_done,
            "batchesDone": batches_done,
            "player": compact_player(player),
        })
        if log_path:
            log("mining log: {}".format(log_path))
        return 0
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run adaptive 2006Scape mining and ore-banking loops.")
    parser.add_argument("--profile", default="", help="Bridge profile/session to use.")
    parser.add_argument("--ores", default="copper,tin,iron",
                        help="Comma-separated desired ores. Default: copper,tin,iron.")
    parser.add_argument("--target-mining-level", type=int, default=0,
                        help="Stop after reaching this Mining level.")
    parser.add_argument("--max-loads", type=int,
                        help="Stop after this many banked ore loads.")
    parser.add_argument("--max-mining-batches", type=int,
                        help="Stop after this many mining batches.")
    parser.add_argument("--site", default="auto",
                        help="auto or manual site tile X,Y,H.")
    parser.add_argument("--bank", default="",
                        help="Restrict auto site discovery to this bank place id/name/alias, or use as the manual bank route target.")
    parser.add_argument("--bank-tile", default="",
                        help="Manual bank tile X,Y,H when --site is a coordinate and no bank place is known.")
    parser.add_argument("--arrival-radius", type=int, default=5)
    parser.add_argument("--strategy", choices=["fastest", "bronze-balanced"], default="fastest")
    parser.add_argument("--list-sites", action="store_true",
                        help="List static cache-discovered mine sites without touching the bridge.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--current-tile", type=parse_tile,
                        help="Optional current tile for static site ranking when using --list-sites.")
    parser.add_argument("--site-search-radius", type=int, default=220)
    parser.add_argument("--cluster-radius", type=int, default=24)
    parser.add_argument("--min-rocks", type=int, default=2)
    parser.add_argument("--max-bank-distance", type=int, default=180)
    parser.add_argument("--max-site-candidates", type=int, default=25)
    parser.add_argument("--max-static-ore-level", type=int, default=99)
    parser.add_argument("--bank-distance-weight", type=float, default=1.0)
    parser.add_argument("--current-distance-weight", type=float, default=0.25)
    parser.add_argument("--rock-scan-distance", type=int, default=24)
    parser.add_argument("--xp-weight", type=float, default=2.0)
    parser.add_argument("--rock-distance-weight", type=float, default=1.0)
    parser.add_argument("--respawn-weight", type=float, default=0.15)
    parser.add_argument("--same-ore-density-weight", type=float, default=0.75)
    parser.add_argument("--wait-for-local-respawn", action="store_true", default=True)
    parser.add_argument("--no-wait-for-local-respawn", dest="wait_for_local_respawn", action="store_false")
    parser.add_argument("--mine-max-ticks", type=int, default=250)
    parser.add_argument("--max-batches-per-leg", type=int, default=8)
    parser.add_argument("--max-walk-distance", type=int, default=48)
    parser.add_argument("--route-max-ticks", type=int, default=180)
    parser.add_argument("--run-reserve", default="auto")
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--no-enable-run", action="store_true")
    parser.add_argument("--bank-all-ores", action="store_true", default=True)
    parser.add_argument("--no-bank-all-ores", dest="bank_all_ores", action="store_false")
    parser.add_argument("--auto-buy-bronze-pickaxe", action="store_true")
    parser.add_argument("--pickaxe-shop-tile", default="2614,3293,0",
                        help="Bronze-pickaxe seller tile used by --auto-buy-bronze-pickaxe.")
    parser.add_argument("--pickaxe-shop-name", default="aemad")
    parser.add_argument("--stop-on-blocked", action="store_true")
    parser.add_argument("--loop-delay", type=float, default=0.2)
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
