# Movement Telemetry

2006Scape routing, map visualization, and future route-learning/ML tooling use one movement event language.

## Producers

- `AgentPassiveTraceLog`: primary and default route-learning producer. Runs inside the game server tick and object packet path, writing passive player movement and object interaction traces without an AI request loop.
- `AgentMovementTraceLog`: bridge batch diagnostics producer. Records detailed tool execution traces for `walk_to_tile_until_arrived`, `travel_to_landmark_until_arrived`, and object transitions. These traces are retained for debugging, but are not consumed by default when passive player traces exist because they duplicate the same movement.
- `agent-navigation/tools/route_recorder.py`: fallback/dev producer. Polls `rs.observe_state` and writes compact records only when a build does not yet have passive server telemetry or extra NPC snapshots are explicitly useful.

Use `python3 agent-navigation/tools/runtime_doctor.py recorder status|start|stop` for fallback recorder control. Do not leave the fallback recorder running during normal passive-telemetry sessions. `route_recorder.py` refuses to start when recent passive telemetry exists unless `--allow-passive-duplicate` is passed for a deliberate debug recording. Add `--profile <name>` or set `RS_PROFILE=<name>` when recording or reading traces for a non-default character.

## Log Locations

```text
2006Scape Server/data/logs/player-movement-traces/<yyyy-MM-dd>/<player>.jsonl
2006Scape Server/data/logs/agent-movement-traces/<yyyy-MM-dd>/<sessionId>.jsonl
agent-navigation/data/movement_traces*.jsonl
```

## Common Event Shape

The shared schema is `agent-navigation/schema/movement_trace.schema.json`. Consumers should rely on these stable fields first:

- `schemaVersion`, `timestamp`, `timestampMs`
- `event`, `source`, `tool`, `traceId`, `sessionId`
- `playerId`, `playerName`
- `tile`, `previousTile`, `edgeKey`, `moved`
- `object`, `objectId`, `objectName`, `objectTile`, `option`, `objectOption`, `objectInteractionPhase`, `packetOpcode`
- `runEnabled`, `runEnergy`, `runEnergyDelta`, `runEnergySpent`
- `hitpoints`, `maxHitpoints`, `hitpointsDelta`, `hitpointsLost`
- `isMoving`, `isDead`, `isInCombat`
- `npcIndex`, `killingNpcIndex`, `underAttackBy`, `underAttackBy2`
- `foodCount`, `freeInventorySlots`

Passive player traces also include `activity` booleans for movement, combat, skilling, banking, shopping, trading, and dialogue. This lets non-AI consumers reconstruct what the player was doing around each route edge.

Manual and bridge-driven object clicks emit `object_interaction` records into the passive player trace file. The `queued` phase captures the raw object packet target from the player's current tile; the `completed` phase captures the reached/pre-interaction tile and the post-handler tile when the object action changes position or height. Use this for doors, gates, ladders, stairs, portals, and other object transitions. Consumers must not treat object-backed edges as ordinary reversible walking edges.

## Consumers

`agent-navigation/tools/navdb.py` owns the unified trace iterator. Route graph summaries, `agent-navigation/tools/router.py`, the active movement map wrappers (`render_movement_topology_v4.py`, `render_movement_topology_v5.py`, `render_movement_topology_v6.py`), and their shared engine (`render_movement_topology_v2.py`) should consume traces through `navdb.iter_movement_traces()` instead of reading one producer directly. The original `render_movement_topology.py` is legacy comparison code.

By default the iterator uses passive player traces when they exist and drops stationary `event:"state"` idle heartbeat records from route/map inputs. Agent batch traces are included only when no passive traces exist or when `NAVDB_INCLUDE_AGENT_BATCH_TRACES=1` is set. Legacy fallback recorder traces are included only when no server traces exist or when `NAVDB_INCLUDE_LEGACY_RECORDER_TRACES=1` is set. Explicit `--trace-file` paths are always honored. Set `NAVDB_INCLUDE_IDLE_STATE_TRACES=1` only for diagnostics that need stationary state heartbeats.

This keeps routing, maps, and route-learning experiments on the best available data stream while preventing duplicate movement evidence.

For multi-character runs, pass `--trace-profile <name>` or set `RS_PROFILE=<name>`. Consumers then exclude other players' trace evidence by default; use `--include-unscoped-traces` only when intentionally mixing legacy records that predate player metadata.
