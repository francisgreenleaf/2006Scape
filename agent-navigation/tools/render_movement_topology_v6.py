#!/usr/bin/env python3
"""Render the active profile fog movement topology."""

import render_movement_topology_v2 as v2
from profile_utils import canonical_map_paths, profile_display_name, profile_from_argv


TITLE_PARAGRAPH = (
    "The selected profile is building an evidence-backed navigation graph for Gielinor from "
    "passive player traces, bridge batch traces, curated places, route memory, "
    "hazards, shops, banks, stalls, combat contact, and death sites. Each movement "
    "edge carries attempts, successes, failures, ticks, run ticks, energy spent, "
    "HP lost, combat ticks, trace IDs, and recency; clean short movements can "
    "infer reverse edges, while deaths and blocked targets become negative "
    "evidence. The router builds a hybrid graph from trace edges and verified "
    "route DB segments, applies hazard and failure penalties, then uses "
    "deterministic Dijkstra search to choose safe, explainable waypoints. GPT-5.5 "
    "plans over that graph, route_runner preflights batches through the server's "
    "clipped PathFinder, and the ML layer is being built to score edge cost, risk, "
    "confidence, shortcut value, and frontier priority without bypassing game "
    "mechanics. The fog marks what the graph has not proven yet."
)


def profile_title():
    return profile_display_name(profile_from_argv(trace=True, default=""), default_text="Mr. Flame")


if __name__ == "__main__":
    profile = profile_from_argv(trace=True, default="")
    title = profile_title()
    output, summary = canonical_map_paths(profile, "fog")
    v2.main(
        default_output=output,
        default_summary=summary,
        default_map_version="Profile Fog",
        default_title_text=title,
        default_title_paragraph=TITLE_PARAGRAPH,
        default_title_paragraph_x=500,
        default_title_paragraph_y=28,
        default_title_paragraph_lines=8,
        default_title_paragraph_align="right",
        default_title_paragraph_right_margin=34,
        default_title_paragraph_char_factor=0.34,
        default_meta_pointsize=23,
        default_show_pois=True,
        default_poi_mode="all",
        default_poi_icon_scale=1.0,
        default_running_overlay=True,
        default_coverage_fog=True,
        default_coverage_fog_alpha=0.72,
        default_coverage_fog_radius_tiles=28.0,
        default_coverage_fog_poi_extra_tiles=4.0,
        default_hide_fogged_pois=True,
    )
