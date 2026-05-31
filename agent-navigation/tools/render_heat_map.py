#!/usr/bin/env python3
"""Render the active Heat Map movement topology."""

import render_movement_topology_v2 as v2
from profile_utils import canonical_map_paths, profile_display_name, profile_from_argv


if __name__ == "__main__":
    profile = profile_from_argv(trace=True, default="")
    output, summary = canonical_map_paths(profile, "heat")
    v2.main(
        default_output=output,
        default_summary=summary,
        default_map_version="Heat Map",
        default_title_text=profile_display_name(profile, default_text="Mrflame"),
        default_title_stats_panel=True,
        default_meta_pointsize=23,
        default_show_pois=True,
        default_poi_mode="all",
        default_poi_icon_scale=1.0,
        default_running_overlay=True,
        default_coverage_heatmap=True,
        default_coverage_heat_alpha=0.42,
        default_coverage_heat_high_percentile=0.985,
        default_coverage_heat_gamma=1.45,
        default_tighten_east_south_bounds=True,
        default_include_historical_agent_batch_traces=True,
    )
