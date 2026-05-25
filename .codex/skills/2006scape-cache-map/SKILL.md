---
name: 2006scape-cache-map
description: Use when working in the /Users/kevin/Documents/2006Scape repo on the cache-backed world map, GameCache/minimap-style renderer, active movement maps (profile map, Heat Map, profile fog), terrain/water/object/mapscene rendering, or documentation/export of map data for other applications. Trigger for tasks involving agent-navigation/tools/cache_world_map.py, render_profile_map.py, render_heat_map.py, render_fog_map.py, cache-world-map artifacts, active movement topology PNG outputs, missing map layers such as water/buildings/objects, or replacing the retired screenshot/minimap fog workflow.
---

# 2006Scape Cache Map

Use this skill for the static cache-backed map system in `/Users/kevin/Documents/2006Scape`.

## Core Rule

Use the cache renderer as the source of static world context. Do not restart or recreate the old screenshot-based minimap fog collector, background focus sampler, or any workflow that periodically brings the Java client window forward.

## Main Files

- `agent-navigation/tools/cache_world_map.py`: cache decoder and minimap-style world-map renderer.
- `agent-navigation/tools/render_agent_context_map.py`: fast agent-facing bounded cache-map wrapper for current location and route-segment debugging, including all cache mapfunction icons in bounds and machine-readable marker labels.
- `agent-navigation/tools/render_context_map.py`: lower-level bounded lossless cache-map window around a tile/place/latest trace, with optional recent-path or segment overlay.
- `agent-navigation/tools/render_movement_topology_v2.py`: shared movement topology render engine used by the active maps. It preserves exact full-resolution output with quantized bounds, direct byte-level overlay loops, cached static base canvases, cached topology prefixes, cached full-resolution heat/fog coverage masks, and spatial-indexed fog-hidden POI checks.
- `agent-navigation/tools/render_profile_map.py`: active `Mr. Flame` profile movement map with cache icons, labels, and run-tinted routes.
- `agent-navigation/tools/render_heat_map.py`: active `Heat Map` with transparent trace-coverage density for route-learning/ML inspection.
- `agent-navigation/tools/render_fog_map.py`: active `Mr. Flame Fog` profile fog map with route/icon overlays and a fog-of-war mask.
- `agent-navigation/tools/active_map_refresher.py`: preferred background controller for continuously keeping active user-facing map exports current. Use `start`, `status`, `logs`, `stop`, and `restart` here instead of hand-launching a detached process.
- `agent-navigation/tools/refresh_active_maps.py`: lower-level foreground worker used by `active_map_refresher.py`. It runs the profile map, `Heat Map`, and profile fog in independent loops by default, writes ignored status/temp files under `agent-navigation/.local/map-refresh/`, writes summaries under `agent-navigation/.local/map-summaries/`, uses per-map cache subdirectories under `agent-navigation/.local/topology-render-cache/` to avoid concurrent cache-write collisions, passes trace-profile filters through to movement renderers, and only refreshes the static full cache map under `.local` when explicitly requested.
- Legacy versioned movement-topology scripts may exist for old experiments or compatibility; leave them on disk, but use the plain-name scripts above for current maps. Old one-off PNG/JSON exports should not be kept in `agent-navigation/topology/`.
- `agent-navigation/.local/context-maps/<date>/*.png`: ignored, timestamped bounded context-map artifacts for agent routing/debugging.
- `agent-navigation/.local/context-maps/<date>/*.json`: matching context-map summaries with bounds, center, mapfunction markers, and place markers.
- `agent-navigation/topology/movement-topology-v4.png`: active profile movement map.
- `agent-navigation/topology/movement-topology-v5-heatmap.png`: active `Heat Map` with run tinting and transparent coverage density.
- `agent-navigation/topology/movement-topology-v6.png`: active profile fog map with unvisited map areas dimmed.
- `agent-navigation/.local/map-summaries/*.json`: ignored metadata summaries for active maps, cache-map renders, and route overview renders.
- `agent-navigation/cache-world-map.md`: repo-facing documentation, if present.

Read `references/cache-world-map.md` when the task asks how the map works, how to reuse it, what data it reads, why water/buildings appear, or how to improve/share the renderer.

## Render Commands

From the repo root, render the canonical full cache map:

```sh
agent-navigation/tools/cache_world_map.py \
  --output agent-navigation/.local/map-summaries/cache-world-map.png \
  --summary agent-navigation/.local/map-summaries/cache-world-map.json
```

Render a small current-location agent context map instead of loading the full world:

```sh
python3 agent-navigation/tools/render_agent_context_map.py --center latest
```

