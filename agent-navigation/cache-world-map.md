# Cache-Backed World Map

This document explains the cache-backed world map used by the 2006Scape navigation harness. The map is generated from `2006Scape Server/data/cache`, not from screenshots or the live client window. It replaced the old visible-minimap sampling workflow, so it does not focus the Java client, steal macOS window focus, or depend on a logged-in player.

The main implementation is `agent-navigation/tools/cache_world_map.py`. The active movement maps use it through the shared topology engine in `agent-navigation/tools/render_movement_topology_v2.py`, with plain-name user-facing wrappers: `render_profile_map.py`, `render_heat_map.py`, and `render_fog_map.py`.

## Outputs

Canonical generated files:

```sh
agent-navigation/topology/cache-world-map-full.png
agent-navigation/topology/cache-world-map-level0.png
agent-navigation/topology/movement-topology-v4.png
agent-navigation/topology/movement-topology-v5-heatmap.png
agent-navigation/topology/movement-topology-v6.png
```

`cache-world-map-full.png` is the labeled full cache-bounds base export. `cache-world-map-level0.png` is the labeled level-0 surface export cropped to the main surface region. Both are 4 px/tile, north-up, generated without resizing, and contain no movement overlays. Other local scripts that need a static base map should use one of these files instead of sampling the Java client or generating their own ad hoc export.

Place labels for these base exports and the active topology maps come from the shared `agent-navigation/tools/map_labels.py` helper. It combines important town/hub labels from `agent-navigation/data/places.json` with curated static labels such as Port Sarim, Ice Mountain, and Edgeville, so Varrock and Barbarian Village stay consistent across the cache-world, profile, and heat-map renders.

`movement-topology-v4.png` is the active main movement map. `movement-topology-v5-heatmap.png` is the active `Heat Map`. `movement-topology-v6.png` is the active fog-of-war map. The movement PNG filenames are retained for compatibility; new code should use the plain-name scripts above instead of versioned renderer names. JSON summaries and route overview renders default to ignored paths under `agent-navigation/.local/map-summaries/` so `agent-navigation/topology/` stays limited to the reusable base-map exports and the three user-facing movement PNGs.

The active movement wrappers use passive player traces as the main evidence stream and backfill agent-batch traces only for the historical period before passive player tracing began. That keeps early exploration and death sites visible without reintroducing duplicate newer batch telemetry.

Agent context maps are disposable debug artifacts. By default, `render_agent_context_map.py` and `render_context_map.py` write unique ignored PNG/JSON pairs under `agent-navigation/.local/context-maps/<date>/`. Do not add stable `agent-context-map.*` or one-off shortcut/proof renders under `agent-navigation/topology/` unless the user explicitly asks for a shareable artifact.

Current cache-map summaries are written to `agent-navigation/.local/map-summaries/cache-world-map-full.json` and `agent-navigation/.local/map-summaries/cache-world-map-level0.json`. Use those summaries for exact bounds, pixel dimensions, region counts, tile counts, object counts, bridge-tile counts, and label metadata.

## How To Render

Render the full cache map:

```sh
agent-navigation/tools/cache_world_map.py \
  --output agent-navigation/.local/map-summaries/cache-world-map.png \
  --summary agent-navigation/.local/map-summaries/cache-world-map.json
```

Render the reusable labeled base-map exports:

```sh
agent-navigation/tools/cache_world_map.py \
  --bounds all \
  --pixels-per-tile 4 \
  --labels \
  --output agent-navigation/topology/cache-world-map-full.png \
  --summary agent-navigation/.local/map-summaries/cache-world-map-full.json

agent-navigation/tools/cache_world_map.py \
  --bounds 1728,2560,3839,4031 \
  --pixels-per-tile 4 \
  --labels \
  --output agent-navigation/topology/cache-world-map-level0.png \
  --summary agent-navigation/.local/map-summaries/cache-world-map-level0.json
```

Render a smaller bounded map:

```sh
agent-navigation/tools/cache_world_map.py \
  --bounds 2910,3149,3305,3567 \
  --pixels-per-tile 4 \
  --output /tmp/lumbridge-varrock.png \
  --summary /tmp/lumbridge-varrock.json
```

Render movement topology with the cache map as the background:

