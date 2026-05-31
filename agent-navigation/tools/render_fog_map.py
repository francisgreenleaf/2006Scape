#!/usr/bin/env python3
"""Render the active profile fog movement topology."""

import render_movement_topology_v2 as v2
from profile_utils import canonical_map_paths, profile_display_name, profile_from_argv


def profile_title():
    return profile_display_name(profile_from_argv(trace=True, default=""), default_text="Mrflame")


if __name__ == "__main__":
    profile = profile_from_argv(trace=True, default="")
    title = profile_title()
    output, summary = canonical_map_paths(profile, "fog")
    v2.main(
        default_output=output,
        default_summary=summary,
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
