#!/usr/bin/env python3
"""Render a combined fog-of-war map for every local player profile.

This is intentionally separate from the per-profile active map wrappers. It
reuses the shared movement topology renderer but writes only its own output.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import render_movement_topology_v2 as v2
from profile_utils import safe_profile


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CHARACTER_DIR = REPO_ROOT / "2006Scape Server" / "data" / "characters"
PLAYER_TRACE_DIR = REPO_ROOT / "2006Scape Server" / "data" / "logs" / "player-movement-traces"
DEFAULT_OUTPUT = ROOT / "topology" / "all-players-fog-map.png"
DEFAULT_SUMMARY = ROOT / ".local" / "map-summaries" / "all-players-fog-map.json"
DEFAULT_CACHE_DIR = ROOT / ".local" / "topology-render-cache" / "all-players-fog-map"

PROFILE_COLORS = [
    (255, 221, 78),
    (95, 205, 255),
    (92, 224, 128),
    (255, 120, 205),
    (255, 165, 72),
    (178, 145, 255),
]

PROFILE_SORT_ORDER = {
    "mrflame": 0,
    "mrfish": 1,
    "mrwood": 2,
    "mrathlete": 3,
}

LEVEL_SKILLS = [
    ("attack", "ATK"),
    ("strength", "STR"),
    ("defence", "DEF"),
    ("hitpoints", "HP"),
    ("ranged", "RNG"),
    ("magic", "MAG"),
    ("prayer", "PRY"),
]


def profile_memory_state(profile: str) -> dict:
    path = (
        REPO_ROOT
        / "2006Scape Server"
        / "data"
        / "logs"
        / "agent-sessions"
        / "profiles"
        / safe_profile(profile)
        / "agent-personality-state.json"
    )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def discover_profiles() -> list[str]:
    profiles = set()
    for path in CHARACTER_DIR.glob("*.txt"):
        profiles.add(path.stem)
    for path in PLAYER_TRACE_DIR.glob("*/*.jsonl"):
        profiles.add(path.stem)
    return sorted(
        profiles,
        key=lambda value: (PROFILE_SORT_ORDER.get(safe_profile(value), 100), safe_profile(value)),
    )


def display_profile(profile: str) -> str:
    text = str(profile or "").strip()
    if not text:
        return "Unknown"
    if text.lower().startswith("mr") and len(text) > 2:
        return "Mr" + text[2:].capitalize()
    return text[:1].upper() + text[1:]


def build_args(parsed: argparse.Namespace, trace_profile: str = "") -> SimpleNamespace:
    reserve_lines = "\n".join(["profile coverage"] * 5)
    return SimpleNamespace(
        trace_file=None,
        trace_profile=trace_profile,
        include_unscoped_traces=False,
        include_agent_batch_traces=False,
        include_historical_agent_batch_traces=True,
        include_legacy_recorder_traces=False,
        coverage_cache=not parsed.no_coverage_cache,
        topology_cache=not parsed.no_topology_cache,
        coverage_cache_dir=str(parsed.coverage_cache_dir),
        output=str(parsed.output),
        summary=str(parsed.summary),
        pixels_per_tile=parsed.pixels_per_tile,
        max_map_pixels=parsed.max_map_pixels,
        padding_tiles=parsed.padding_tiles,
        bounds_quantum_tiles=64,
        tighten_east_south_bounds=True,
        surface_only=True,
        include_underground=False,
        plane=0,
        world_map_source="cache",
        no_world_map=False,
        supersample=2,
        background_mute=0.18,
        grid_alpha=0.0,
        major_grid_alpha=0.0,
        reference_grid=False,
        reference_grid_origin="level0",
        reference_grid_row_origin="south",
        reference_grid_cell_tiles=32.0,
        reference_grid_alpha=0.0,
        reference_grid_major_alpha=0.0,
        reference_grid_major_every=4,
        reference_grid_label_alpha=0.0,
        reference_grid_label_pointsize=24,
        reference_grid_cell_labels="none",
        reference_grid_cell_label_alpha=0.0,
        reference_grid_cell_label_pointsize=13,
        route_width=2.2,
        node_alpha=0.28,
        map_version="All Players Fog",
        title_text="All Players Fog",
        title_paragraph=reserve_lines,
        title_paragraph_x=600,
        title_paragraph_y=35,
        title_paragraph_lines=5,
        title_paragraph_align="left",
        title_paragraph_right_margin=34,
        title_paragraph_char_factor=0.56,
        title_stats_panel=False,
        title_stats_x=-1,
        title_stats_y=30,
        show_pois=True,
        poi_mode="all",
        poi_labels=True,
        poi_icon_scale=1.0,
        poi_label_pointsize=28,
        hide_fogged_pois=True,
        running_overlay=True,
        coverage_heatmap=False,
        coverage_heat_radius_tiles=18.0,
        coverage_heat_alpha=0.12,
        coverage_heat_high_percentile=0.98,
        coverage_heat_gamma=1.25,
        coverage_fog=True,
        coverage_fog_alpha=parsed.fog_alpha,
        coverage_fog_radius_tiles=parsed.fog_radius_tiles,
        coverage_fog_core_fraction=0.34,
        coverage_fog_poi_extra_tiles=4.0,
        min_world_coordinate=1024,
        max_edge_distance=8,
        title_pointsize=72,
        section_pointsize=38,
        legend_pointsize=28,
        stats_pointsize=24,
        meta_pointsize=28,
    )


def load_profile_topology(profile: str, parsed: argparse.Namespace):
    args = build_args(parsed, trace_profile=profile)
    args.coverage_cache_dir = str(Path(parsed.coverage_cache_dir) / ("profile-" + safe_profile(profile)))
    topology = v2.load_topology_with_cache(args.trace_file, args.surface_only, args)
    topology = v2.filter_implausible_topology(topology, args.min_world_coordinate)
    topology = v2.filter_nonlocal_edges(topology, args.max_edge_distance)
    return topology


def merge_text_min(current: str, candidate: str) -> str:
    if not current:
        return candidate or ""
    if not candidate:
        return current
    return candidate if candidate < current else current


def merge_text_max(current: str, candidate: str) -> str:
    if not current:
        return candidate or ""
    if not candidate:
        return current
    return candidate if candidate > current else current


def merge_node(target: dict, node: dict) -> None:
    for key in ("visits", "combatTicks", "failures", "deaths"):
        target[key] = int(target.get(key, 0)) + int(node.get(key, 0))
    target["firstSeen"] = merge_text_min(target.get("firstSeen", ""), node.get("firstSeen", ""))
    target["lastSeen"] = merge_text_max(target.get("lastSeen", ""), node.get("lastSeen", ""))


def merge_edge(target: dict, edge: dict) -> None:
    for key, value in edge.items():
        if key in ("from", "to"):
            target.setdefault(key, copy.deepcopy(value))
        elif key == "lastSeen":
            target[key] = merge_text_max(target.get(key, ""), value)
        elif isinstance(value, (int, float)):
            target[key] = target.get(key, 0) + value
        elif key not in target:
            target[key] = copy.deepcopy(value)
    v2.ensure_running_counters(target)


def merge_topologies(topologies: list[dict]) -> dict:
    merged = v2.empty_cached_topology()
    for topology in topologies:
        for key, node in topology.get("nodes", {}).items():
            if key not in merged["nodes"]:
                merged["nodes"][key] = copy.deepcopy(node)
            else:
                merge_node(merged["nodes"][key], node)
        for key, edge in topology.get("edges", {}).items():
            if key not in merged["edges"]:
                merged["edges"][key] = copy.deepcopy(edge)
                v2.ensure_running_counters(merged["edges"][key])
            else:
                merge_edge(merged["edges"][key], edge)
        merged["failureTiles"].extend(copy.deepcopy(topology.get("failureTiles", [])))
        merged["deathTiles"].extend(copy.deepcopy(topology.get("deathTiles", [])))
        merged["deathIncidents"].extend(copy.deepcopy(v2.topology_death_incidents(topology)))
        merged["traceIds"].update(topology.get("traceIds", set()))
        merged["sourcePaths"].update(topology.get("sourcePaths", set()))
        merged["totalRecords"] += int(topology.get("totalRecords", 0))
        merged["includedRecords"] += int(topology.get("includedRecords", 0))
        merged["skippedRecords"] += int(topology.get("skippedRecords", 0))
    return merged


def aggregate_profile_stats(profile_stats: list[dict]) -> dict:
    adventure = v2.empty_adventure_stats()
    adventure["_loot"] = {}
    play_seconds = 0
    play_records = 0
    total_level = 0
    bank_value = 0
    damage_dealt = 0
    for stats in profile_stats:
        profile_adventure = stats.get("adventureStats", {})
        v2.merge_adventure_stats(adventure, profile_adventure)
        bank_value += int(profile_adventure.get("bankValue", 0))
        damage_dealt += int(profile_adventure.get("damageDealt", 0))
        play_seconds += int(stats.get("playSeconds", 0))
        play_records += int(stats.get("playTraceRecords", 0))
        total_level += int(stats.get("totalLevel", 0))
    adventure = v2.finalize_adventure_stats(adventure)
    adventure["bankValue"] = bank_value
    adventure["damageDealt"] = damage_dealt
    return {
        "profile": "all-players",
        "skills": [],
        "totalLevel": total_level,
        "hoursPlayed": v2.format_hours(play_seconds),
        "playSeconds": play_seconds,
        "playTraceRecords": play_records,
        "adventureStats": adventure,
    }


def skill_level(stats: dict, name: str) -> int:
    expected = name.lower()
    for skill in stats.get("skills", []):
        if str(skill.get("name", "")).lower() == expected:
            return int(skill.get("baseLevel", skill.get("currentLevel", 1)))
    return 1


def skill_xp(stats: dict, name: str) -> int:
    expected = name.lower()
    for skill in stats.get("skills", []):
        if str(skill.get("name", "")).lower() == expected:
            return int(skill.get("xp", 0))
    return 0


def fun_stats(profile_stats: list[dict]) -> dict:
    fishing_xp = sum(skill_xp(stats, "fishing") for stats in profile_stats)
    mining_xp = sum(skill_xp(stats, "mining") for stats in profile_stats)
    woodcutting_xp = sum(skill_xp(stats, "woodcutting") for stats in profile_stats)
    cow_mentions = sum(int(profile_memory_state(stats.get("profile", "")).get("cowMentions", 0)) for stats in profile_stats)
    kills = sum(int((stats.get("adventureStats") or {}).get("killsEstimated", 0)) for stats in profile_stats)
    return {
        "fishCaughtEstimated": int(round(fishing_xp / 80.0)),
        "rocksMinedEstimated": int(round(mining_xp / 35.0)),
        "forestsMeltedEstimated": int(round(woodcutting_xp / 25.0)),
        "cowsBothered": cow_mentions,
        "enemiesKilledEstimated": kills,
    }


def fun_stats_line(stats: dict) -> str:
    return (
        "FISH EST %s   ROCKS EST %s   FORESTS MELTED EST %s   COWS BOTHERED %s   KILLS EST %s"
        % (
            v2.format_compact_int(stats.get("fishCaughtEstimated", 0)),
            v2.format_compact_int(stats.get("rocksMinedEstimated", 0)),
            v2.format_compact_int(stats.get("forestsMeltedEstimated", 0)),
            v2.format_compact_int(stats.get("cowsBothered", 0)),
            v2.format_compact_int(stats.get("enemiesKilledEstimated", 0)),
        )
    )


def level_row(stats: dict) -> str:
    level_bits = ["%s %02d" % (short, skill_level(stats, name)) for name, short in LEVEL_SKILLS]
    return "TOTAL %-3d  HRS %-5s  %s" % (
        int(stats.get("totalLevel", 0)),
        str(stats.get("hoursPlayed", "0H")),
        "  ".join(level_bits),
    )


def project_tile(tile: dict, render_info: dict) -> tuple[int, int]:
    bounds = render_info["bounds"]
    width = int(render_info["pixelWidth"])
    height = int(render_info["pixelHeight"])
    title_h = int(render_info.get("titleHeight", 150))
    map_h = height - title_h - v2.FOOTER_HEIGHT
    scale = float(render_info["pixelsPerTile"])
    span_x = bounds["maxX"] - bounds["minX"] + 1
    map_w = int(math.ceil(span_x * scale)) + 1
    map_x0 = (width - map_w) // 2
    x = int(round(map_x0 + (int(tile["x"]) - bounds["minX"]) * scale))
    y = int(round(title_h + map_h - 1 - (int(tile["y"]) - bounds["minY"]) * scale))
    return x, y


def color_hex(color: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % color


def overlay_all_player_panel(
    output: Path,
    render_info: dict,
    profile_stats: list[dict],
    latest_tiles: dict[str, dict],
    ledger: dict,
) -> bool:
    magick = shutil.which("magick")
    if not magick or not v2.RUNESCAPE_FONT.exists():
        return False

    width = int(render_info["pixelWidth"])
    title_h = int(render_info.get("titleHeight", 220))
    command = [
        magick,
        str(output),
        "+antialias",
        "-font", str(v2.RUNESCAPE_FONT),
        "-fill", color_hex(v2.PALETTE["paper2"]),
        "-draw", "rectangle 0,0 %d,%d" % (width, title_h),
        "-stroke", color_hex(v2.PALETTE["frame"]),
        "-strokewidth", "2",
        "-draw", "line 28,%d %d,%d" % (title_h - 12, width - 28, title_h - 12),
        "-stroke", "none",
    ]

    left_center = min(270, max(190, width // 5))
    v2.add_center_shadow_text(command, left_center, 82, 68, "All Players Fog", v2.PALETTE["osrs_yellow"])
    v2.add_center_shadow_text(
        command,
        left_center,
        126,
        23,
        "%d accounts  combined exploration coverage" % len(profile_stats),
        v2.PALETTE["muted"],
    )
    v2.add_center_shadow_text(
        command,
        left_center,
        158,
        23,
        "squad total %s levels" % v2.format_int(sum(int(stats.get("totalLevel", 0)) for stats in profile_stats)),
        v2.PALETTE["muted"],
    )
    v2.add_shadow_text(command, 34, title_h - 30, 25, fun_stats_line(ledger), v2.PALETTE["muted"])

    table_x = max(620, int(width * 0.19))
    row_y = 43
    row_gap = 42
    for index, stats in enumerate(profile_stats):
        color = PROFILE_COLORS[index % len(PROFILE_COLORS)]
        y = row_y + index * row_gap
        name = display_profile(stats.get("profile", ""))
        v2.add_outline_text(command, table_x, y, 30, name, color, 2)
        v2.add_shadow_text(command, table_x + 185, y, 26, level_row(stats), v2.PALETTE["osrs_yellow"])

    for index, stats in enumerate(profile_stats):
        profile = str(stats.get("profile") or "")
        tile = latest_tiles.get(profile)
        if not tile:
            continue
        color = PROFILE_COLORS[index % len(PROFILE_COLORS)]
        x, y = project_tile(tile, render_info)
        command.extend([
            "-fill", "none",
            "-stroke", color_hex(v2.PALETTE["text_shadow"]),
            "-strokewidth", "8",
            "-draw", "circle %d,%d %d,%d" % (x, y, x + 21, y),
            "-stroke", color_hex(color),
            "-strokewidth", "6",
            "-draw", "circle %d,%d %d,%d" % (x, y, x + 21, y),
            "-fill", color_hex(color),
            "-stroke", "none",
            "-draw", "circle %d,%d %d,%d" % (x, y, x + 6, y),
        ])
        v2.add_outline_text(command, x + 27, y - 9, 24, display_profile(profile), color, 2)

    footer_top = int(render_info["pixelHeight"]) - v2.FOOTER_HEIGHT
    legend_text_x = 94 + 270
    legend_text_y = footer_top + v2.FOOTER_ITEM_TEXT_Y + 2 * v2.FOOTER_ROW_GAP
    command.extend([
        "-fill", color_hex(v2.PALETTE["paper2"]),
        "-draw", "rectangle %d,%d %d,%d" % (
            legend_text_x - 6,
            legend_text_y - 31,
            legend_text_x + 178,
            legend_text_y + 9,
        ),
    ])
    v2.add_shadow_text(command, legend_text_x, legend_text_y, 28, "PLAYERS", v2.PALETTE["osrs_yellow"])

    command.append(str(output))
    subprocess.run(command, check=True)
    return True


def update_summary(
    summary_path: Path,
    profile_stats: list[dict],
    render_info: dict,
    overlay_applied: bool,
    ledger: dict,
) -> dict:
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    data.update({
        "mapVersion": "All Players Fog",
        "profiles": [
            {
                "profile": stats.get("profile"),
                "displayName": display_profile(stats.get("profile", "")),
                "totalLevel": stats.get("totalLevel"),
                "hoursPlayed": stats.get("hoursPlayed"),
                "levels": {
                    short: skill_level(stats, name)
                    for name, short in LEVEL_SKILLS
                },
            }
            for stats in profile_stats
        ],
        "funStats": ledger,
        "allPlayersTitleOverlay": overlay_applied,
        "titleHeight": render_info.get("titleHeight", data.get("titleHeight")),
    })
    summary_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render one combined fog map for every local player profile.")
    parser.add_argument("--profile", action="append",
                        help="Profile to include. May be repeated; defaults to every character/trace profile.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--coverage-cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--no-coverage-cache", action="store_true")
    parser.add_argument("--no-topology-cache", action="store_true")
    parser.add_argument("--pixels-per-tile", type=float, default=4.0)
    parser.add_argument("--max-map-pixels", type=int, default=3200)
    parser.add_argument("--padding-tiles", type=int, default=20)
    parser.add_argument("--fog-radius-tiles", type=float, default=28.0)
    parser.add_argument("--fog-alpha", type=float, default=0.72)
    return parser.parse_args()


def main() -> int:
    parsed = parse_args()
    profiles = parsed.profile or discover_profiles()
    if not profiles:
        raise SystemExit("no player profiles found")

    parsed.output = parsed.output.resolve()
    parsed.summary = parsed.summary.resolve()
    parsed.coverage_cache_dir = parsed.coverage_cache_dir.resolve()
    parsed.output.parent.mkdir(parents=True, exist_ok=True)
    parsed.summary.parent.mkdir(parents=True, exist_ok=True)
    parsed.coverage_cache_dir.mkdir(parents=True, exist_ok=True)

    profile_topologies = []
    profile_stats = []
    latest_tiles = {}
    for profile in profiles:
        topology = load_profile_topology(profile, parsed)
        profile_topologies.append(topology)
        stats = v2.load_profile_stats(profile)
        stats["profile"] = profile
        profile_stats.append(stats)
        latest = v2.latest_node(topology.get("nodes", {}))
        if latest:
            latest_tiles[profile] = latest["tile"]

    combined = merge_topologies(profile_topologies)
    render_args = build_args(parsed, trace_profile="")
    aggregate_stats = aggregate_profile_stats(profile_stats)
    ledger = fun_stats(profile_stats)

    original_load_profile_stats = v2.load_profile_stats
    original_latest_node = v2.latest_node
    try:
        v2.load_profile_stats = lambda _profile: aggregate_stats
        v2.latest_node = lambda _nodes: None
        render_info = v2.render(combined, render_args)
    finally:
        v2.load_profile_stats = original_load_profile_stats
        v2.latest_node = original_latest_node

    v2.write_summary(parsed.summary, combined, render_info, parsed.output, render_args)
    overlay_applied = overlay_all_player_panel(parsed.output, render_info, profile_stats, latest_tiles, ledger)
    summary = update_summary(parsed.summary, profile_stats, render_info, overlay_applied, ledger)
    print(json.dumps({
        "success": True,
        "output": str(parsed.output),
        "summary": str(parsed.summary),
        "profiles": [stats["profile"] for stats in profile_stats],
        "records": summary.get("records"),
        "nodes": summary.get("nodes"),
        "edges": summary.get("edges"),
        "deaths": summary.get("deaths"),
        "uniqueDeathSites": summary.get("uniqueDeathSites"),
        "overlay": overlay_applied,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