```sh
agent-navigation/tools/render_profile_map.py
```

Render the active analysis variants:

```sh
agent-navigation/tools/render_heat_map.py
agent-navigation/tools/render_fog_map.py
```

Use `--no-world-map` or `--world-map-source none` on an active wrapper when you only want the movement graph without terrain. Legacy versioned topology wrappers, direct V2 outputs, and old experiment scripts may remain on disk for comparison, but they are not current map products.

## Continuous Refresh

Use `active_map_refresher.py` when the active exports should stay current in the background while movement traces keep changing:

```sh
agent-navigation/tools/active_map_refresher.py start
agent-navigation/tools/active_map_refresher.py status
agent-navigation/tools/active_map_refresher.py logs --lines 40
agent-navigation/tools/active_map_refresher.py stop
```

`active_map_refresher.py` is the small background controller for the lower-level `refresh_active_maps.py` worker. By default it refreshes these canonical files in parallel worker loops:

- `agent-navigation/topology/movement-topology-v4.png`
- `agent-navigation/topology/movement-topology-v5-heatmap.png`
- `agent-navigation/topology/movement-topology-v6.png`

All three active map workers target a five-minute cadence. If a render takes longer than five minutes, that map starts its next pass immediately after the previous pass finishes; it never overlaps two renders for the same map. Auxiliary cache-map and route-overview renders are ignored `.local` artifacts, not topology exports.

The watcher renders to ignored temp files first, then atomically replaces the canonical PNG after a successful run and writes matching ignored summaries to `agent-navigation/.local/map-summaries/`. It prints start/done/failure lines and writes ignored status JSON to `agent-navigation/.local/map-refresh/status.json`, including the latest duration, records/nodes/edges/deaths, cache fields, and heat/fog coverage-cache fields when available. Parallel topology workers use separate persistent cache subdirectories under `agent-navigation/.local/topology-render-cache/` so their cache writes do not collide; each map still gets warm-cache behavior across its own repeats.

Movement map workers honor the same trace-profile filtering as the topology renderer. Use `--trace-profile <profile>` or set `RS_TRACE_PROFILE`/`RS_PROFILE` when you need one player/profile's traces only; add `--include-unscoped-traces` to keep legacy records with no player name.

Useful options:

```sh
agent-navigation/tools/active_map_refresher.py restart --only mr-flame --interval-seconds 300
agent-navigation/tools/active_map_refresher.py restart --serial
agent-navigation/tools/active_map_refresher.py restart --refresh-world-map
agent-navigation/tools/active_map_refresher.py restart --trace-profile mrflame
agent-navigation/tools/refresh_active_maps.py --once
```

## Cache Inputs

The renderer reads the same cache family the Java client reads:

- `main_file_cache.dat` and `main_file_cache.idx*`: low-level cache container files.
- archive `0,5`, entry `map_index`: region list and terrain/object file ids.
- archive `0,2`, entries `flo.dat`, `loc.dat`, and `loc.idx`: floor definitions and object definitions.
- archive `0,6`: texture sprites used to derive average texture colors.
- archive `0,4`, entries `mapscene.dat` and `index.dat`: mapscene background sprites.
- index `4` region files: compressed terrain and object payloads for each map region.

The code uses local cache decoding helpers only. It does not invoke the Java client or server.

## Render Pipeline

`load_cache_world_map(bounds, plane)` builds an in-memory map in four broad stages.

1. Read `map_index` and select regions intersecting the requested bounds.
2. Decode floor definitions from `flo.dat`, object definitions from `loc.dat`/`loc.idx`, average texture colors from the texture archive, and mapscene sprites from the media archive.
3. Decode each selected terrain region into underlay ids, overlay ids, overlay shapes, overlay rotations, and tile settings.
4. Apply the same bridge/downshift rule used by the client minimap: when `settings[1] & 2` is set for a tile, plane `n + 1` is displayed on plane `n`. This keeps walkable-over-water surfaces such as Lumbridge bridges and Port Sarim docks visible in the base map.
5. Decode each selected object region into object id, local tile, height, type, and orientation, then attach object-definition metadata such as name, width, length, mapscene id, and mapfunction id.

The return value is a plain dictionary with:

- `tiles`: tile tuples containing world x/y, plane, underlay RGB, overlay RGB, overlay shape, and overlay rotation.
- `objects`: object dictionaries containing world x/y, display plane, source height, id, name, type, orientation, width, length, mapscene id, and mapfunction id.
- `bounds`, `regions`, `textures`, `mapScenes`, and `stats`.

`draw_world_map(canvas, world_map, project, scale)` then paints the map in layers:

1. Terrain tiles.
2. Large-object and mapscene-backed footprints.
3. Decoded mapscene sprites.
4. Simple mapfunction markers in the base cache canvas.
5. Wall, diagonal-wall, corner, and wall-decoration linework for object types `0`, `2`, `3`, and `9`.

## Terrain Color

Terrain color comes from floor underlays and overlays in `flo.dat`.

When a floor definition references a texture, the renderer derives an average RGB from the texture archive and prefers that over the raw floor RGB. This is the important water fix: some water-like surfaces are texture-backed, so a floor-color-only renderer can miss or miscolor them.

Overlay shape and rotation are preserved from terrain opcodes. Instead of painting every overlay as a full square, the renderer uses the client-style 4x4 shape masks in `SHAPE_MASKS` and `ROTATION_MASKS`. This makes roads, shorelines, path edges, and floor transitions closer to the minimap than the first cache renderer.

## Objects And Buildings

Early versions decoded region objects but only drew a few wall-like types. That made buildings and scenery look absent even though the cache data was present.

The current renderer parses `loc.dat` and `loc.idx` so it can use object dimensions, mapscene ids, and mapfunction ids. This adds several visible object layers:

- mapscene sprites for objects with `mapScene >= 0`;
- semi-transparent footprints for large type `10` and `11` objects, plus mapscene-backed objects;
- line marks for walls and related object types;
- simple cross markers for objects with mapfunction ids in the base cache canvas.
- decoded `mapfunction` sprites in the agent context and movement topology overlays, so banks, shops, altars, transport icons, and other minimap symbols are visible in bounded tactical maps.

This is intentionally minimap-inspired, not a perfect scene renderer. It gives the navigation harness useful world context without trying to render 3D models.

## Coordinate Model

The map uses game world tile coordinates:

- `x` increases east.
- `y` increases north.
- `plane` is the height level, defaulting to `0`.
- regions are `64 x 64` tiles.

PNG drawing flips the y-axis so north appears upward. A project function maps tile coordinates into pixel coordinates:

```python
px = (tile["x"] - bounds["minX"]) * pixels_per_tile
py = image_height - 1 - (tile["y"] - bounds["minY"]) * pixels_per_tile
```

When integrating the map into another application, keep the world-coordinate data from the JSON/dictionary and apply your own projection at display time.

## Using It From Python

The renderer can be imported by another local tool:

```python
from cache_world_map import draw_world_map, load_cache_world_map
from render_navigation_png import Canvas

bounds = {"minX": 2910, "minY": 3149, "maxX": 3305, "maxY": 3567}
world_map = load_cache_world_map(bounds, plane=0)

canvas = Canvas(1600, 1800, (232, 224, 199))

def project(tile):
    # Replace with your application's coordinate transform.
    ...

draw_world_map(canvas, world_map, project, scale=4.0)
canvas.save_png("/tmp/cache-map.png")
```

For non-PNG applications, use `load_cache_world_map()` as the data source and ignore `draw_world_map()`. The returned `tiles` and `objects` lists are suitable for GIS conversion, browser canvas rendering, route-planning debug views, or custom map tiles.

## Limitations

Known limitations to keep in mind:

- The renderer mirrors the client minimap's bridge/downshift rule, but it still renders one requested display plane at a time rather than a full 3D scene.
- Dynamic object variants from varbits/varps are decoded as definitions but not resolved against live game state.
- The base `draw_world_map()` helper still draws simple mapfunction markers; agent context maps and active movement topology renders draw decoded mapfunction sprites as an overlay.
- Large-object footprints are approximate navigation context, not exact client minimap output.
- Collision, reachability, doors-open state, NPCs, ground items, and other live server state are not part of this map.
- The full-world PNG is large. Use bounds for application previews, web tiles, and iterative debugging.

Use the cache-backed map as durable static context. Use `rs.observe_state`, movement traces, route data, and hazards for live gameplay truth.
