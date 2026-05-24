---
name: 2006scape-cache-map
description: Use when working in the /Users/kevin/Documents/2006Scape repo on the cache-backed world map, GameCache/minimap-style renderer, active movement maps (profile map, Heat Map, profile fog), terrain/water/object/mapscene rendering, or documentation/export of map data for other applications. Trigger for tasks involving agent-navigation/tools/cache_world_map.py, render_movement_topology_v4.py, render_movement_topology_v5.py, render_movement_topology_v6.py, cache-world-map.png/json, active movement topology PNG/JSON outputs, missing map layers such as water/buildings/objects, or replacing the retired screenshot/minimap fog workflow.
---

# 2006Scape Cache Map

Use this skill for the static cache-backed map system in `/Users/kevin/Documents/2006Scape`.

## Core Rule

Use the cache renderer as the source of static world context. Do not restart or recreate the old screenshot-based minimap fog collector, background focus sampler, or any workflow that periodically brings the Java client window forward.

## Main Files

- `agent-navigation/tools/cache_world_map.py`: cache decoder and minimap-style world-map renderer.
- `agent-navigation/tools/render_agent_context_map.py`: fast agent-facing bounded cache-map wrapper for current location and route-segment debugging, including all cache mapfunction icons in bounds and machine-readable marker labels.
- `agent-navigation/tools/render_context_map.py`: lower-level bounded lossless cache-map window around a tile/place/latest trace, with optional recent-path or segment overlay.
- `agent-navigation/tools/render_movement_topology_v2.py`: shared movement topology render engine used by the active maps.
- `agent-navigation/tools/render_movement_topology_v4.py`: active profile movement map with cache icons, labels, and run-tinted routes.
- `agent-navigation/tools/render_movement_topology_v5.py`: active `Heat Map` with transparent trace-coverage density for route-learning/ML inspection.
- `agent-navigation/tools/render_movement_topology_v6.py`: active profile fog map with route/icon overlays and a fog-of-war mask.
- `agent-navigation/tools/refresh_active_maps.py`: continuous refresher for active user-facing map exports. It runs `surface-routes`, the profile map, `Heat Map`, and profile fog in independent loops by default, writes ignored status/temp files under `agent-navigation/.local/map-refresh/`, uses per-map cache subdirectories under `agent-navigation/.local/topology-render-cache/` to avoid concurrent cache-write collisions, passes trace-profile filters through to movement renderers, and only refreshes the static full cache map when missing or explicitly requested.
- Legacy movement-topology scripts may exist for old experiments; leave scripts on disk, but do not use or document them as current maps. Old one-off PNG/JSON exports should not be kept in `agent-navigation/topology/`.
- `agent-navigation/topology/cache-world-map.png`: canonical full cache map image.
- `agent-navigation/topology/cache-world-map.json`: summary metadata for the full cache map.
- `agent-navigation/.local/context-maps/<date>/*.png`: ignored, timestamped bounded context-map artifacts for agent routing/debugging.
- `agent-navigation/.local/context-maps/<date>/*.json`: matching context-map summaries with bounds, center, mapfunction markers, and place markers.
- `agent-navigation/topology/movement-topology-v4.png`: active profile movement map.
- `agent-navigation/topology/movement-topology-v4.json`: active profile movement map metadata.
- `agent-navigation/topology/movement-topology-v5-heatmap.png`: active `Heat Map` with run tinting and transparent coverage density.
- `agent-navigation/topology/movement-topology-v5-heatmap.json`: active `Heat Map` metadata.
- `agent-navigation/topology/movement-topology-v6.png`: active profile fog map with unvisited map areas dimmed.
- `agent-navigation/topology/movement-topology-v6.json`: active profile fog metadata.
- `agent-navigation/cache-world-map.md`: repo-facing documentation, if present.

Read `references/cache-world-map.md` when the task asks how the map works, how to reuse it, what data it reads, why water/buildings appear, or how to improve/share the renderer.

## Render Commands

From the repo root, render the canonical full cache map:

```sh
agent-navigation/tools/cache_world_map.py \
  --output agent-navigation/topology/cache-world-map.png \
  --summary agent-navigation/topology/cache-world-map.json
```

Render a small current-location agent context map instead of loading the full world:

```sh
python3 agent-navigation/tools/render_agent_context_map.py --center latest
```

Use `render_agent_context_map.py` for live agent routing and route debugging. It caps trace records, bounds the output, draws every cache `mapfunction` icon in bounds, adds simple place labels, and writes unique ignored artifacts under `agent-navigation/.local/context-maps/<date>/` by default. Filenames include timestamp, mode, resolved center tile, radius, and pixel scale so Router/debug renders do not overwrite each other. The JSON includes `mapFunctionMarkers`, `placeMarkers`, and artifact metadata for machine-readable context. Segment maps default to enough padding/max span to keep nearby route geometry such as Port Sarim dock planks visible without rendering the full world. Use integer `--pixels-per-tile` values for lossless, pixel-perfect map windows. Increase `--radius-tiles` for more context or lower `--pixels-per-tile` for a smaller image; do not render the full world when a bounded window answers the question. Use explicit `--output`/`--summary` only when a stable path is intentionally needed.

