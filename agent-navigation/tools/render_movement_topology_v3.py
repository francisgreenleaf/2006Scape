#!/usr/bin/env python3
"""Render V3 movement topology with cache minimap icons.

V3 intentionally reuses the V2 renderer and data semantics. The only default
visual additions are all cache-backed mapfunction icons and place labels.
"""

from pathlib import Path

import render_movement_topology_v2 as v2


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "topology"


if __name__ == "__main__":
    v2.main(
        default_output=OUT / "movement-topology-v3.png",
        default_summary=OUT / "movement-topology-v3.json",
        default_map_version="V3",
        default_show_pois=True,
        default_poi_mode="all",
        default_poi_icon_scale=1.0,
    )
