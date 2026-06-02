#!/usr/bin/env python3
"""Compact wrapper around rs.observe_state for routine navigation decisions."""

import json
import argparse
import os
import subprocess
from pathlib import Path

from usage_log import log_usage
from profile_utils import resolve_profile

ROOT = Path(__file__).resolve().parents[1]
RSTOOL = ROOT / "tools" / "rs-tool.sh"


def compact_item(item):
    return {
        "slot": item.get("slot"),
        "id": item.get("id"),
        "name": item.get("name"),
        "amount": item.get("amount"),
        **({"foodHeal": item.get("foodHeal")} if item.get("foodHeal") else {}),
    }


def compact_npc(npc):
    return {
        "idx": npc.get("npcIndex", npc.get("index", npc.get("idx"))),
        "name": npc.get("name"),
        "level": npc.get("combatLevel", npc.get("level")),
        "x": npc.get("x"),
        "y": npc.get("y"),
        "h": npc.get("height", npc.get("h")),
        "tile": npc.get("tile"),
        "dist": npc.get("distance"),
        "hp": npc.get("hitpoints", npc.get("hp")),
        "maxHp": npc.get("maxHitpoints", npc.get("maxHp")),
        "aggressive": npc.get("aggressive"),
        "underAttack": npc.get("underAttack"),
    }


def compact_object(obj):
    out = {
        "id": obj.get("objectId"),
        "name": obj.get("name"),
        "x": obj.get("x"),
        "y": obj.get("y"),
        "h": obj.get("height"),
        "tile": obj.get("tile"),
        "dist": obj.get("distance"),
        "reachable": obj.get("reachable"),
        "inRange": obj.get("interactionInRange"),
    }
    if obj.get("interactionWalkTarget"):
        t = obj["interactionWalkTarget"]
        out["walkTarget"] = (
            {"x": t.get("x"), "y": t.get("y"), "h": t.get("height")}
            if isinstance(t, dict) else t
        )
    if obj.get("nearestInteractionTile"):
        t = obj["nearestInteractionTile"]
        out["near"] = (
            {"x": t.get("x"), "y": t.get("y"), "h": t.get("height")}
            if isinstance(t, dict) else t
        )
    return out


def main():
    parser = argparse.ArgumentParser(description="Compact observe_state wrapper for one selected profile.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    args = parser.parse_args()
    log_usage("observe-slim", surface="legacy")
    env = os.environ.copy()
    if args.profile:
        env["RS_PROFILE"] = args.profile
    raw = subprocess.check_output([str(RSTOOL), "observe_state_XS", "{}"], cwd=str(ROOT.parent), text=True, env=env)
    data = json.loads(raw)
    if not data.get("success"):
        print(json.dumps({"success": False, "message": data.get("message", "observe_state failed")}, sort_keys=True))
        raise SystemExit(1)
    p = data.get("player", {})
    inv_data = data.get("inventory") or p.get("inventory", [])
    if isinstance(inv_data, dict):
        inv = inv_data.get("items") or inv_data.get("counts") or []
    elif isinstance(inv_data, list):
        inv = inv_data
    else:
        inv = []
    inv = [item for item in inv if isinstance(item, dict)]
    food = [item for item in inv if item.get("foodHeal")]
    nearby_npcs = sorted(data.get("nearbyNpcs", []), key=lambda n: n.get("distance", 999))[:12]
    nearby_objects = sorted(data.get("nearbyObjects", []), key=lambda o: o.get("distance", 999))[:16]
    payload = {
        "success": True,
        "tick": data.get("serverTick"),
        "player": {
            "name": p.get("name"),
            "x": p.get("x"),
            "y": p.get("y"),
            "h": p.get("height"),
            "hp": p.get("hitpoints"),
            "maxHp": p.get("maxHitpoints"),
            "combatLevel": p.get("combatLevel"),
            "runEnergy": p.get("runEnergy"),
            "runEnabled": p.get("runEnabled"),
            "moving": p.get("isMoving"),
            "inCombat": p.get("isInCombat"),
            "dead": p.get("isDead"),
            "freeSlots": p.get("freeInventorySlots"),
        },
        "combat": {
            "target": compact_npc(data.get("targetNpc") or p.get("targetNpc")) if (data.get("targetNpc") or p.get("targetNpc")) else None,
            "underAttackBy": p.get("underAttackBy"),
            "underAttackBy2": p.get("underAttackBy2"),
            "eatAtHp": data.get("combatReadiness", {}).get("eatAtHitpoints"),
            "retreatAtHp": data.get("combatReadiness", {}).get("retreatAtHitpoints"),
        },
        "inventory": {
            "foodCount": len(food),
            "foodHealing": sum(int(item.get("foodHeal") or 0) * int(item.get("amount") or 1) for item in food),
            "items": [compact_item(item) for item in inv[:12]],
        },
        "nearbyNpcs": [compact_npc(npc) for npc in nearby_npcs],
        "nearbyObjects": [compact_object(obj) for obj in nearby_objects],
    }
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
