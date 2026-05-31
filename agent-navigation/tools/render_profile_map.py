#!/usr/bin/env python3
"""Render the active profile movement map."""

import render_movement_topology_v2 as v2
from profile_utils import canonical_map_paths, profile_display_name, profile_from_argv


def profile_title():
    return profile_display_name(profile_from_argv(trace=True, default=""), default_text="Mrflame")


if __name__ == "__main__":
    profile = profile_from_argv(trace=True, default="")
    title = profile_title()
    output, summary = canonical_map_paths(profile, "profile")
    v2.main(
        default_output=output,
        default_summary=summary,
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
