#!/usr/bin/env python3
"""Move a profile safely from Lumbridge/Al Kharid to the Agility Pyramid start."""

import argparse
import datetime as dt
import json
import uuid

import bridge_script as bridge
from profile_utils import resolve_profile


RUN_BASE_DIR = bridge.ROOT / ".local" / "runners"
SHANTAY_PASS = 1854
FULL_WATERSKIN = 1823
SHANTAY_PASS_PRICE = 5
FULL_WATERSKIN_PRICE = 30
AL_KHARID_TOLL = 10
DESERT_RESUME_RADIUS = 16

SHANTAY_TO_PYRAMID_WEST_ROCKS = [
    (3304, 3113, 0), (3303, 3112, 0), (3303, 3110, 0), (3299, 3106, 0),
    (3299, 3082, 0), (3299, 3072, 0), (3309, 3062, 0), (3309, 3060, 0),
    (3333, 3036, 0), (3334, 3035, 0), (3334, 3034, 0), (3354, 3014, 0),
    (3354, 3011, 0), (3360, 3005, 0), (3360, 2997, 0), (3361, 2996, 0),
    (3361, 2987, 0), (3363, 2985, 0), (3363, 2976, 0), (3362, 2976, 0),
    (3362, 2972, 0), (3357, 2967, 0), (3357, 2965, 0), (3356, 2964, 0),
    (3356, 2963, 0), (3354, 2961, 0), (3346, 2961, 0), (3346, 2960, 0),
    (3343, 2957, 0), (3339, 2957, 0), (3335, 2953, 0), (3331, 2953, 0),
    (3307, 2929, 0), (3302, 2924, 0), (3301, 2924, 0), (3296, 2919, 0),
    (3293, 2919, 0), (3292, 2918, 0), (3292, 2917, 0), (3289, 2914, 0),
    (3289, 2912, 0), (3288, 2911, 0), (3288, 2909, 0), (3284, 2905, 0),
    (3284, 2896, 0), (3286, 2896, 0), (3287, 2895, 0), (3291, 2895, 0),
    (3315, 2871, 0), (3339, 2847, 0), (3343, 2843, 0),
]


def tile(player):
    return int(player["x"]), int(player["y"]), int(player.get("height", 0))


def same_tile(player, target):
    return tile(player) == tuple(target)


def runner_dir(profile):
    return RUN_BASE_DIR / str(profile).strip().lower()


def hitpoints(player):
    return int(player.get("hitpoints", player.get("hp", 0)) or 0)


def log(handle, event, **payload):
    if handle is None:
        return
    payload["event"] = event
    payload["timestamp"] = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
    handle.flush()


def require_safe(player, label):
    if player.get("isDead"):
        raise RuntimeError("{}: player is dead".format(label))
    if player.get("isInCombat") or int(player.get("underAttackBy", 0) or 0) > 0 or int(player.get("underAttackBy2", 0) or 0) > 0:
        raise RuntimeError("{}: player is in combat".format(label))
    hp = int(player.get("hitpoints", player.get("hp", 0)) or 0)
    eat_attempts = 0
    while hp < 8 and eat_attempts < 5:
        eat_attempts += 1
        try:
            result = bridge.call_tool("eat_best_food_XXS", {}, profile=PROFILE)
        except RuntimeError:
            break
        player = bridge.player_from(result)
        hp = int(player.get("hitpoints", player.get("hp", 0)) or 0)
    if hp <= 4:
        raise RuntimeError("{}: hitpoints are too low ({})".format(label, hp))
    return player


def wait_idle(profile, max_ticks=12):
    return bridge.player_from(bridge.call_tool("wait_until_idle_XS", {
        "maxTicks": int(max_ticks),
        "movement": True,
        "skilling": False,
        "combat": False,
    }, profile=profile))


