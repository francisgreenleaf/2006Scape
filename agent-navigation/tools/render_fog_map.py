#!/usr/bin/env python3
"""Render the active profile fog movement topology."""

from pathlib import Path
import os

import render_movement_topology_v2 as v2


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "topology"
SUMMARY_OUT = ROOT / ".local" / "map-summaries"


def profile_title():
    value = os.environ.get("RS_TRACE_PROFILE") or os.environ.get("RS_PROFILE") or ""
    normalized = "".join(ch for ch in value.lower() if ch.isalnum())
    if not value or normalized == "mrflame":
        value = "Mrflame"
    return value


if __name__ == "__main__":
    title = profile_title()
    v2.main(
        default_output=OUT / "movement-topology-v6.png",
        default_summary=SUMMARY_OUT / "movement-topology-v6.json",
        default_map_version=title + " Fog",
        default_title_text=title,
        default_title_stats_panel=True,
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
        default_tighten_east_south_bounds=True,
        default_include_historical_agent_batch_traces=True,
    )
