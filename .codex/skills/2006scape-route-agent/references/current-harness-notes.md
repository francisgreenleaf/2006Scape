# Current 2006Scape Harness Notes

Important local files:

- `agent-navigation/tools/observe_XS.sh`: default extra-compact state observe wrapper.
- `agent-navigation/tools/rs-tool_XS.sh`: default extra-compact bridge wrapper for gameplay tools.
- `agent-navigation/tools/observe-slim.sh` and `agent-navigation/tools/rs-tool.sh`: fallback bridge wrappers for missing fields or debugging. `rs-tool.sh observe_state` requires `RS_ALLOW_FULL_OBSERVE=1` to prevent accidental full-state context dumps.
- `agent-navigation/tools/runtime_doctor.py`: status, restart, claim, verify, and route recorder helper.
- `agent-navigation/tools/capture-cardinal-screenshots.sh`: compact north/east/south/west client screenshots.
- `agent-navigation/ml2-routing/route_ml_XS.py`: preferred ML2 route-definition API for normal A-to-B routing.
- `agent-navigation/tools/navdb_XS.py`: default compact route DB observations, validation, tests, and diagnostic queries.
- `agent-navigation/tools/route_runner_XS.py`: compact legacy orientation/compatibility wrapper.
- `agent-navigation/ml2-routing/route_ml.py`, `agent-navigation/tools/navdb.py`, `agent-navigation/ml-routing/route_ml.py`, and `agent-navigation/tools/route_runner.py`: full/fallback tools for missing debug fields and compatibility checks.
- `agent-navigation/tools/render_navigation_png.py`: surface route overview renderer for ignored analysis artifacts.
- `agent-navigation/tools/cache_world_map.py`: cache-backed world-map renderer.
- `agent-navigation/tools/render_agent_context_map_XS.py`: default compact bounded cache-backed tactical map wrapper for current-tile and segment checks.
- `agent-navigation/tools/map_labels.py`: shared place/static labels for cache-world exports and active topology maps.
- `agent-navigation/topology/cache-world-map-full.png`: reusable labeled full cache-bounds base map.
- `agent-navigation/topology/cache-world-map-level0.png`: reusable labeled level-0 surface base map.
- `agent-navigation/topology/movement-topology-v4.png`: active profile movement map.
- `agent-navigation/topology/movement-topology-v5-heatmap.png`: active Heat Map.
- `agent-navigation/topology/movement-topology-v6.png`: active profile fog map.

Current important places/routes:

- `lumbridge_basement_entry`: verified at `3208,9616,0`.
- `lumbridge_castle_trapdoor_to_basement`: verified chain from `3208,3216,0` via objects `14879` then `10698`.
- `lumbridge_basement_rockslugs_level_29`: dangerous-for-new-accounts hazard.

Known pitfalls:

- Do not start background screen samplers that steal focus from the user's Mac.
- Use cache-backed map generation for terrain context instead of screenshot-based sampling.
- User may manually move, attack, or interact; observe before assuming autonomous causality.
