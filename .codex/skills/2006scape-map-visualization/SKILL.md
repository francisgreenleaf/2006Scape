---
name: 2006scape-map-visualization
description: "Use when designing, rendering, reviewing, or improving 2006Scape map visual outputs in /Users/kevin/Documents/2006Scape, including movement-topology PNGs, cache-world-map artifacts, route overlays, movement trace styling, grid/label readability, canonical image paths, visual QA, and sharing map images with users. Use with 2006scape-cache-map when renderer internals or cache decoding are involved."
---

# 2006Scape Map Visualization

Use this skill for how map outputs should look and be reviewed. Use `2006scape-cache-map` for cache decoding, terrain/object/mapscene renderer internals, or data export.

## Canonical Outputs

- `agent-navigation/topology/movement-topology-v4.png`: active profile movement map.
- `agent-navigation/topology/movement-topology-v5-heatmap.png`: active `Heat Map` with transparent coverage density for route-learning/ML inspection.
- `agent-navigation/topology/movement-topology-v6.png`: active profile fog topology with route/icon overlays and dimmed unvisited map context.
- `agent-navigation/topology/cache-world-map-full.png`: reusable full cache-bounds base map export with labels and no movement overlays.
- `agent-navigation/topology/cache-world-map-level0.png`: reusable labeled level-0 surface base map export for scripts that need a static base map.
- `agent-navigation/.local/map-summaries/*.json`: ignored summaries for active map renders and auxiliary map outputs.
- `agent-navigation/.local/context-maps/<date>/*.png`: ignored, timestamped agent context-map artifacts for current-location and segment debugging.
- `agent-navigation/.local/context-maps/<date>/*.json`: matching machine-readable context-map summaries with bounds, center, POI markers, and place markers.
- `agent-navigation/ml-routing/artifacts/comparisons/<runId>/*.png`: ignored ML before/after benchmark route maps. Use these for route-quality visual comparisons, not as active topology outputs.
- `agent-navigation/ml-routing/artifacts/comparisons/<runId>/*.json`: per-case marker/metric sidecars; the aggregate `comparison-report.json` is compact and points to these details.
- `agent-navigation/analysis/movement-topology-<date>.png`: dated analysis renders when comparison is useful.

`agent-navigation/topology/` should stay uncluttered: keep only the three active user-facing movement PNGs plus the two reusable cache-world-map base exports there. Avoid timestamp clutter, JSON sidecars, surface-route renders, and one-off proof/shortcut/context exports in `topology/`; those belong under ignored `.local/` paths unless the user explicitly asks for a shareable artifact.

## Render Commands

For the active profile movement map:

```sh
agent-navigation/tools/render_profile_map.py
```

Movement topology reads unified movement traces through the shared nav trace sources. Passive server player traces from `2006Scape Server/data/logs/player-movement-traces/` are the main evidence source; the plain-name user-facing map wrappers also backfill historical agent-batch traces recorded before passive player tracing began, so early exploration/deaths remain visible without double-counting newer batches. Stationary idle `state` heartbeats, full duplicate agent batch traces, and legacy fallback `agent-navigation/data/movement_traces*.jsonl` are opt-in/fallback only. Use `--trace-profile NAME` or `RS_PROFILE=NAME` to render one character's evidence.

For the active `Heat Map` and profile fog player-facing analysis maps:

```sh
agent-navigation/tools/render_heat_map.py
agent-navigation/tools/render_fog_map.py
```

Use the profile movement map for the main map, `Heat Map` for player-facing trace-coverage density, and the profile fog map for fog-of-war coverage. Agents should not run these full topology renders during live routing unless explicitly asked. Active movement maps read the latest movement traces at render time. Legacy versioned map renderers may exist on disk for old outputs or compatibility; leave them alone and use the plain-name scripts as the current map interface.

For continuous background refresh while movement traces are being collected:

```sh
agent-navigation/tools/active_map_refresher.py start
agent-navigation/tools/active_map_refresher.py status
```

