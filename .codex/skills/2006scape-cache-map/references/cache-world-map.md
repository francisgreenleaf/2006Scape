# Cache-Backed World Map Reference

## Contents

- Purpose
- Generated Artifacts
- Cache Inputs
- Data Flow
- Terrain Rendering
- Object And Building Rendering
- Movement Topology Integration
- Reuse From Python
- Limitations
- Improvement Ideas

## Purpose

The 2006Scape cache-backed world map is a static minimap-style renderer built from `2006Scape Server/data/cache`. It replaced the old screenshot/minimap fog workflow. It does not need a logged-in player, does not capture the visible client window, and does not bring the Java client to the foreground.

The renderer is intentionally practical rather than a full scene renderer. It gives the agent-navigation harness durable terrain and object context for route planning, topology inspection, and external map export.

## Generated Artifacts

Canonical active map outputs live under `agent-navigation/topology/`:

```text
movement-topology-v4.png
movement-topology-v5-heatmap.png
movement-topology-v6.png
```

The active movement maps are the profile movement map, `Heat Map`, and profile fog; they overlay learned movement traces, failures, deaths, combat edges, visited tiles, route density, and fog-of-war coverage on top of bounded cache-map backgrounds. JSON summaries and auxiliary full cache-map or route-overview renders default to ignored files under `agent-navigation/.local/map-summaries/`. Legacy movement-topology outputs may exist for old experiments, but they are not current user-facing maps.

Agent context maps are not canonical topology exports. By default, `render_agent_context_map.py` and `render_context_map.py` write unique ignored artifacts under `agent-navigation/.local/context-maps/<date>/`; use explicit `--output` and `--summary` only for a deliberate smoke test or a user-facing comparison.

Current full-map summary:

```text
bounds: 1728,2560 through 3839,10367
plane: 0
pixels per tile: 2
regions: 660
tiles: 2,128,515
objects: 948,982
object definitions: 14,974
mapscene sprites: 80
mapscene objects: 47,723
footprint objects: 31,028
mapfunction objects: 933
```

Render the full map from repo root:

```sh
agent-navigation/tools/cache_world_map.py \
  --output agent-navigation/.local/map-summaries/cache-world-map.png \
  --summary agent-navigation/.local/map-summaries/cache-world-map.json
```

Render a bounded preview:

```sh
agent-navigation/tools/cache_world_map.py \
  --bounds 2910,3149,3305,3567 \
  --pixels-per-tile 4 \
  --output /tmp/lumbridge-varrock.png \
  --summary /tmp/lumbridge-varrock.json
```

Render the active movement maps:

```sh
agent-navigation/tools/render_profile_map.py
agent-navigation/tools/render_heat_map.py
agent-navigation/tools/render_fog_map.py
```

Keep active exports fresh while traces are changing:

```sh
agent-navigation/tools/active_map_refresher.py start
```

The refresher runs the profile movement map, `Heat Map`, and profile fog in independent non-overlapping worker loops on a five-minute target cadence. It writes status/temp files under ignored `agent-navigation/.local/map-refresh/`, writes summaries under ignored `agent-navigation/.local/map-summaries/`, gives parallel topology workers separate persistent cache subdirectories under `agent-navigation/.local/topology-render-cache/`, passes trace-profile filters through to movement renderers, and atomically replaces the three canonical PNG outputs only after successful renders.

## Cache Inputs

The renderer reads the same cache family used by the client:

- `main_file_cache.dat` and `main_file_cache.idx*`: low-level cache container files.
- archive `0,5`, entry `map_index`: region ids and terrain/object file ids.
- archive `0,2`, entries `flo.dat`, `loc.dat`, and `loc.idx`: floor and object definitions.
- archive `0,6`: texture sprite data used for average texture colors.
- archive `0,4`, entries `mapscene.dat` and `index.dat`: mapscene background sprites.
- index `4`: compressed terrain and object region payloads.

The renderer uses local Python cache decoding helpers. It does not invoke the Java client or server.

## Data Flow

`load_cache_world_map(bounds, plane)` returns a dictionary with static map data:

- `tiles`: tuples of world x/y, plane, underlay RGB, overlay RGB, overlay shape, and overlay rotation.
- `objects`: dictionaries of object id, name, world x/y, height, type, orientation, width, length, mapscene id, and mapfunction id.
- `bounds`: requested or inferred world tile bounds.
- `regions`: selected map region count.
- `textures`: decoded texture color count.
- `mapScenes`: decoded mapscene sprites.
- `stats`: object definition, mapscene, mapfunction, and footprint counts.

The high-level pipeline:

1. Load `map_index` and select regions intersecting the requested bounds.
2. Decode `flo.dat`, `loc.dat`, `loc.idx`, texture colors, and mapscene sprites.
3. Decode terrain regions into underlays, overlays, overlay shapes, overlay rotations, and settings.
4. Decode object regions into object placements.
5. Join object placements to `loc` definitions for dimensions and minimap metadata.
6. Draw terrain, object footprints, mapscene sprites, mapfunction markers, and wall linework.

## Terrain Rendering

Terrain color comes from floor underlays and overlays in `flo.dat`.

When a floor references a texture, the renderer derives an average RGB from the texture archive and prefers it over the raw floor RGB. This is the water fix: water-like surfaces can be texture-backed, so a floor-RGB-only renderer can miss or miscolor water.

Terrain opcodes also include overlay shape and rotation. The renderer preserves those values and uses client-style 4x4 masks (`SHAPE_MASKS` and `ROTATION_MASKS`) instead of always painting overlays as full squares. This improves roads, path edges, shorelines, and floor transitions.

## Object And Building Rendering

Early cache renders decoded object placements but only drew simple wall-like object types. That made buildings and scenery look missing even when cache data existed.

The current renderer parses `loc.dat` and `loc.idx` so it can attach:

- `width`
- `length`
- `mapScene`
- `mapFunction`
- `name`

The renderer draws several object layers:

1. Semi-transparent footprints for large type `10` and `11` objects and mapscene-backed objects.
2. Actual decoded mapscene sprites for objects with `mapScene >= 0`.
3. Simple cross markers for objects with mapfunction ids.
4. Wall, corner, diagonal, and wall-decoration linework for object types `0`, `2`, `3`, and `9`.

This is minimap-inspired, not model-accurate. It is meant to reveal buildings and navigation context without reimplementing the 3D scene renderer.

## Movement Topology Integration

The active movement maps use the shared movement topology engine, which imports:

```python
from cache_world_map import draw_world_map, load_cache_world_map
```

It computes bounds from movement traces, loads a bounded cache map for those bounds, paints the map, then draws movement edges, visited nodes, combat/failure markers, and death markers.

The active wrappers reuse the same cache-map helpers and canonical movement trace loader. The profile fog wrapper also uses exact full-resolution fog reveal caching under the ignored `agent-navigation/.local/topology-render-cache` directory.

`render_movement_topology_v2.py` is the shared engine for active wrappers. Do not present its direct `movement-topology-v2.*` defaults, the original `movement-topology.*`, or old one-off proof/shortcut exports as current products.

Disable the cache background with:

```sh
agent-navigation/tools/render_movement_topology_v4.py --no-world-map
```

or:

```sh
agent-navigation/tools/render_movement_topology_v4.py --world-map-source none
```

## Reuse From Python

Use `load_cache_world_map()` as the reusable data source:

```python
from cache_world_map import load_cache_world_map

bounds = {"minX": 2910, "minY": 3149, "maxX": 3305, "maxY": 3567}
world_map = load_cache_world_map(bounds, plane=0)
```

Use `draw_world_map()` when a simple PNG/canvas renderer is enough:

```python
from cache_world_map import draw_world_map, load_cache_world_map
from render_navigation_png import Canvas

world_map = load_cache_world_map(bounds, plane=0)
canvas = Canvas(1600, 1800, (232, 224, 199))

def project(tile):
    # Convert world tile x/y into pixel x/y for this canvas.
    ...

draw_world_map(canvas, world_map, project, scale=4.0)
canvas.save_png("/tmp/cache-map.png")
```

For web, GIS, or custom tile applications, consume `tiles` and `objects` directly and use the application's own projection. World coordinates use game tiles: x east, y north, plane as height. PNG output flips y so north appears upward.

## Limitations

- One plane is rendered at a time.
- Client-style bridge and upper-plane compositing is simplified.
- Dynamic object variants from varbits/varps are not resolved against live state.
- The base `draw_world_map()` helper uses simple mapfunction markers; agent context maps and active movement maps draw decoded `mapfunction` sprites as an overlay.
- Large-object footprints are approximate.
- Collision, reachability, open/closed doors, NPCs, items, player location, and other live server state are outside the static cache map.
- The full-world PNG is large; use bounds for web previews and iterative debugging.

Treat the cache map as durable static context. Use `rs.observe_state`, movement traces, route data, and hazards for live truth.

## Improvement Ideas

Useful next improvements:

- Promote the mapfunction sprite overlay into `draw_world_map()` if the full cache-world PNG needs the same icon fidelity as agent context maps.
- Add optional plane/bridge compositing closer to the Java client minimap.
- Export vector or tile-indexed JSON for browser map viewers.
- Add command-line layer toggles for terrain, mapscene, footprints, walls, and mapfunction markers.
- Add deterministic color legends for object types useful to the navigation harness.
