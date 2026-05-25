#!/usr/bin/env python3
"""Render the active Heat Map movement topology."""

from pathlib import Path

import render_movement_topology_v2 as v2


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "topology"
SUMMARY_OUT = ROOT / ".local" / "map-summaries"
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
    "mechanics. The heat marks where evidence is strongest and where the graph "
    "still needs coverage."
)


if __name__ == "__main__":
    v2.main(
        default_output=OUT / "movement-topology-v5-heatmap.png",
        default_summary=SUMMARY_OUT / "movement-topology-v5-heatmap.json",
        default_map_version="Heat Map",
        default_title_text="Heat Map",
        default_title_paragraph=TITLE_PARAGRAPH,
        default_title_paragraph_x=520,
        default_title_paragraph_y=104,
        default_title_paragraph_lines=8,
        default_title_paragraph_align="right",
        default_title_paragraph_right_margin=34,
        default_title_paragraph_char_factor=0.34,
        default_meta_pointsize=23,
        default_show_pois=True,
        default_poi_mode="all",
        default_poi_icon_scale=1.0,
        default_running_overlay=True,
        default_coverage_heatmap=True,
        default_coverage_heat_alpha=0.38,
        default_coverage_heat_high_percentile=0.94,
        default_coverage_heat_gamma=0.90,
        default_include_historical_agent_batch_traces=True,
    )