Use `render_agent_context_map.py` for live agent routing and route debugging. It caps trace records, bounds the output, draws every cache `mapfunction` icon in bounds, adds simple place labels, and writes unique ignored artifacts under `agent-navigation/.local/context-maps/<date>/` by default. Filenames include timestamp, mode, resolved center tile, radius, and pixel scale so Router/debug renders do not overwrite each other. The JSON includes `mapFunctionMarkers`, `placeMarkers`, and artifact metadata for machine-readable context. Segment maps default to enough padding/max span to keep nearby route geometry such as Port Sarim dock planks visible without rendering the full world. Use integer `--pixels-per-tile` values for lossless, pixel-perfect map windows. Increase `--radius-tiles` for more context or lower `--pixels-per-tile` for a smaller image; do not render the full world when a bounded window answers the question. Use explicit `--output`/`--summary` only when a stable path is intentionally needed.

Render the active profile movement map:

```sh
agent-navigation/tools/render_profile_map.py
```

Render the active `Heat Map`:

```sh
agent-navigation/tools/render_heat_map.py
```

Render the active profile fog map:

```sh
agent-navigation/tools/render_fog_map.py
```

Use the profile movement map for the main human-facing movement view, `Heat Map` for trace-coverage density, and the profile fog map for fog-of-war coverage. Agents should not run these full topology renders during live routing unless explicitly asked. All active movement maps read the latest unified movement traces at render time, and the plain-name wrappers backfill historical agent-batch traces recorded before passive player tracing began so early exploration/deaths are not lost while newer duplicated batches stay omitted. They draw cache `mapfunction` icons in bounds, cluster death events into death sites, and filter non-local respawn/teleport edges so they do not appear as route or combat lines. The fog map hides cache POI icons outside the explored POI radius, which should stay close to the visible fog reveal.

Coverage rendering must preserve full-resolution output quality. Do not speed it up by lowering the coverage mask resolution unless the user explicitly accepts a visual approximation. The shared renderer has exact radial-kernel caches, an append-validated topology prefix cache, a static base-map canvas cache, a POI list cache, exact full-resolution heat and fog coverage caches, direct byte-level drawing/downsampling, and spatial-indexed POI fog checks. By default these persistent caches live under ignored `agent-navigation/.local/topology-render-cache`; use `--no-topology-cache` or `--no-coverage-cache` only when testing a cold render or debugging cache behavior. Check the summary `cache` block plus `coverageHeatCache`/`coverageFogCache`, cached node counts, and rendered node counts when verifying coverage-cache behavior.

The optimized heat mask is applied as a single full-map pass. It uses cached full-resolution radial kernels with a non-saturating max mask so high-coverage areas do not make every explored corridor look dense. Check the heat summary fields and inspect the PNG if low/high coverage stops separating.

To keep canonical active exports current in the background without babysitting renders, use the dedicated controller:

```sh
agent-navigation/tools/active_map_refresher.py start
agent-navigation/tools/active_map_refresher.py status
agent-navigation/tools/active_map_refresher.py logs --lines 40
```

Default behavior is one worker per active map. The `mr-flame` profile movement map is a continuous hot loop: as soon as one render finishes, the next render starts. `Heat Map` and profile fog use the 30-second target cadence. A worker never overlaps the same map; if a non-hot render takes longer than 30 seconds, the next pass starts immediately after it finishes. The worker renders to ignored temp files first and atomically replaces only the three canonical topology PNGs on success; JSON summaries stay under `.local/map-summaries/`. Check progress through `active_map_refresher.py status`, `active_map_refresher.py logs`, or `agent-navigation/.local/map-refresh/status.json`. Use `active_map_refresher.py restart --only mr-flame` for only the profile map, `--trace-profile mrflame` for profile-specific traces, `--include-unscoped-traces` when legacy unscoped records should remain visible, and `--serial` to reduce CPU pressure. Use `refresh_active_maps.py --once ...` directly only for one-shot validation or renderer debugging.

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
python3 -m py_compile agent-navigation/tools/cache_world_map.py agent-navigation/tools/render_context_map.py agent-navigation/tools/render_agent_context_map.py agent-navigation/tools/render_movement_topology_v2.py agent-navigation/tools/render_profile_map.py agent-navigation/tools/render_heat_map.py agent-navigation/tools/render_fog_map.py
python3 -m py_compile agent-navigation/tools/active_map_refresher.py agent-navigation/tools/refresh_active_maps.py
agent-navigation/tools/cache_world_map.py --bounds 3200,3200,3210,3210 --output /tmp/2006scape-cache-map-smoke.png --summary /tmp/2006scape-cache-map-smoke.json
python3 agent-navigation/tools/render_agent_context_map.py --center 3205,3205,0 --radius-tiles 12 --recent-seconds 0 --output /tmp/2006scape-agent-context-map-smoke.png --summary /tmp/2006scape-agent-context-map-smoke.json
agent-navigation/tools/refresh_active_maps.py --once --only heat-map
agent-navigation/tools/active_map_refresher.py status
```

If changing topology integration, also run the affected active movement topology renderer: `agent-navigation/tools/render_profile_map.py`, `agent-navigation/tools/render_heat_map.py`, or `agent-navigation/tools/render_fog_map.py`.
