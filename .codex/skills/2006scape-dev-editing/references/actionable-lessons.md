# Actionable Lessons

These notes are repo-specific operational memory from actual agent experience. Add only durable lessons that would change future behavior.

## Java And Maven

### Keep new Java methods at class scope

- **Observed:** Adding a helper to `2006Scape Server/src/main/java/com/rs2/world/clip/PathFinder.java` caused `illegal start of expression` compiler errors.
- **Cause:** The new method was inserted inside an existing method body instead of after its closing brace.
- **Use instead:** Inspect enough surrounding structure with `nl -ba ... | sed -n` before and after patching large decompiled-style Java files.
- **Validation:** Run `mvn -q -DskipTests package` after bridge or server source edits.

### Verify Maven reactor module names before using `-pl`

- **Observed:** `mvn -q -pl server -Dtest=AgentToolServiceTest test` failed with "Could not find the selected project in the reactor: server".
- **Cause:** The selected Maven project key was assumed instead of checked.
- **Use instead:** Inspect the root `pom.xml` module names before using `-pl`; this repo's server module selector is `-pl '2006Scape Server'`. Running focused Maven commands from the module directory is also valid.
- **Validation:** The focused command should reach test execution rather than failing during Maven project selection.

## Codex Agent Bridge

### Runtime bridge changes need a restart before tool calls can prove them

- **Observed:** Adding a new bridge tool to Java source and client tool metadata compiles locally, but the currently running server/client keep using the old jar.
- **Cause:** The live bridge is served by the already-running JVM, not by modified source files.
- **Use instead:** Treat `mvn -q -DskipTests package` as compile validation only. Restart the server/client through `agent-navigation/tools/runtime_doctor.py` before testing new bridge tools through `agent-navigation/tools/rs-tool.sh`.
- **Validation:** After restart, call the new tool through `rs-tool.sh` and confirm the response shape matches the source change.

### Make primitive item-on-object start cooking interfaces

- **Observed:** `catherby_food_runner.py` could cook tuna through `use_item_on_object` plus `click_interface_button`, but the first lobster inventory logged `cook_primitive_round madeProgress:false` before falling back to `cook_food`.
- **Cause:** `AgentToolService.useItemOnObject` delegated to `UseItem.itemOnObject`, which does not open the Cooking interface for raw cookable food on ranges; previous tuna success depended on stale `player.cookingItem` state.
- **Use instead:** For raw cookable items used on known cooking objects, have `use_item_on_object` call `Cooking.startCooking(...)` before `click_interface_button` starts the selected amount.
- **Validation:** `mvn -q -pl "2006Scape Server" -Dtest=AgentToolServiceTest test` compiles the bridge surface; live proof still requires a runtime restart before bridge calls use the new code.

### Use the documented agent-owned relaunch for clean bridge sessions

- **Observed:** Stale clients, old `codex app-server --listen stdio://` children, and expired `agent-navigation/.local/rsbridge-session.json` files make fresh bridge testing unreliable after server restarts.
- **Cause:** The repo-side bridge session is scoped to a logged-in client claim; restarting only one part leaves the wrapper pointing at an invalid session.
- **Use instead:** Prefer `python3 agent-navigation/tools/runtime_doctor.py restart --replace-runtime --build --verify`. It performs the documented cleanup, detached server/client launch, nonce claim, token-safe session-file write, and `observe-slim` verification. Use `docs/local-agent-startup.md` only for details or manual fallback.
- **Validation:** `agent-navigation/tools/observe-slim.sh` returns `success:true` for player `mrflame`.

### Use Python detached launch instead of shell backgrounding

- **Observed:** `nohup ./scripts/start-server.sh > /tmp/2006scape-server.log 2>&1 &` reported a PID but the server exited silently and no usable Java process remained.
- **Cause:** Background processes launched from transient Codex shell commands can lose the intended process/session ownership.
- **Use instead:** Use `agent-navigation/tools/runtime_doctor.py`, which launches server/client processes with Python `subprocess.Popen(..., start_new_session=True)` and writes pid/log files under predictable paths. If hand-launching is unavoidable, use the same Python detached-launch pattern.
- **Validation:** `runtime_doctor.py status --observe` shows both ports open and a valid `mrflame` bridge session.

### Process inspection and shutdown may need sandbox escalation

