#!/usr/bin/env python3
"""Render the active profile movement map."""

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
        return "Mrflame"
    return value


if __name__ == "__main__":
    title = profile_title()
    v2.main(
        default_output=OUT / "movement-topology-v4.png",
        default_summary=SUMMARY_OUT / "movement-topology-v4.json",
        default_map_version=title,
        default_title_text=title,
        default_title_stats_panel=True,
        default_show_pois=True,
        default_poi_mode="all",
        default_poi_icon_scale=1.0,
        default_running_overlay=True,
        default_reference_grid=True,
        default_reference_grid_origin="level0",
        default_reference_grid_row_origin="south",
        default_reference_grid_cell_tiles=32.0,
        default_reference_grid_alpha=0.18,
        default_reference_grid_major_alpha=0.28,
        default_reference_grid_major_every=4,
        default_reference_grid_label_alpha=0.86,
        default_reference_grid_label_pointsize=24,
        default_reference_grid_cell_labels="all",
        default_reference_grid_cell_label_alpha=0.55,
        default_reference_grid_cell_label_pointsize=13,
        default_tighten_east_south_bounds=True,
        default_include_historical_agent_batch_traces=True,
    )