Use `agent-navigation/tools/active_map_refresher.py` as the special background tool; it manages the PID, log, status file, and restart behavior for the lower-level `refresh_active_maps.py` worker. The refresher updates the profile movement map, `Heat Map`, and profile fog in independent non-overlapping worker loops on a five-minute target cadence. It writes ignored temp/status files under `agent-navigation/.local/map-refresh/`, ignored summaries under `agent-navigation/.local/map-summaries/`, uses per-map cache subdirectories under `agent-navigation/.local/topology-render-cache/` for parallel topology workers, and atomically replaces the three canonical PNG files only after successful renders. Use `refresh_active_maps.py --once ...` directly only for one-shot validation or renderer debugging.

For route overview:

```sh
agent-navigation/tools/render_navigation_png.py \
  --region all \
  --output agent-navigation/.local/map-summaries/surface-routes.png
```

For current location or segment context without full-world resolution:

```sh
python3 agent-navigation/tools/render_agent_context_map_XS.py --center latest

python3 agent-navigation/tools/map_grid.py locate --tile 3222,3218,0

python3 agent-navigation/tools/render_agent_context_map_XS.py --grid-cell AU21 --grid-padding-tiles 4

python3 agent-navigation/tools/render_agent_context_map_XS.py \
  --segment-from FROM_PLACE \
  --segment-to TO_PLACE
```

By default, `render_agent_context_map_XS.py` delegates to the full context renderer and writes unique PNG/JSON artifacts under ignored `agent-navigation/.local/context-maps/<date>/`. Filenames include timestamp, mode, resolved center tile, radius, and pixel scale, so repeated Router/debug renders do not overwrite each other or clutter `agent-navigation/topology/`. Context maps draw the level-0 32-tile reference grid by default; use `map_grid.py locate --tile X,Y,H` to convert a tile to shorthand such as `AU21`, then `render_agent_context_map_XS.py --grid-cell AU21` to render that cell. Use full `render_agent_context_map.py` only when XS omits marker/detail fields needed for debugging. Use explicit `--output` and/or `--summary` only when a stable path is intentionally needed for a smoke test or a user-facing artifact.

For agent routing, consume the JSON summary before opening the PNG. The summary includes bounds, center, output path, mapfunction/place marker counts, and marker coordinates. Loading the PNG into the thread is appropriate only when geometry or label placement cannot be resolved from JSON and tool output.

For cache-map internals or full-map rendering, switch to `2006scape-cache-map`.

For ML before/after route comparisons:

```sh
python3 agent-navigation/ml-routing/route_ml_XS.py compare-maps \
  --case CASE_NAME \
  --combat-level N \
  --food N \
  --run-energy N \
  --run-enabled
```

`compare-maps` uses the shared cache/context-map base layers, so benchmark images already include terrain, water, mapscene buildings, large object footprints, mapfunction icons, and place labels. Old routes are red, new routes are cyan, and hazard/run segments are overlaid in yellow. Read the compact `comparison-report.json` first; use the per-case sidecar JSON for marker labels/coordinates, compact `routeSteps`, and `runPlan` details, and open the PNG only when route geometry itself needs visual review.

## Visual Standards

Maps should be useful at a glance:

- keep terrain visible behind overlays;
- keep movement traces readable without hiding roads, rivers, and buildings;
- use labels sparingly and avoid label collisions;
- make blockers, hazards, verified routes, partial routes, and raw movement traces visually distinct;
- avoid heavy grid lines that compete with roads or trace paths;
- keep coordinate grid overlays disabled on active movement topology maps unless the user explicitly asks for coordinate debugging;
- preserve north-up world coordinates and explain bounds/pixels-per-tile when sharing analysis.
- use integer pixel scales for bounded context maps so the result stays lossless and pixel-perfect without resampling.
- use `cache-world-map-full.png` or `cache-world-map-level0.png` when another script needs a static labeled base map instead of re-rendering or sampling the client.
- keep user-facing place labels centralized in `agent-navigation/tools/map_labels.py` so cache-world exports, the profile map, `Heat Map`, and profile fog agree on Varrock, Barbarian Village, Edgeville, Ice Mountain, and other named places.
- keep agent context maps bounded, compact, and archived under `.local/context-maps`; use `render_agent_context_map_XS.py` rather than full topology or heatmap renderers for tactical routing.
- keep nearby route geometry visible in agent segment maps, including docks, ports, bridges, and useful POI surroundings; use padding/max-span options rather than a full-world render when the default crop is too tight.
- include all cache mapfunction icons in agent context maps, and rely on JSON marker labels before opening images when visual labels are too dense.
- keep the agent-facing level-0 grid consistent across the profile map and context maps: 32-tile cells, columns west-to-east as `A..Z, AA..`, rows south-to-north starting at `1`, with `currentGridCell` and `referenceGridCells` in JSON summaries.
- reuse `render_context_map.draw_static_context_layers` for new bounded route comparison images so mapfunction icons and place labels stay consistent across agent tools.
- for `Heat Map`, keep the gradient legend separate from route-state items; do not reintroduce the old `DENSE` legend item because coverage now represents trace density.
- for `Heat Map`, the optimized cached mask is applied once with a non-saturating max radial mask. If every explored tile looks dense, inspect the heat mask/cache version and summary before changing unrelated map layers.
- for active movement maps, keep the title short and use the title-bar stats panel for profile skill levels, total level, and playtime instead of explanatory paragraph text. The skill tiles should stay modeled after the client stats tab interface `3917`, using the cache `miscgraphics` tile backing, `staticons`/`staticons2` icons, OSRS yellow text, combat-first menu-style skill order, and the built-in slash divider with same-size current/base level text above-left of the slash and `99` below-right; arrange them as the current wide two-row map strip rather than the exact in-client 3x7 shape.
- for profile fog, keep route/death/current markers above the fog layer, dim unvisited background context very dark, use a wider visible reveal around movement evidence, and hide cache POI icons beyond the separate explored POI radius close to the visible reveal.
- for `Heat Map` and profile fog performance work, preserve exact full-resolution output. Prefer exact radial-kernel caching, the append-validated topology prefix cache, the static base-map canvas cache, the POI list cache, ignored full-resolution heat/fog coverage caches in `agent-navigation/.local/topology-render-cache`, direct byte-level loops/downsampling, quantized bounds, and spatial indexes. Do not switch coverage to lower-resolution masks or paint over stale final PNGs unless the user explicitly trades quality for speed. Verify behavior through the summary `cache` block plus `coverageHeatCache`/`coverageFogCache`, cached node counts, and rendered node counts.

When the user asks to see an image, render or reference it with an absolute path:

```markdown
![Profile movement map](/Users/kevin/Documents/2006Scape/agent-navigation/topology/movement-topology-v4.png)
```

## Review Workflow

After changing a visualization script or style:

1. Run a bounded or temporary render first if full render cost is high.
2. Open or view the output image before declaring it done when the task is visual QA or user-facing map work; for live agent routing, prefer the JSON summary and open images only when needed.
3. Check that roads/water/buildings remain visible, traces do not look like noisy square beads, labels are readable, legend items do not overlap, death counts match the intended semantics, and respawn/teleport jumps are not drawn as route lines.
4. Update only visualization docs/skills when the workflow changes; do not edit game code for visual-only tasks.

Use summaries (`*.json`) to verify bounds, trace counts, tiles, and output path. Use the PNG for readability and composition.

## Runtime Boundaries

Visualization work should not require a live client or server. Do not restart gameplay processes or run focus-stealing screenshot samplers for map visuals. The retired minimap fog collector must stay retired.

## Skill Maintenance

If you discover a better map style, renderer option, canonical output convention, or visual QA check while using this skill, surface it to the user and ask whether to make the skill edit.
