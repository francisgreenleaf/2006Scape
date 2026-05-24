#!/usr/bin/env python3
"""Render the active profile movement map with running-route tinting.

This keeps cache icons and place-label defaults, then adds a subtle route color
shift where movement traces show actual or inferred running.
"""

from pathlib import Path
import os

import render_movement_topology_v2 as v2


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "topology"


def profile_title():
    return os.environ.get("RS_TRACE_PROFILE") or os.environ.get("RS_PROFILE") or "Mr. Flame"


if __name__ == "__main__":
    title = profile_title()
    v2.main(
        default_output=OUT / "movement-topology-v4.png",
        default_summary=OUT / "movement-topology-v4.json",
        default_map_version=title,
        default_title_text=title,
        default_show_pois=True,
        default_poi_mode="all",
        default_poi_icon_scale=1.0,
        default_running_overlay=True,
    )
