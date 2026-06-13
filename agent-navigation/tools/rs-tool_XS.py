#!/usr/bin/env python3
"""Extra-slim wrapper around a single rs bridge tool call."""

import argparse
import json
import os
from pathlib import Path

from xs_common import ROOT, compact_bridge, dump, run_command
from profile_utils import resolve_profile
from usage_log import log_usage
import bridge_script as bridge


RS_TOOL = Path(__file__).resolve().parent / "rs-tool.sh"

XS_TOOL_BASES = {
    "observe_state",
    "observe_state_if_changed",
    "combat_state",
    "walk_path_steps",
    "walk_to_tile_until_arrived",
    "travel_to_landmark_until_arrived",
    "wait_ticks",
    "wait_until_idle",
    "wait_until_combat_event",
    "wait_until_combat_event_smart",
    "object_transition_step",
    "interact_object",
    "find_nearest_object",
    "find_nearest_rock",
    "find_nearest_tree",
    "bury_bones",
    "deposit_inventory_items",
    "withdraw_bank_items",
    "bank_item_count",
    "agent_chat_send",
    "agent_chat_read",
    "agent_chat_status",
    "unequip_item",
    "unequip_items",
    "food_bank",
}


def xs_tool_name(tool):
    if tool.endswith("_XS"):
        return tool
    if tool.endswith("_XXS"):
        base = tool[:-4]
        return base + "_XS" if base in XS_TOOL_BASES else tool
    if tool in XS_TOOL_BASES:
        return tool + "_XS"
    return tool


def main():
    parser = argparse.ArgumentParser(description="Call an rs bridge tool and emit an extra-slim response.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("tool")
    parser.add_argument("arguments", nargs="?", default="{}")
    args = parser.parse_args()

    try:
        parsed = json.loads(args.arguments)
    except json.JSONDecodeError as exc:
        dump({"ok": False, "error": "invalid JSON arguments: {}".format(exc)})
        return 2
    if not isinstance(parsed, dict):
        dump({"ok": False, "error": "arguments must be a JSON object"})
        return 2

    tool = xs_tool_name(args.tool)
    if bridge._has_batched_withdraw_args(tool, parsed):
        log_usage("rs-tool_XS", surface="xs", argv=[tool, parsed])
        data = bridge.call_tool(tool, parsed, profile=args.profile)
        payload = compact_bridge(data, tool)
        if isinstance(payload, dict):
            payload.setdefault("tool", tool)
        dump(payload)
        return 0 if bool(payload.get("success", payload.get("ok", False))) else 1

    env = os.environ.copy()
    if args.profile:
        env["RS_PROFILE"] = args.profile
    log_usage("rs-tool_XS", surface="xs", argv=[tool, parsed])
    proc = run_command([str(RS_TOOL), tool, json.dumps(parsed, separators=(",", ":"))], cwd=ROOT, env=env)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        dump({"ok": False, "tool": tool, "stderr": proc.stderr.strip()[-500:], "stdout": proc.stdout.strip()[-500:]})
        return proc.returncode or 2

    payload = compact_bridge(data, tool)
    if isinstance(payload, dict):
        payload.setdefault("tool", tool)
    dump(payload)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
