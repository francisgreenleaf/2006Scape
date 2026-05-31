#!/usr/bin/env python3
"""Render the active profile movement map with running-route tinting.

This keeps cache icons and place-label defaults, then adds a subtle route color
shift where movement traces show actual or inferred running.
"""

import render_movement_topology_v2 as v2
from profile_utils import canonical_map_paths, profile_display_name, profile_from_argv


def profile_title():
    return profile_display_name(profile_from_argv(trace=True, default=""), default_text="Mr. Flame")


if __name__ == "__main__":
    profile = profile_from_argv(trace=True, default="")
    title = profile_title()
    output, summary = canonical_map_paths(profile, "profile")
    v2.main(
        default_output=output,
        default_summary=summary,
        default_map_version=title,
        default_title_text=title,
        default_show_pois=True,
        default_poi_mode="all",
        default_poi_icon_scale=1.0,
        default_running_overlay=True,
    )
