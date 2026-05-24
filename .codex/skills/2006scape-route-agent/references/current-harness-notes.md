# Current 2006Scape Harness Notes

Important local files:

- `agent-navigation/tools/observe-slim.sh`: compact state observe wrapper.
- `agent-navigation/tools/rs-tool.sh`: bridge wrapper for gameplay tools.
- `agent-navigation/tools/runtime_doctor.py`: status, restart, claim, verify, and route recorder helper.
- `agent-navigation/tools/capture-cardinal-screenshots.sh`: compact north/east/south/west client screenshots.
- `agent-navigation/tools/navdb.py`: route DB decisions, observations, validation, tests.
- `agent-navigation/tools/route_runner.py`: low-token learned-route executor around `router.py`.
- `agent-navigation/tools/render_navigation_png.py`: canonical surface map renderer.
- `agent-navigation/tools/cache_world_map.py`: cache-backed world-map renderer.
- `agent-navigation/topology/surface-routes.png`: current route map.
- `agent-navigation/topology/cache-world-map.png`: cache-backed world map.

Current important places/routes:

- `lumbridge_basement_entry`: verified at `3208,9616,0`.
- `lumbridge_castle_trapdoor_to_basement`: verified chain from `3208,3216,0` via objects `14879` then `10698`.
- `lumbridge_basement_rockslugs_level_29`: dangerous-for-new-accounts hazard.

Known pitfalls:

- Do not start background screen samplers that steal focus from the user's Mac.
- Use cache-backed map generation for terrain context instead of screenshot-based sampling.
- User may manually move, attack, or interact; observe before assuming autonomous causality.
