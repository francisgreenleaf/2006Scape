#!/usr/bin/env python3
"""Shared compactors for experimental *_XS agent wrappers."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
XP_RECENT_SECONDS = 300
XP_STATE_DEFAULT = ROOT / "agent-navigation" / ".local" / "xs-skill-xp-state.json"


def dump(payload):
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def run_command(command, cwd=None, env=None):
    effective_env = dict(os.environ if env is None else env)
    effective_env.setdefault("AGENT_NAV_XS_PARENT", "xs")
    return subprocess.run(
        command,
        cwd=str(cwd or ROOT),
        env=effective_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def parse_json(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Some tools print a single JSON object after warnings or status lines.
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def tail_text(text, limit=600):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def tile(value):
    if not isinstance(value, dict):
        return value
    x = value.get("x")
    y = value.get("y")
    h = value.get("height", value.get("h", 0))
    if x is None or y is None:
        return value
    return "{},{},{}".format(x, y, h)


def item(value):
    if not isinstance(value, dict):
        return value
    out = {
        "s": value.get("slot"),
        "slot": value.get("slotName"),
        "id": value.get("id"),
        "n": value.get("name"),
        "a": value.get("amount"),
    }
    if value.get("foodHeal"):
        out["heal"] = value.get("foodHeal")
    return {k: v for k, v in out.items() if v is not None}


def ground_item(value):
    if not isinstance(value, dict):
        return value
    out = {
        "id": value.get("id", value.get("itemId")),
        "n": value.get("name"),
        "a": value.get("amount"),
        "t": tile(value),
        "d": value.get("distance", value.get("dist")),
    }
    return {k: v for k, v in out.items() if v is not None}


def npc(value):
    if not isinstance(value, dict):
        return value
    out = {
        "i": value.get("npcIndex", value.get("idx")),
        "n": value.get("name"),
        "lvl": value.get("combatLevel", value.get("level")),
        "t": tile(value),
        "d": value.get("distance", value.get("dist")),
        "hp": value.get("hitpoints", value.get("hp")),
        "max": value.get("maxHitpoints", value.get("maxHp")),
    }
    if value.get("aggressive") is True:
        out["agg"] = True
    if value.get("underAttack") is True:
        out["atk"] = True
    return {k: v for k, v in out.items() if v is not None}


def game_object(value):
    if not isinstance(value, dict):
        return value
    out = {
        "id": value.get("objectId", value.get("id")),
        "n": value.get("name"),
        "t": tile(value),
        "d": value.get("distance", value.get("dist")),
        "r": value.get("reachable"),
    }
    if value.get("interactionInRange") is True or value.get("inRange") is True:
        out["in"] = True
    walk = value.get("interactionWalkTarget") or value.get("walkTarget")
    near = value.get("nearestInteractionTile") or value.get("near")
    if walk:
        out["w"] = tile(walk)
    elif near:
        out["near"] = tile(near)
    return {k: v for k, v in out.items() if v is not None}


def player(value):
    if not isinstance(value, dict):
        return None
    out = {
        "n": value.get("name"),
        "t": tile(value),
        "hp": value.get("hitpoints", value.get("hp")),
        "max": value.get("maxHitpoints", value.get("maxHp")),
        "cb": value.get("combatLevel"),
        "run": value.get("runEnergy"),
        "runOn": value.get("runEnabled"),
        "free": value.get("freeInventorySlots", value.get("freeSlots")),
    }
    flags = []
    if value.get("isMoving") or value.get("moving"):
        flags.append("moving")
    if value.get("isInCombat") or value.get("inCombat"):
        flags.append("combat")
    if value.get("isDead") or value.get("dead"):
        flags.append("dead")
    skilling = [
        "isMining", "isWoodcutting", "isFishing", "isCooking", "isSmithing",
        "isSmelting", "isFletching", "isFiremaking", "isShopping",
    ]
    for key in skilling:
        if value.get(key):
            flags.append(key[2:].lower())
    if flags:
        out["flags"] = flags
    xp_recent = recent_xp_summary(value)
    if xp_recent:
        out["xpRecent"] = xp_recent
    return {k: v for k, v in out.items() if v is not None}


def all_skill_summary(player_data):
    skills = player_data.get("skills") if isinstance(player_data, dict) else None
    if not isinstance(skills, dict):
        return {}
    out = {}
    for name, skill in skills.items():
        if not isinstance(skill, dict):
            continue
        if str(name).startswith("unused"):
            continue
        level = skill.get("level")
        xp = skill.get("xp")
        base = skill.get("baseLevel")
        # Level-1 zero-xp skills are usually noise unless currently relevant.
        if level in (None, 1) and xp in (None, 0):
            continue
        entry = {"lvl": level, "xp": xp}
        if base not in (None, level):
            entry["base"] = base
        out[name] = {k: v for k, v in entry.items() if v is not None}
    return out


def int_or_none(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def xp_state_path():
    disabled = os.environ.get("XS_DISABLE_XP_STATE", "").lower()
    if disabled in ("1", "true", "yes", "on"):
        return None
    override = os.environ.get("XS_XP_STATE_PATH")
    if override:
        if override.lower() in ("off", "none", "disabled"):
            return None
        return Path(override)
    return XP_STATE_DEFAULT


def load_xp_state():
    path = xp_state_path()
    if path is None:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_xp_state(state):
    path = xp_state_path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(state, separators=(",", ":"), sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def recent_xp_summary(player_data, now=None, ttl=XP_RECENT_SECONDS):
    current = all_skill_summary(player_data)
    if not current:
        return {}
    profile = str(player_data.get("name") or "unknown").lower()
    now = int(now if now is not None else time.time())
    state = load_xp_state()
    profiles = state.setdefault("profiles", {})
    profile_state = profiles.setdefault(profile, {})
    last = profile_state.setdefault("skills", {})
    recent = profile_state.setdefault("recent", {})

    for name, skill in current.items():
        xp = int_or_none(skill.get("xp"))
        level = int_or_none(skill.get("lvl"))
        if xp is None:
            continue
        prior = last.get(name) if isinstance(last.get(name), dict) else {}
        prior_xp = int_or_none(prior.get("xp"))
        prior_level = int_or_none(prior.get("lvl"))
        if prior_xp is not None and xp > prior_xp:
            existing = recent.get(name) if isinstance(recent.get(name), dict) else {}
            if existing and now - int(existing.get("at") or 0) <= ttl:
                from_xp = int_or_none(existing.get("fromXp"))
                from_level = int_or_none(existing.get("fromLvl"))
            else:
                from_xp = prior_xp
                from_level = prior_level
            recent[name] = {
                "at": now,
                "fromXp": from_xp,
                "fromLvl": from_level,
                "xp": xp,
                "lvl": level,
            }
        last[name] = {"xp": xp, "lvl": level}

    out = {}
    for name in list(recent.keys()):
        entry = recent.get(name) if isinstance(recent.get(name), dict) else {}
        at = int_or_none(entry.get("at"))
        xp = int_or_none(entry.get("xp"))
        from_xp = int_or_none(entry.get("fromXp"))
        if at is None or xp is None or from_xp is None or now - at > ttl:
            recent.pop(name, None)
            continue
        summary = {
            "gain": max(0, xp - from_xp),
            "xp": xp,
            "lvl": int_or_none(entry.get("lvl")),
            "fromXp": from_xp,
            "age": now - at,
        }
        from_level = int_or_none(entry.get("fromLvl"))
        if from_level is not None and summary["lvl"] is not None and from_level != summary["lvl"]:
            summary["fromLvl"] = from_level
        out[name] = {k: v for k, v in summary.items() if v is not None}

    save_xp_state(state)
    return out


def inventory_counts(items, limit=12):
    counts = {}
    order = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        key = (entry.get("id"), entry.get("name"), entry.get("foodHeal"))
        if key not in counts:
            counts[key] = 0
            order.append(key)
        counts[key] += int(entry.get("amount") or 1)
    out = []
    for key in order[:limit]:
        item_id, name, heal = key
        entry = {"id": item_id, "n": name, "a": counts[key]}
        if heal:
            entry["heal"] = heal
        out.append({k: v for k, v in entry.items() if v is not None})
    if len(order) > limit:
        out.append({"more": len(order) - limit})
    return out


def inventory_from(data, limit=12):
    p = data.get("player") if isinstance(data, dict) else {}
    inv = data.get("inventory") if isinstance(data, dict) else None
    if inv is None and isinstance(p, dict):
        inv = p.get("inventory")
    inv = inv if isinstance(inv, list) else []
    food = [entry for entry in inv if isinstance(entry, dict) and entry.get("foodHeal")]
    return {
        "food": len(food),
        "heal": sum(int(entry.get("foodHeal") or 0) * int(entry.get("amount") or 1) for entry in food),
        "counts": inventory_counts(inv),
        "items": [item(entry) for entry in inv[:limit]],
    }


def equipment_from(player_data, limit=8):
    equipment = player_data.get("equipment") if isinstance(player_data, dict) else []
    if not isinstance(equipment, list):
        return []
    return [item(entry) for entry in equipment[:limit]]


def bank_summary(player_data, limit=8):
    bank = player_data.get("bank") if isinstance(player_data, dict) else []
    if not isinstance(bank, list):
        return None
    coins = 0
    food = 0
    food_heal = 0
    for entry in bank:
        if not isinstance(entry, dict):
            continue
        if int(entry.get("id") or 0) == 995:
            coins += int(entry.get("amount") or 0)
        if entry.get("foodHeal"):
            amount = int(entry.get("amount") or 1)
            food += amount
            food_heal += amount * int(entry.get("foodHeal") or 0)
    return {
        "count": len(bank),
        "coins": coins,
        "food": food,
        "heal": food_heal,
        "items": [item(entry) for entry in bank[:limit]],
    }


def operation_fields(data):
    keys = (
        "complete", "batchStatus", "batchTicks", "waitedTicks", "submittedTick",
        "targetTick", "serverTick", "arrived", "approaching", "pickedUp",
        "equipped", "reachable", "pathLength",
    )
    out = {key: data.get(key) for key in keys if data.get(key) not in (None, "", [], {})}
    message = data.get("message")
    if message and message not in ("Observed current game state.",):
        out["msg"] = message
    return out


def compact_observe(data, npc_limit=8, object_limit=12, include_bank=True,
                    include_equipment=True, inventory_limit=12):
    p = data.get("player", {}) if isinstance(data, dict) else {}
    combat = p.get("combatReadiness") if isinstance(p, dict) else {}
    if not isinstance(combat, dict):
        combat = data.get("combatReadiness", {}) if isinstance(data, dict) else {}
    area = combat.get("recommendedArea") if isinstance(combat, dict) else None
    if isinstance(area, dict):
        area = {
            "name": area.get("name"),
            "npc": area.get("npcName"),
            "maxHit": area.get("maxHit"),
            "until": area.get("recommendedUntilLevel"),
        }
    payload = {
        "ok": bool(data.get("success")),
        "tick": data.get("serverTick", data.get("tick")),
        "op": operation_fields(data),
        "p": player(p),
        "combat": {
            "target": npc(data.get("targetNpc") or p.get("targetNpc")) if isinstance(p, dict) and (data.get("targetNpc") or p.get("targetNpc")) else None,
            "by": p.get("underAttackBy") if isinstance(p, dict) else None,
            "by2": p.get("underAttackBy2") if isinstance(p, dict) else None,
            "eat": combat.get("eatAtHitpoints"),
            "retreat": combat.get("retreatAtHitpoints"),
            "invFood": combat.get("inventoryFoodCount"),
            "invHeal": combat.get("inventoryFoodHealing"),
            "bankFood": combat.get("bankFoodCount"),
            "invCoins": combat.get("inventoryCoins"),
            "bankCoins": combat.get("bankCoins"),
            "area": area,
        },
        "inv": inventory_from(data, limit=inventory_limit),
        "eq": equipment_from(p) if include_equipment else [],
        "bank": bank_summary(p) if include_bank else None,
        "npcs": [npc(entry) for entry in sorted(data.get("nearbyNpcs", []), key=lambda n: n.get("distance", n.get("dist", 999)))[:npc_limit]],
        "objs": [game_object(entry) for entry in sorted(data.get("nearbyObjects", []), key=lambda o: o.get("distance", o.get("dist", 999)))[:object_limit]],
        "ground": [ground_item(entry) for entry in sorted(data.get("nearbyGroundItems", []), key=lambda item: item.get("distance", item.get("dist", 999)))[:8]],
    }
    if not payload["op"]:
        payload.pop("op")
    payload["combat"] = {k: v for k, v in payload["combat"].items() if v is not None}
    if not payload["combat"]:
        payload.pop("combat")
    for key in ("eq", "ground"):
        if not payload.get(key):
            payload.pop(key, None)
    if not payload.get("bank"):
        payload.pop("bank", None)
    return payload


def route_steps(steps, limit=8):
    out = []
    for index, step in enumerate(steps or []):
        if index >= limit:
            break
        if not isinstance(step, dict):
            out.append(step)
            continue
        target = step.get("to") or step.get("tile") or step.get("target")
        if target is None and step.get("x") is not None and step.get("y") is not None:
            target = step
        entry = {
            "i": step.get("index", step.get("order", index + 1)),
            "t": step.get("type"),
            "to": tile(target),
            "near": tile(step.get("near")) if step.get("near") else None,
            "run": step.get("run"),
        }
        if step.get("objectId"):
            entry["obj"] = step.get("objectId")
        if step.get("objectName"):
            entry["objN"] = step.get("objectName")
        text = step.get("instruction") or step.get("label") or step.get("place")
        if text:
            entry["txt"] = str(text)[:90]
        out.append({k: v for k, v in entry.items() if v is not None})
    if steps and len(steps) > limit:
        out.append({"more": len(steps) - limit})
    return out


def run_plan(value):
    if not isinstance(value, dict):
        return value
    keys = (
        "mode", "policy", "reserve", "reserveEnergy", "minimumEnergy",
        "wouldRun", "runRequired", "required", "reason", "warning",
        "routeDistance", "walkTileDistance", "runTileDistance", "segmentCount",
    )
    out = {key: value.get(key) for key in keys if key in value and value.get(key) not in (None, "", [])}
    segments = value.get("segments") or value.get("runSegments")
    if isinstance(segments, list) and segments:
        out["segments"] = [
            {k: seg.get(k) for k in ("from", "to", "minRunEnergy", "requiresRun", "risk", "distance") if seg.get(k) is not None}
            for seg in segments[:4] if isinstance(seg, dict)
        ]
        if len(segments) > 4:
            out["segmentMore"] = len(segments) - 4
    return out or value


def safety(value):
    if not isinstance(value, dict):
        return value
    out = {
        "review": value.get("requiresReview"),
        "warnings": value.get("warnings")[:5] if isinstance(value.get("warnings"), list) else value.get("warnings"),
        "hazards": (value.get("hazardWarnings") or value.get("hazards"))[:5]
        if isinstance(value.get("hazardWarnings") or value.get("hazards"), list)
        else value.get("hazardWarnings") or value.get("hazards"),
        "wrongWay": value.get("wrongWayFlags")[:5] if isinstance(value.get("wrongWayFlags"), list) else value.get("wrongWayFlags"),
        "detours": value.get("detourSegments")[:5] if isinstance(value.get("detourSegments"), list) else value.get("detourSegments"),
    }
    return {k: v for k, v in out.items() if v not in (None, "", [])}


def route_evidence(value):
    if not isinstance(value, dict):
        return value
    routes = value.get("routesUsed")
    out = {
        "level": value.get("level"),
        "proven": value.get("proven"),
        "src": value.get("edgeSources"),
        "routes": list(routes.keys())[:3] if isinstance(routes, dict) else routes,
    }
    if value.get("summary"):
        out["note"] = str(value.get("summary"))[:120]
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}


def compact_command(command, limit=10):
    if not isinstance(command, list):
        return command
    return " ".join(str(part) for part in command[:limit]) + (" ..." if len(command) > limit else "")


def compact_feedback(value):
    if not isinstance(value, dict):
        return None
    command = value.get("manualOutcomeCommand")
    if isinstance(command, list):
        command = list(command)
        for index, part in enumerate(command):
            if str(part).endswith("agent-navigation/ml-routing/route_ml.py"):
                command[index] = str(part).replace("route_ml.py", "route_ml_XS.py")
                break
    out = {
        "events": value.get("automaticEvents"),
        "evidence": value.get("automaticEvidenceJsonl"),
        "fields": value.get("manualFields")[:8] if isinstance(value.get("manualFields"), list) else value.get("manualFields"),
        "cmd": compact_command(command, limit=9),
    }
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}


def route_definition(data):
    if not isinstance(data, dict):
        return data
    execution = data.get("execution") if isinstance(data.get("execution"), dict) else {}
    command = execution.get("command")
    exec_summary = {
        "strategy": execution.get("strategy"),
        "maxBatch": execution.get("maxBatchDistance"),
        "runnerMax": execution.get("runnerMaxBatches"),
    } if execution else None
    if isinstance(exec_summary, dict):
        exec_summary = {k: v for k, v in exec_summary.items() if v not in (None, "", [], {})}
    out = {
        "api": data.get("api"),
        "ok": data.get("actionable"),
        "id": data.get("routeId"),
        "from": data.get("from"),
        "to": data.get("to"),
        "status": data.get("status"),
        "quality": data.get("quality"),
        "mode": data.get("mode"),
        "score": data.get("score"),
        "dist": data.get("routeDistance"),
        "distTiles": data.get("distanceTiles"),
        "direct": data.get("directDistance"),
        "detour": data.get("detourRatio"),
        "ticks": data.get("estimatedTicks"),
        "arrival": data.get("arrivalRadius"),
        "planner": data.get("planner"),
        "tdInc": data.get("targetDistanceIncreases"),
        "evidence": route_evidence(data.get("evidence")),
        "next": tile(data.get("next")),
        "end": tile(data.get("endTile") or data.get("targetTile")),
        "stepCount": data.get("routeStepCount"),
        "steps": route_steps(data.get("routeSteps"), limit=8),
        "run": run_plan(data.get("runPlan")),
        "runSegments": data.get("runSegments")[:4] if isinstance(data.get("runSegments"), list) else data.get("runSegments"),
        "safety": safety(data.get("safety")),
        "path": execution.get("routeDefinitionPath"),
        "cmd": compact_command(command, limit=10),
        "exec": exec_summary,
        "feedback": compact_feedback(data.get("feedback")),
        "error": data.get("error"),
        "message": data.get("message"),
        "layers": data.get("coordinateLayers"),
        "transition": data.get("transition"),
    }
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}


def compact_route_ml(data):
    if not isinstance(data, dict):
        return data
    if data.get("api") == "2006scape.route-definition" or "routeSteps" in data:
        return route_definition(data)
    recommended = data.get("recommended")
    if isinstance(recommended, dict):
        out = {
            "request": data.get("request"),
            "recommended": route_definition(recommended.get("routeDefinition") or recommended),
            "candidates": [],
        }
        if isinstance(recommended.get("selectedOverLearned"), dict):
            selected = recommended["selectedOverLearned"]
            out["selectedOverLearned"] = {
                "reason": selected.get("reason"),
                "saved": selected.get("savedTiles"),
                "prevQuality": selected.get("previousQuality"),
                "prevStatus": selected.get("previousStatus"),
            }
        if isinstance(recommended.get("learnedCandidate"), dict):
            learned = recommended["learnedCandidate"]
            out["learned"] = {
                "status": learned.get("status"),
                "quality": learned.get("quality"),
                "next": tile(learned.get("next")),
                "dist": learned.get("routeDistance"),
                "detour": learned.get("detourRatio"),
                "warnings": learned.get("hazardWarnings", [])[:4] if isinstance(learned.get("hazardWarnings"), list) else learned.get("hazardWarnings"),
            }
        for cand in (data.get("candidates") or [])[:3]:
            if isinstance(cand, dict):
                out["candidates"].append({
                    "mode": cand.get("mode"),
                    "status": cand.get("status"),
                    "quality": cand.get("quality"),
                    "score": cand.get("score"),
                    "next": tile(cand.get("next")),
                    "dist": cand.get("routeDistance"),
                    "detour": cand.get("detourRatio"),
                })
        return {k: v for k, v in out.items() if v not in (None, "", [], {})}
    if "results" in data and isinstance(data["results"], list):
        return {
            "caseCount": data.get("caseCount"),
            "ok": data.get("okCount", data.get("actionableCount")),
            "bad": data.get("badCount"),
            "output": data.get("outputDir"),
            "results": [
                {
                    "case": item.get("case"),
                    "status": item.get("status"),
                    "quality": item.get("quality"),
                    "steps": len(item.get("routeSteps") or []),
                    "run": run_plan(item.get("runPlan")),
                }
                for item in data["results"][:8] if isinstance(item, dict)
            ],
        }
    return data


def compact_preview(data):
    if not isinstance(data, dict):
        return data
    path = data.get("path") or data.get("steps") or []
    path_tiles = [tile(entry) for entry in path] if isinstance(path, list) else []
    path_sample = None
    if path_tiles:
        path_sample = path_tiles if len(path_tiles) <= 8 else path_tiles[:4] + ["...{}...".format(len(path_tiles) - 8)] + path_tiles[-4:]
    out = {
        "ok": data.get("success"),
        "reachable": data.get("reachable"),
        "complete": data.get("complete"),
        "steps": data.get("stepCount", data.get("pathLength", len(path) if isinstance(path, list) else None)),
        "target": tile(data.get("target") or data.get("destination")),
        "walk": tile(data.get("walkTarget") or data.get("interactionWalkTarget")),
        "end": tile(path[-1]) if isinstance(path, list) and path else None,
        "path": path_sample,
        "blocked": data.get("blockedReason") or data.get("failureReason"),
    }
    return {k: v for k, v in out.items() if v is not None}


def compact_bridge(data, tool=None):
    if not isinstance(data, dict):
        return data
    if data.get("compact") is True or data.get("xxs") is True:
        return data
    if tool in ("food_bank", "food_bank_XS"):
        return compact_food_bank(data)
    if "nearbyNpcs" in data or "nearbyObjects" in data:
        return compact_observe(
            data,
            npc_limit=8,
            object_limit=8,
            include_bank=(tool == "observe_state"),
            include_equipment=tool in ("observe_state", "equip_best_items", "attack_npc"),
            inventory_limit=12 if tool == "observe_state" else 8,
        )
    bank_tools = (
        "deposit_inventory_items", "withdraw_bank_items", "deposit_excess_coins",
        "buy_shop_item", "sell_inventory_item", "sell_inventory_items",
        "open_nearest_shop",
    )
    player_data = data.get("player") if isinstance(data.get("player"), dict) else None
    out = {
        "ok": data.get("success"),
        "msg": data.get("message"),
        "complete": data.get("complete"),
        "status": data.get("batchStatus") or data.get("status"),
        "tick": data.get("serverTick"),
        "batchTicks": data.get("batchTicks"),
        "waited": data.get("waitedTicks"),
        "arrived": data.get("arrived"),
        "reachable": data.get("reachable"),
        "objectReachable": data.get("objectReachable"),
        "p": player(player_data) if player_data else None,
        "inv": inventory_from(data, limit=8) if player_data else None,
        "bank": bank_summary(player_data) if player_data and tool in bank_tools else None,
        "preview": compact_preview(data.get("preview")) if isinstance(data.get("preview"), dict) else None,
        "dest": tile(data.get("target") or data.get("destination")) if isinstance(data.get("target") or data.get("destination"), dict) else None,
        "final": tile(data.get("finalTile")) if isinstance(data.get("finalTile"), dict) else None,
        "moveNear": data.get("moveNear"),
        "applyBounds": data.get("applyBounds"),
        "maxWalk": data.get("maxWalkDistance"),
        "target": npc(data.get("targetNpc")) if isinstance(data.get("targetNpc"), dict) else None,
        "object": game_object(data.get("object")) if isinstance(data.get("object"), dict) else None,
        "npc": npc(data.get("npc")) if isinstance(data.get("npc"), dict) else None,
        "itemId": data.get("itemId"),
        "amount": data.get("amount"),
        "deposited": data.get("deposited"),
        "depositedAmount": data.get("depositedAmount"),
        "withdrawn": data.get("withdrawn"),
        "withdrawnAmount": data.get("withdrawnAmount"),
        "dropped": data.get("dropped"),
        "picked": data.get("pickedUpAmount"),
        "bought": data.get("bought"),
        "sold": data.get("sold"),
        "soldAmount": data.get("soldAmount"),
        "price": data.get("price"),
        "candidates": [npc(entry) for entry in (data.get("candidates") or [])[:8]] if isinstance(data.get("candidates"), list) else None,
        "groundItem": ground_item(data.get("groundItem")) if isinstance(data.get("groundItem"), dict) else None,
        "equippedItems": [item(entry) for entry in (data.get("equippedItems") or [])[:8]] if isinstance(data.get("equippedItems"), list) else None,
        "equipped": data.get("equipped"),
        "pickedUp": data.get("pickedUp"),
        "run": {
            key: data.get(key)
            for key in ("runReq", "runBefore", "runAfter", "runSpent", "expectedRunSpend", "runWarn", "tps", "tilesPerTick")
            if data.get(key) is not None
        },
        "error": data.get("error"),
    }
    if isinstance(data.get("path"), list):
        path_tiles = [tile(entry) for entry in data["path"]]
        sample = path_tiles if len(path_tiles) <= 8 else path_tiles[:4] + ["...{}...".format(len(path_tiles) - 8)] + path_tiles[-4:]
        out["path"] = {"n": len(data["path"]), "end": tile(data["path"][-1]) if data["path"] else None, "sample": sample}
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}


def compact_food_bank(data):
    if not isinstance(data, dict):
        return data
    player_data = data.get("player") if isinstance(data.get("player"), dict) else data
    combat = player_data.get("combatReadiness") if isinstance(player_data, dict) else {}
    inv = inventory_from({"player": player_data}, limit=12)
    bank = bank_summary(player_data, limit=12)
    raw_food = []
    cooked_food = []
    burnt_food = []
    tools = []
    inventory = player_data.get("inventory") if isinstance(player_data, dict) else []
    bank_items = player_data.get("bank") if isinstance(player_data, dict) else []
    for source, collection in (("inv", inventory), ("bank", bank_items)):
        if not isinstance(collection, list):
            continue
        for entry in collection:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").lower()
            compact = item(entry)
            compact["src"] = source
            if "raw " in name:
                raw_food.append(compact)
            elif "burnt" in name:
                burnt_food.append(compact)
            elif entry.get("foodHeal"):
                cooked_food.append(compact)
            elif name in ("small fishing net", "fishing rod", "fly fishing rod", "harpoon", "lobster pot", "knife", "tinderbox"):
                tools.append(compact)
    out = {
        "ok": bool(data.get("success", True)),
        "p": player(player_data),
        "inv": inv,
        "bank": bank,
        "food": {
            "raw": raw_food[:8],
            "cooked": cooked_food[:8],
            "burnt": burnt_food[:8],
            "tools": tools[:8],
        },
        "combat": {
            "eat": combat.get("eatAtHitpoints") if isinstance(combat, dict) else None,
            "retreat": combat.get("retreatAtHitpoints") if isinstance(combat, dict) else None,
            "invFood": combat.get("inventoryFoodCount") if isinstance(combat, dict) else None,
            "invHeal": combat.get("inventoryFoodHealing") if isinstance(combat, dict) else None,
            "bankFood": combat.get("bankFoodCount") if isinstance(combat, dict) else None,
            "bankCoins": combat.get("bankCoins") if isinstance(combat, dict) else None,
        },
    }
    out["combat"] = {k: v for k, v in out["combat"].items() if v is not None}
    out["food"] = {k: v for k, v in out["food"].items() if v}
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}


def compact_context_map(data):
    if not isinstance(data, dict):
        return data
    sidecar = {}
    summary_path = data.get("summary")
    if summary_path:
        try:
            path = Path(summary_path)
            if path.exists() and path.is_file():
                sidecar = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            sidecar = {}
    markers = []
    for marker in (sidecar.get("mapFunctionMarkers") or data.get("mapFunctionMarkers") or [])[:10]:
        if isinstance(marker, dict):
            markers.append({
                "n": marker.get("name") or marker.get("label") or marker.get("objectName"),
                "id": marker.get("id") or marker.get("objectId") or marker.get("mapFunction"),
                "t": tile(marker.get("tile") or marker),
            })
    out = {
        "ok": data.get("success"),
        "png": data.get("output"),
        "json": data.get("summary"),
        "bounds": data.get("bounds"),
        "center": tile(data.get("center")) if isinstance(data.get("center"), dict) else data.get("center"),
        "span": data.get("spanTiles"),
        "grid": data.get("currentGridCell") or data.get("centerGridCell"),
        "cells": data.get("referenceGridCells")[:12] if isinstance(data.get("referenceGridCells"), list) else data.get("referenceGridCells"),
        "mapIcons": data.get("mapFunctionMarkerCount"),
        "iconsDrawn": data.get("mapFunctionIconsDrawn"),
        "markers": markers,
        "places": data.get("placeLabelsDrawn"),
        "recent": data.get("recentEdgesDrawn"),
        "segment": data.get("segmentEdgesDrawn"),
        "trace": data.get("traceRecordsConsidered"),
        "anchors": data.get("contextAnchors")[:8] if isinstance(data.get("contextAnchors"), list) else data.get("contextAnchors"),
    }
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}


def compact_route_runner(data):
    if not isinstance(data, dict):
        return data
    out = {
        "ok": data.get("success", data.get("status") == "ok"),
        "target": data.get("target"),
        "from": tile(data.get("from") or data.get("currentTile")),
        "status": data.get("status") or (data.get("plan") or {}).get("status"),
        "quality": data.get("quality") or (data.get("evaluation") or data.get("routeEval") or {}).get("quality"),
        "next": tile(data.get("next") or (data.get("plan") or {}).get("next")),
        "preview": compact_preview(data.get("preview")) if isinstance(data.get("preview"), dict) else None,
        "run": run_plan(data.get("run") or data.get("runPolicy") or data.get("runPlan")),
        "eval": None,
        "map": None,
    }
    evaluation = data.get("evaluation") or data.get("routeEval")
    if isinstance(evaluation, dict):
        out["eval"] = {
            "quality": evaluation.get("quality"),
            "detour": evaluation.get("detourRatio"),
            "wrong": len(evaluation.get("wrongWay") or []),
            "suspects": evaluation.get("suspects", [])[:4] if isinstance(evaluation.get("suspects"), list) else evaluation.get("suspects"),
        }
    context = data.get("contextMap")
    if isinstance(context, dict):
        out["map"] = compact_context_map(context)
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}


def compact_text_output(text, limit_lines=12):
    lines = [line.rstrip() for line in (text or "").splitlines() if line.strip()]
    if len(lines) <= limit_lines:
        return {"lines": lines}
    head = lines[: max(1, limit_lines // 2)]
    tail = lines[-max(1, limit_lines // 2):]
    return {"lines": head + ["... {} lines omitted ...".format(len(lines) - len(head) - len(tail))] + tail}


def compact_navdb_text(command, text):
    lines = [line.rstrip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return {"ok": True}
    subcommand = command[0] if command else ""
    if subcommand == "validate":
        errors = [line for line in lines if line.startswith("ERROR:")][:8]
        return {"ok": not errors, "summary": lines[-1], "errors": errors}
    if subcommand == "self-test":
        fails = [line for line in lines if line.startswith("FAIL")][:8]
        return {"ok": not fails, "summary": lines[-1], "failures": fails}
    if subcommand == "graph-summary":
        summary = {}
        edges = []
        for line in lines:
            if ":" in line and "->" not in line:
                key, value = line.split(":", 1)
                summary[key.strip().replace(" ", "_")] = value.strip()
            elif "->" in line and len(edges) < 8:
                match = re.match(r"(.+? -> .+?) \| success=(\d+) fail=(\d+)", line)
                if match:
                    edges.append({"edge": match.group(1), "ok": int(match.group(2)), "fail": int(match.group(3))})
                else:
                    edges.append(line)
        return {"summary": summary, "edges": edges, "edgeMore": max(0, len([line for line in lines if "->" in line]) - len(edges))}
    if subcommand == "next-step":
        out = {}
        hazards = []
        warnings = []
        mode = None
        def short_path(value):
            parts = [part.strip() for part in value.split("->")]
            if len(parts) <= 8:
                return " -> ".join(parts)
            return " -> ".join(parts[:4] + ["... {} omitted ...".format(len(parts) - 7)] + parts[-3:])
        for line in lines:
            if line.startswith("route:"):
                out["route"] = line
            elif line.startswith("next:"):
                out["next"] = line
            elif line.startswith("instruction:"):
                out["instruction"] = line[len("instruction:"):].strip()
            elif line.startswith("graphPath:"):
                out["graphPath"] = short_path(line[len("graphPath:"):].strip())
            elif line.startswith("hazards:"):
                mode = "hazards"
            elif line.startswith("warnings:"):
                mode = "warnings"
            elif line.startswith("  ") and mode == "hazards" and len(hazards) < 5:
                text = line.strip()
                hazard, note = (text.split(" - ", 1) + [""])[:2] if " - " in text else (text, "")
                entry = {"hazard": hazard}
                if note:
                    entry["note"] = note[:160]
                hazards.append(entry)
            elif line.startswith("  ") and mode == "warnings" and len(warnings) < 5:
                warnings.append(line.strip())
        if hazards:
            out["hazards"] = hazards
        if warnings:
            out["warnings"] = warnings
        return out or compact_text_output(text)
    if subcommand in ("hazards", "route-risk"):
        return compact_text_output(text, limit_lines=10)
    return compact_text_output(text)


def emit_process_result(proc, compactor, raw_text_compactor=None):
    data = parse_json(proc.stdout)
    if data is not None:
        dump(compactor(data))
    else:
        payload = raw_text_compactor(proc.stdout) if raw_text_compactor else compact_text_output(proc.stdout)
        if proc.stderr.strip():
            payload["stderr"] = tail_text(proc.stderr)
        dump(payload)
    return proc.returncode


def main_error(message, code=2):
    dump({"ok": False, "error": message})
    return code