- **Observed:** `ps aux | rg ...` returned `operation not permitted`, and stopping a detached `route_recorder.py` process raised `PermissionError: [Errno 1] Operation not permitted`.
- **Cause:** macOS process inspection and signaling can be blocked by the active Codex sandbox even for same-user Java/Python runtime processes.
- **Use instead:** First try repo-local status commands such as `python3 agent-navigation/tools/runtime_doctor.py status --observe` and `python3 agent-navigation/tools/runtime_doctor.py recorder status`; when a real clean restart requires process inspection or termination, request escalation for narrow `ps` or `kill` commands rather than working around it with unrelated scripts.
- **Validation:** Re-check that old server/client/app-server/recorder processes are gone before launching a fresh runtime.

## Navigation Tooling

### Gate Catherby fishing methods by Cooking level

- **Observed:** `agent-navigation/tools/catherby_food_runner.py` switched from harpoon tuna to lobster at Fishing 40, filled an inventory of raw lobsters, then failed with `cooking made no progress for 2 rounds` at Cooking 37.
- **Cause:** The method policy considered Fishing unlocks but not Cooking requirements; this server requires Cooking 40 for lobster and Cooking 50 for swordfish.
- **Use instead:** Choose Catherby fishing methods by both Fishing and Cooking levels, and bank any uncookable raw fish during recovery before resuming a cookable method.
- **Validation:** A recovery run with raw lobsters at Cooking 37 logs `cook_uncookable_raw_deferred`, banks the raw lobsters, deposits the lobster pot, withdraws the harpoon, and resumes harpoon tuna.

### Let Catherby fishing waits run to useful boundaries

- **Observed:** `catherby_food_runner.py` accepted `--max-fish-ticks 900`, but each fish wait was hard-capped at 120 ticks, so one lobster inventory produced several extra `find_nearest_npc`/`interact_npc`/status cycles.
- **Cause:** The wait loop used `min(120, ...)`, which woke the script even while passive telemetry showed the player was still actively fishing with no idle spans.
- **Use instead:** Use the configurable `--fish-round-max-ticks` long wait and rely on `wait_until_idle` returning early when the spot moves, the inventory fills, a level-up interrupts skilling, or the player becomes idle.
- **Validation:** The patched runner log includes `maxWaitTicks:900` and `maxWaitTicks:650` fish rounds while `catherby_food_runner.py --efficiency-report --quiet` still reports `idlePct:0.0`.

### Treat `PathFinder` as a local clip oracle, not the global router

- **Observed:** Route exploration repeatedly bounced into blocked pockets even though normal walking used server pathfinding.
- **Cause:** `com.rs2.world.clip.PathFinder` solves clipped movement only inside the current 104x104 local map region; it does not know hazard history, deaths, route confidence, run energy, food, or long-distance objectives.
- **Use instead:** Keep long-range planning in `agent-navigation` route/trace/hazard tooling. Use `PathFinder` or bridge preview tools only to preflight local legs before movement.
- **Validation:** A planned route should combine a learned macro path from `agent-navigation/tools/router.py` with local clipped reachability checks before issuing walk commands.

### Keep passive movement logging out of the AI loop

- **Observed:** Running `route_recorder.py` while server passive traces and agent batch traces existed double-counted movement and added stationary polling records to `agent-navigation/data/movement_traces.jsonl`.
- **Cause:** The fallback recorder polls `rs.observe_state`; it is useful for old runtimes and extra NPC snapshots, but it duplicates authoritative `AgentPassiveTraceLog` output on current builds.
- **Use instead:** Prefer passive server telemetry. Use `python3 agent-navigation/tools/runtime_doctor.py recorder start` only as a fallback/dev supplement when the running build lacks passive traces or extra NPC snapshots are explicitly useful. Default trace consumers should use passive traces, drop stationary idle state heartbeats, and require opt-in env vars for agent batch or legacy fallback traces.
- **Validation:** `python3 agent-navigation/tools/runtime_doctor.py recorder status` should report not running for normal sessions, `route_recorder.py start` should refuse while recent passive telemetry exists, and `python3 agent-navigation/tools/navdb.py graph-summary` should read passive non-idle trace counts without legacy fallback records unless intentionally opted in.

### Do not recreate the retired minimap fog sampler

- **Observed:** A background minimap sampler launched with `--focus` brought the Java game window to the foreground every few seconds.
- **Cause:** The sampler intentionally focused the client before screenshots, which disrupted normal desktop use.
- **Use instead:** Use the cache-backed map renderer and movement topology tools. Keep screenshot capture manual and evidence-driven, not a periodic focus-stealing background process.
- **Validation:** Repo searches should not reintroduce `minimap_fog.py` or startup instructions that run a focused sampler.
