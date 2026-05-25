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
        return "Mr. Flame"
    return value


if __name__ == "__main__":
    title = profile_title()
    v2.main(
        default_output=OUT / "movement-topology-v4.png",
        default_summary=SUMMARY_OUT / "movement-topology-v4.json",
        default_map_version=title,
        default_title_text=title,
        default_show_pois=True,
        default_poi_mode="all",
        default_poi_icon_scale=1.0,
        default_running_overlay=True,
        default_include_historical_agent_batch_traces=True,
    )