def walk_to(profile, player, target, handle, label, max_ticks=90, max_distance=48):
    player = require_safe(player, label + "_pre")
    if same_tile(player, target):
        return player
    result = bridge.call_tool("walk_to_tile_until_arrived_XS", {
        "x": int(target[0]),
        "y": int(target[1]),
        "height": int(target[2]),
        "stopDistance": 0,
        "maxTicks": int(max_ticks),
        "maxWalkDistance": int(max_distance),
        "stopOnCombat": True,
        "stopOnStall": True,
    }, profile=profile)
    player = bridge.player_from(result)
    log(handle, "walk", label=label, target=target, success=bool(result.get("success")),
        message=result.get("message"), tile=tile(player), batchStatus=result.get("batchStatus"))
    player = require_safe(player, label)
    if not same_tile(player, target):
        player = wait_idle(profile, 8)
    if not same_tile(player, target):
        raise RuntimeError("{}: failed to reach {}; now at {}".format(label, target, tile(player)))
    return player


def walk_path(profile, player, waypoints, handle, label):
    for i, target in enumerate(waypoints, start=1):
        player = walk_to(profile, player, target, handle, "{}_{}".format(label, i))
    return player


def densify_path(waypoints, max_step=8):
    dense = []
    previous = None
    for target in waypoints:
        if previous is None:
            dense.append(target)
            previous = target
            continue
        dx = target[0] - previous[0]
        dy = target[1] - previous[1]
        dh = target[2] - previous[2]
        steps = max(1, int(max(abs(dx), abs(dy)) + max_step - 1) // int(max_step))
        for step in range(1, steps + 1):
            dense.append((
                previous[0] + int(round(dx * step / float(steps))),
                previous[1] + int(round(dy * step / float(steps))),
                previous[2] + int(round(dh * step / float(steps))),
            ))
        previous = target
    return dense


def interact_object(profile, player, object_id, x, y, h, handle, label, wait_ticks=8):
    result = bridge.call_tool("interact_object_XS", {
        "objectId": int(object_id),
        "x": int(x),
        "y": int(y),
        "height": int(h),
        "option": "first",
        "requireReachable": True,
    }, profile=profile)
    player = bridge.player_from(result)
    log(handle, "object", label=label, objectId=object_id, objectTile=(x, y, h),
        success=bool(result.get("success")), message=result.get("message"), tile=tile(player),
        objectReachable=result.get("objectReachable"))
    if not result.get("success"):
        raise RuntimeError("{}: object interaction failed: {}".format(label, result.get("message")))
    player = wait_idle(profile, wait_ticks)
    return require_safe(player, label)


def count_item(player, item_id):
    return bridge.count_inventory_item(player, item_id)


def required_supply_coins(player, required_waterskins):
    coins = 0
    if count_item(player, SHANTAY_PASS) <= 0:
        coins += SHANTAY_PASS_PRICE
    missing_waterskins = max(0, int(required_waterskins) - count_item(player, FULL_WATERSKIN))
    coins += missing_waterskins * FULL_WATERSKIN_PRICE
    return coins


def require_carried_coins(player, amount, label):
    coins = count_item(player, bridge.COINS)
    if coins < int(amount):
        raise RuntimeError("{}: need {} carried coins; have {}".format(label, int(amount), coins))


def tile_string(player):
    return "{},{},{}".format(*tile(player))


def is_shantay_shop_area(player):
    x, y, h = tile(player)
    return h == 0 and 3295 <= x <= 3311 and 3116 <= y <= 3128


def is_lumbridge_to_al_kharid_gate_area(player):
    x, y, h = tile(player)
    return h == 0 and 3200 <= x <= 3268 and 3190 <= y <= 3260


def is_al_kharid_to_shantay_area(player):
    x, y, h = tile(player)
    return h == 0 and 3268 <= x <= 3330 and 3120 <= y <= 3228


def is_desert_to_pyramid_area(player):
    x, y, h = tile(player)
    return h == 0 and 3280 <= x <= 3370 and 2830 <= y <= 3115


def status_payload(profile, player, required_waterskins):
    carried_coins = count_item(player, bridge.COINS)
    carried_passes = count_item(player, SHANTAY_PASS)
    carried_waterskins = count_item(player, FULL_WATERSKIN)
    supply_coins = required_supply_coins(player, required_waterskins)
    location = "unsupported"
    required_carried_coins = None
    ready = False
    reason = ""

    if tile(player) == (3355, 2830, 0):
        location = "pyramid_start"
        required_carried_coins = 0
        ready = True
        reason = "already_at_pyramid_start"
    elif is_lumbridge_to_al_kharid_gate_area(player):
        location = "lumbridge_to_al_kharid_gate_area"
        required_carried_coins = AL_KHARID_TOLL + supply_coins
        ready = carried_coins >= required_carried_coins
        reason = "ready_for_al_kharid_toll_and_shantay_supplies" if ready else "needs_carried_coins"
    elif is_al_kharid_to_shantay_area(player) or is_shantay_shop_area(player) or tile(player) == (3278, 3212, 0):
        location = "al_kharid_or_shantay_area"
        required_carried_coins = supply_coins
        ready = carried_coins >= required_carried_coins
        reason = "ready_for_shantay_supplies" if ready else "needs_carried_coins"
    elif tile(player) == (3304, 3115, 0) or is_desert_to_pyramid_area(player):
        location = "desert_to_pyramid_area"
        required_carried_coins = 0
        ready = carried_waterskins >= int(required_waterskins)
        reason = "ready_for_desert_to_pyramid" if ready else "needs_waterskins_before_desert_resume"
    else:
        reason = "unsupported_start_location"

    return {
        "ok": True,
        "profile": profile,
        "tile": tile_string(player),
        "hp": hitpoints(player),
        "maxHp": int(player.get("maxHitpoints", player.get("maxHp", 0)) or 0),
        "isDead": bool(player.get("isDead", False)),
        "isInCombat": bool(player.get("isInCombat", False)),
        "location": location,
        "readyForSetup": bool(ready) and not player.get("isDead") and not player.get("isInCombat"),
        "reason": reason,
        "requiredWaterskins": int(required_waterskins),
        "carriedWaterskins": carried_waterskins,
        "missingWaterskins": max(0, int(required_waterskins) - carried_waterskins),
        "carriedPasses": carried_passes,
        "carriedCoins": carried_coins,
        "requiredCarriedCoins": required_carried_coins,
        "missingCoins": max(0, int(required_carried_coins or 0) - carried_coins),
        "supplyCoins": supply_coins,
        "alKharidToll": AL_KHARID_TOLL,
        "nextCommand": "python3 agent-navigation/tools/agility_pyramid_travel_setup.py --profile {} --waterskins {}".format(
            profile, int(required_waterskins)),
    }


def wait_for_safe_hp(profile, player, handle, label, min_hp=10):
    if not is_shantay_shop_area(player):
        return require_safe(player, label)
    rounds = 0
    while hitpoints(player) < int(min_hp) and rounds < 40:
        rounds += 1
        result = bridge.call_tool("wait_ticks_XXS", {"ticks": 25}, profile=profile)
        player = bridge.player_from(result)
        log(handle, "wait_hp", label=label, hp=hitpoints(player), minHp=int(min_hp),
            tile=tile(player), waitedTicks=result.get("waitedTicks"))
        player = require_safe(player, label)
    if hitpoints(player) < int(min_hp):
        raise RuntimeError("{}: hitpoints did not recover to {}; hp={}".format(label, int(min_hp), hitpoints(player)))
    return player


def route_to_shantay(profile, player, handle, required_waterskins):
    if is_shantay_shop_area(player):
        return player

    supply_coins = required_supply_coins(player, required_waterskins)
    if is_lumbridge_to_al_kharid_gate_area(player):
        require_carried_coins(player, AL_KHARID_TOLL + supply_coins, "route_to_shantay")
        player = walk_to(profile, player, (3267, 3227, 0), handle, "walk_to_al_kharid_gate_west",
                         max_ticks=90, max_distance=80)
        try:
            player = bridge.cross_al_kharid_toll_gate(
                player,
                to_east=True,
                profile=profile,
                handle=handle,
                reason="pyramid_setup_al_kharid_gate",
                approach_max_ticks=24,
                approach_max_walk_distance=12,
            )
        except bridge.ObjectTransitionError as exc:
            raise RuntimeError("route_to_shantay: {}".format(exc)) from exc

    if is_al_kharid_to_shantay_area(player):
        require_carried_coins(player, supply_coins, "route_to_shantay")
        for label, target in (
            ("walk_to_al_kharid_kebab_shop", (3275, 3180, 0)),
            ("walk_to_al_kharid_general_store", (3313, 3183, 0)),
            ("walk_to_shantay", (3303, 3124, 0)),
        ):
            if is_shantay_shop_area(player):
                break
            player = walk_to(profile, player, target, handle, label, max_ticks=90, max_distance=72)
        return player

    raise RuntimeError("route_to_shantay: no supported safe route from {}".format(tile(player)))


def buy_shantay_supplies(profile, player, handle, required_waterskins):
    player = walk_to(profile, player, (3303, 3124, 0), handle, "walk_to_shantay", max_ticks=120, max_distance=64)
    result = bridge.call_tool("open_nearest_shop", {"name": "shantay", "maxDistance": 8}, profile=profile)
    player = bridge.player_from(result)
    log(handle, "shop", label="open_shantay_shop", success=bool(result.get("success")),
        message=result.get("message"), tile=tile(player))
    if not result.get("success"):
        raise RuntimeError("could not open Shantay shop: {}".format(result.get("message")))

    needed = required_supply_coins(player, required_waterskins)
    require_carried_coins(player, needed, "buy_shantay_supplies")

    if count_item(player, SHANTAY_PASS) <= 0:
        result = bridge.call_tool("buy_shop_item", {"itemId": SHANTAY_PASS, "amount": 1}, profile=profile)
        player = bridge.player_from(result)
        log(handle, "buy", label="buy_shantay_pass", itemId=SHANTAY_PASS, success=bool(result.get("success")),
            message=result.get("message"), passCount=count_item(player, SHANTAY_PASS),
            coins=count_item(player, bridge.COINS), tile=tile(player))
        if count_item(player, SHANTAY_PASS) <= 0:
            raise RuntimeError("failed to buy Shantay pass: {}".format(result.get("message")))

    while count_item(player, FULL_WATERSKIN) < int(required_waterskins):
        result = bridge.call_tool("buy_shop_item", {"itemId": FULL_WATERSKIN, "amount": 1}, profile=profile)
        player = bridge.player_from(result)
        log(handle, "buy", label="buy_required_waterskin", itemId=FULL_WATERSKIN,
            success=bool(result.get("success")), message=result.get("message"),
            waterskins=count_item(player, FULL_WATERSKIN), coins=count_item(player, bridge.COINS), tile=tile(player))
        if not result.get("success"):
            raise RuntimeError("failed to buy required waterskin: {}".format(result.get("message")))
    if count_item(player, FULL_WATERSKIN) < int(required_waterskins):
        raise RuntimeError("need {} waterskin(4); have {}".format(
            int(required_waterskins), count_item(player, FULL_WATERSKIN)))
    return player


def cross_shantay_gate(profile, player, handle):
    player = walk_to(profile, player, (3304, 3117, 0), handle, "walk_to_shantay_gate_north", max_ticks=24, max_distance=12)
    player = interact_object(profile, player, 4031, 3302, 3116, 0, handle, "cross_shantay_gate", wait_ticks=6)
    if tile(player) != (3304, 3115, 0):
        player = wait_idle(profile, 8)
    if tile(player) != (3304, 3115, 0):
        raise RuntimeError("failed to cross Shantay gate south; now at {}".format(tile(player)))
    return player


def desert_waypoints_from_current(player, waypoints):
    current = tile(player)
    candidates = []
    for index, target in enumerate(waypoints):
        if int(target[2]) != current[2]:
            continue
        # Agility Pyramid travel is southbound. Avoid selecting a waypoint that
        # sends a wounded resume run materially back north through heat.
        if int(target[1]) > current[1] + 8:
            continue
        distance = max(abs(int(target[0]) - current[0]), abs(int(target[1]) - current[1]))
        candidates.append((distance, index, target))
    if not candidates:
        raise RuntimeError("desert resume: no forward waypoint from {}".format(current))
    distance, index, target = min(candidates, key=lambda item: (item[0], item[1]))
    if distance > DESERT_RESUME_RADIUS:
        raise RuntimeError("desert resume: nearest forward waypoint {} is {} tiles from {}".format(
            target, distance, current))
    return waypoints[index:]


def enter_pyramid(profile, player, handle, required_waterskins):
    if count_item(player, FULL_WATERSKIN) < int(required_waterskins):
        raise RuntimeError("refusing desert travel without {} waterskin(4); have {}".format(
            int(required_waterskins), count_item(player, FULL_WATERSKIN)))
    waypoints = densify_path(SHANTAY_TO_PYRAMID_WEST_ROCKS, max_step=8)
    waypoints = desert_waypoints_from_current(player, waypoints)
    player = walk_path(profile, player, waypoints, handle, "desert_to_pyramid")
    player = interact_object(profile, player, 10852, 3344, 2843, 0, handle, "enter_pyramid_rocks", wait_ticks=6)
    if tile(player)[0] != 3349:
        player = wait_idle(profile, 8)
    if tile(player)[0] != 3349:
        raise RuntimeError("failed to enter Pyramid rocks; now at {}".format(tile(player)))
    player = walk_to(profile, player, (3355, 2830, 0), handle, "walk_to_first_pyramid_stair_hotspot",
                     max_ticks=32, max_distance=24)
    return player


def main(argv=None):
    parser = argparse.ArgumentParser(description="Move a profile to the Agility Pyramid first stair hotspot.")
    parser.add_argument("--profile", default=resolve_profile(default="Mrathlete"))
    parser.add_argument("--waterskins", type=int, default=2,
                        help="Minimum carried waterskin(4) count before any desert crossing.")
    parser.add_argument("--status", action="store_true",
                        help="Print compact readiness status without moving, shopping, or opening a log.")
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args(argv)

    global PROFILE
    PROFILE = args.profile
    if args.status:
        player = bridge.observe(args.profile)
        print(json.dumps(status_payload(args.profile, player, args.waterskins), sort_keys=True, separators=(",", ":")))
        return 0

    run_id = "{}-{}".format(dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:8])
    run_dir = runner_dir(args.profile)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "agility-pyramid-setup-{}.jsonl".format(run_id)
    handle = None if args.no_log else log_path.open("a", encoding="utf-8")
    try:
        player = require_safe(bridge.observe(args.profile), "initial_observe")
        if tile(player) != (3355, 2830, 0):
            if tile(player) == (3278, 3212, 0) or is_lumbridge_to_al_kharid_gate_area(player) or is_al_kharid_to_shantay_area(player):
                player = route_to_shantay(args.profile, player, handle, args.waterskins)
                player = buy_shantay_supplies(args.profile, player, handle, args.waterskins)
                player = wait_for_safe_hp(args.profile, player, handle, "pre_desert_hp", min_hp=10)
                player = cross_shantay_gate(args.profile, player, handle)
            if tile(player) == (3304, 3115, 0) or (3280 <= tile(player)[0] <= 3370 and 2830 <= tile(player)[1] <= 3115):
                player = enter_pyramid(args.profile, player, handle, args.waterskins)
        if tile(player) != (3355, 2830, 0):
            raise RuntimeError("setup ended before Pyramid start; now at {}".format(tile(player)))
        log(handle, "complete", tile=tile(player), player=bridge.compact_player(player, ("agility",)))
        print(json.dumps({
            "success": True,
            "profile": args.profile,
            "tile": "{},{},{}".format(*tile(player)),
            "log": str(log_path) if handle is not None else None,
        }, separators=(",", ":")))
        return 0
    finally:
        if handle is not None:
            handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