Render the active profile movement map:

```sh
agent-navigation/tools/render_movement_topology_v4.py
```

Render the active `Heat Map`:

```sh
agent-navigation/tools/render_movement_topology_v5.py
```

Render the active profile fog map:

```sh
agent-navigation/tools/render_movement_topology_v6.py
```

Use the profile movement map for the main human-facing movement view, `Heat Map` for trace-coverage density, and the profile fog map for fog-of-war coverage. Agents should not run these full topology renders during live routing unless explicitly asked. All active movement maps read the latest unified movement traces at render time, draw cache `mapfunction` icons in bounds, cluster death events into death sites, and filter non-local respawn/teleport edges so they do not appear as route or combat lines. The fog map hides cache POI icons outside the explored POI radius, which should stay close to the visible fog reveal.

Coverage rendering must preserve full-resolution output quality. Do not speed it up by lowering the coverage mask resolution unless the user explicitly accepts a visual approximation. The shared renderer has exact radial-kernel caches, an append-validated topology prefix cache, a static base-map canvas cache, a POI list cache, an exact full-resolution fog reveal cache, direct-byte downsampling, and spatial-indexed POI fog checks. By default these persistent caches live under ignored `agent-navigation/.local/topology-render-cache`; use `--no-topology-cache` or `--no-coverage-cache` only when testing a cold render or debugging cache behavior. Check the summary `cache` block plus `coverageFogCache`, `coverageFogCachedNodes`, and `coverageFogRenderedNodes` in the fog summary when verifying cache behavior.

To keep canonical active exports current without babysitting renders, use:

```sh
agent-navigation/tools/refresh_active_maps.py
```

Default behavior is one worker per active map with a 30-second target cadence. A worker never overlaps the same map; if a render takes longer than 30 seconds, the next pass starts immediately after it finishes. The script renders to ignored temp files first and atomically replaces canonical PNG/JSON outputs only on success. Check progress in stdout or `agent-navigation/.local/map-refresh/status.json`. Use `--once` for a single refresh, `--only mr-flame` for the profile map, `--trace-profile mrflame` for profile-specific traces, `--include-unscoped-traces` when legacy unscoped records should remain visible, `--serial` to reduce CPU pressure, and `--refresh-world-map` only when the static cache map must be regenerated.

For quick checks, use small bounds:

```sh
agent-navigation/tools/cache_world_map.py \
  --bounds 3200,3200,3210,3210 \
  --output /tmp/2006scape-cache-map-smoke.png \
  --summary /tmp/2006scape-cache-map-smoke.json
```

## Editing Workflow

When changing map behavior:

1. Inspect the relevant client-side rendering reference before changing approximations:
   - `2006Scape Client/src/main/java/Game.java`
   - `2006Scape Client/src/main/java/ObjectManager.java`
   - `2006Scape Client/src/main/java/WorldController.java`
   - `2006Scape Client/src/main/java/ObjectDef.java`
2. Keep changes scoped to static map decoding/rendering unless the user asks for navigation or gameplay changes.
3. Preserve canonical output paths for full/player-facing maps. Context maps are agent artifacts and should default to ignored timestamped paths under `agent-navigation/.local/context-maps/` unless a stable path is explicitly requested.
4. Update `references/cache-world-map.md` and `agent-navigation/cache-world-map.md` when the workflow, layers, or outputs change.

## Validation

After renderer edits, run:

```sh
python3 -m py_compile agent-navigation/tools/cache_world_map.py agent-navigation/tools/render_context_map.py agent-navigation/tools/render_agent_context_map.py agent-navigation/tools/render_movement_topology_v2.py agent-navigation/tools/render_movement_topology_v4.py agent-navigation/tools/render_movement_topology_v5.py agent-navigation/tools/render_movement_topology_v6.py
python3 -m py_compile agent-navigation/tools/refresh_active_maps.py
agent-navigation/tools/cache_world_map.py --bounds 3200,3200,3210,3210 --output /tmp/2006scape-cache-map-smoke.png --summary /tmp/2006scape-cache-map-smoke.json
python3 agent-navigation/tools/render_agent_context_map.py --center 3205,3205,0 --radius-tiles 12 --recent-seconds 0 --output /tmp/2006scape-agent-context-map-smoke.png --summary /tmp/2006scape-agent-context-map-smoke.json
agent-navigation/tools/refresh_active_maps.py --once --only surface-routes
```

If changing topology integration, also run the affected active movement topology renderer: `agent-navigation/tools/render_movement_topology_v4.py`, `agent-navigation/tools/render_movement_topology_v5.py`, or `agent-navigation/tools/render_movement_topology_v6.py`.
