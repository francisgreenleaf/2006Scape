# Map Exports

This directory is for stable, user-facing map exports only.

Current canonical files:

- `cache-world-map.png` / `cache-world-map.json`: full cache-backed world map.
- `surface-routes.png`: route database overview.
- `movement-topology-v4.png` / `movement-topology-v4.json`: `Mr. Flame` main movement map.
- `movement-topology-v5-heatmap.png` / `movement-topology-v5-heatmap.json`: `Heat Map`.
- `movement-topology-v6.png` / `movement-topology-v6.json`: `Mr. Flame Fog`.

Agent context maps, shortcut proofs, temporary route crops, and comparison renders should not be written here by default. Use the context-map renderers' default ignored archive under `agent-navigation/.local/context-maps/<date>/`, or pass an explicit `/tmp/...` path for smoke tests.

To keep active exports current in the background while traces are being collected, run:

```sh
agent-navigation/tools/active_map_refresher.py start
agent-navigation/tools/active_map_refresher.py status
```

`active_map_refresher.py` manages the PID, log, status file, and restart behavior for the lower-level `refresh_active_maps.py` worker. It refreshes `surface-routes`, `Mr. Flame`, `Heat Map`, and `Mr. Flame Fog` on independent loops. `Mr. Flame` / V4 is a continuous hot loop that starts the next render immediately after the previous one finishes; the other active maps keep the normal cadence. The refresher uses ignored temp files for atomic replacement and records status under `agent-navigation/.local/map-refresh/status.json`. Parallel topology workers use per-map cache subdirectories under `agent-navigation/.local/topology-render-cache/`. The static `cache-world-map` is skipped unless missing or explicitly refreshed.
