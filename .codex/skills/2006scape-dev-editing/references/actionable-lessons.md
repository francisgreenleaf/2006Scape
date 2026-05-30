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
- **Use instead:** Treat `mvn -q -DskipTests package` as compile validation only. Restart the server/client through `agent-navigation/tools/runtime_doctor.py` before testing new bridge tools through `agent-navigation/tools/rs-tool_XXS.sh` or `agent-navigation/tools/rs-tool_XS.sh`; use full `rs-tool.sh` only when compact proof omits a required field.
- **Validation:** After restart, call the new compact alias through `rs-tool_XXS.sh`/`rs-tool_XS.sh` and confirm the response shape matches the source change.

### Make primitive item-on-object start cooking interfaces

- **Observed:** `catherby_food_runner.py` could cook tuna through `use_item_on_object` plus `click_interface_button`, but the first lobster inventory logged `cook_primitive_round madeProgress:false` before falling back to `cook_food`.
- **Cause:** `AgentToolService.useItemOnObject` delegated to `UseItem.itemOnObject`, which does not open the Cooking interface for raw cookable food on ranges; previous tuna success depended on stale `player.cookingItem` state.
- **Use instead:** For raw cookable items used on known cooking objects, have `use_item_on_object` call `Cooking.startCooking(...)` before `click_interface_button` starts the selected amount.
- **Validation:** `mvn -q -pl "2006Scape Server" -Dtest=AgentToolServiceTest test` compiles the bridge surface; live proof still requires a runtime restart before bridge calls use the new code.

### Wire interface-button primitives to tanning and leather crafting handlers

- **Observed:** `click_interface_button` reported success on Tanner and leather-crafting dialogs, but cowhides stayed as cowhide and leather batches made no progress.
- **Cause:** `2006Scape Server/src/main/java/com/rs2/agent/AgentToolService.java` handled some skill interfaces but did not dispatch button ids to `Tanning.tanHide(...)` or `LeatherMaking.craftLeather(...)`.
- **Use instead:** When a primitive-backed runner relies on a server skill interface, verify `click_interface_button` actually routes those button ids to the matching gameplay handler before debugging the Python loop.
- **Validation:** After packaging and `runtime_doctor.py restart --replace-runtime --verify`, a live Tanner click converts cowhide to leather and leather recipe buttons consume leather/thread with XP gain.

### Use the documented agent-owned relaunch for clean bridge sessions

- **Observed:** Stale clients, old `codex app-server --listen stdio://` children, and expired `agent-navigation/.local/rsbridge-session.json` files make fresh bridge testing unreliable after server restarts.
- **Cause:** The repo-side bridge session is scoped to a logged-in client claim; restarting only one part leaves the wrapper pointing at an invalid session.
- **Use instead:** Prefer `python3 agent-navigation/tools/runtime_doctor.py restart --replace-runtime --build --verify`. It performs the documented cleanup, detached server/client launch, nonce claim, token-safe session-file write, and compact bridge verification. Use `docs/local-agent-startup.md` only for details or manual fallback.
- **Validation:** `agent-navigation/tools/observe_XXS.sh` or `agent-navigation/tools/observe_XS.sh` returns `success:true` for player `mrflame`.

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

### Suppress repeated stale combat targets

- **Observed:** The White Knight runner repeatedly attacked the same nearby NPC index, then cancelled after two no-XP polls because the player stayed adjacent but never entered productive combat.
- **Cause:** Fast local target selection treated the NPC as a valid candidate on every cycle, so a stale cancel did not affect the next target choice.
- **Use instead:** After `stale_combat_cancel`, temporarily suppress that NPC index or tile before selecting the next fast-local combat target.
- **Validation:** The patched White Knight run continued after suppressing `idx:692` and avoided the earlier repeated stale-cancel churn.

### Reattack after food interrupts combat

- **Observed:** The Moss Giant runner ate a lobster at the safe HP threshold, then stayed in a no-XP combat poll loop until manual reattack.
- **Cause:** Eating interrupts the active attack, while the runner still saw an `underAttack` NPC and waited instead of explicitly resuming combat.
- **Use instead:** After any in-fight `eat_if_needed` call consumes food, immediately reattack the same reachable in-bounds NPC before stale no-XP cancellation logic runs.
- **Validation:** The patched Moss Giant run logged `eat_food` at 40 HP followed by `reattack_after_eat` on the same target, then continued gaining XP and burying big bones.

### Refresh compact decision state after combat waits before inventory decisions

- **Observed:** A combat runner tried to bank after every Chaos Druid kill even while the inventory still had food.
- **Cause:** Older `wait_until_combat_event_XS` output was compact and combat-oriented, so inventory and equipment arrays could be omitted and food/loadout helpers that expected full `observe_state` data read zero food.
- **Use instead:** After XS/XXS combat waits, first use the compact result, `combat_state_XS`, `observe_state_XS`, or a focused helper such as `food_bank_XS` before `should_bank`, restock, equipment, or inventory policy decisions. Call full `observe_state` only when a specific required field is still missing.
- **Validation:** The Chaos Druid runner stayed out for 19 kills, banked accumulated rune/herb/coin loot, and did not restock after every single kill.

### Register gate transitions by primitive family

- **Observed:** Edgeville dungeon gates failed when the player opened a gate but did not immediately move through before closure; combat auto-retaliate could also pull movement back toward enemies.
- **Cause:** Raw object clicks rely on pathfinder behavior and do not encode approach tile, open object, through-footprint steps, side proof, midline resume, or combat movement policy.
- **Use instead:** Add each proven gate to a small transition catalog with a primitive family such as `simple_timed_open_gate`, `toll_dialogue_gate`, or `chained_timed_open_gate`. Use exact per-direction approach/open/step/proof data and disable auto-retaliate in hostile areas before crossing.
- **Validation:** The Edgeville second druid gate proved southbound from its midline to `3132,9916,0`, and the full Chaos Druid bank loop crossed both gates, exited the ladder, banked, and stopped safely.

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

## Progression Scripts

### Launching the GUI client from Codex requires escalation; sandboxed claim runs can fake progress

- **Observed:** `runtime_doctor.py claim` could print `client_starting ...` and leave only `Launching 2006Scape client against localhost...` in `/tmp/2006scape-client.log`, but never create `agent-navigation/.local/rsbridge-session.json` or connect the player.
- **Cause:** The launcher shell script can run inside the sandbox, but the actual GUI client launch needs to happen outside the sandbox; otherwise the bridge claim loop waits on a client that never really comes up.
- **Use instead:** When recovering a dead bridge session from Codex, run `python3 agent-navigation/tools/runtime_doctor.py claim --profile ... --verify` with escalated permissions so the Java client can actually open and log in.
- **Validation:** The escalated claim path produced `session_ready ...`, `observe_slim_ok`, and a fresh default session file, while repeated sandboxed claim attempts never did.

### Sandboxed `pgrep`/`pkill` can miss live client processes on this macOS setup

- **Observed:** `start-client.sh` and `runtime_doctor.py` emitted `sysmond service not found` / `Cannot get process list`, failed to detect an existing client, and allowed stale client instances to keep MrFlame logged in.
- **Cause:** macOS process enumeration from the sandbox is incomplete here, so `pgrep -f client-1.0-jar-with-dependencies.jar` is not reliable for single-instance enforcement or cleanup.
- **Use instead:** Prefer the tracked client pid files for first-pass cleanup, and if the server still shows the player online, use an escalated `pkill -f client-1.0-jar-with-dependencies.jar` before retrying the bridge claim.
- **Validation:** After the elevated `pkill`, the server log showed `[DEREGISTERED]: mrflame` and `Players: 0`, which allowed the next escalated claim to succeed cleanly.

### Guard `Game.method120()` when camera and player share the same tile

- **Observed:** The client could crash with `ArithmeticException: / by zero` at `Game.method120()` line `9632`, reached from `method146()` during normal drawing.
- **Cause:** When both camera delta components were zero, the `k1 > l1` branch fell through to `k1 * 0x10000 / l1`, dividing by zero.
- **Use instead:** Return early from `method120()` when both deltas are zero before computing the Bresenham-style step ratios.
- **Validation:** The client source now guards `k1 == 0 && l1 == 0` in `2006Scape Client/src/main/java/Game.java`, removing that divide-by-zero path from future launches.

### Re-resolve obstacle tiles after walking agility approaches

- **Observed:** Higher-course agility wrappers needed exact object tiles, but hotspot coordinates from server skill code were not always the same as the interactable cache object tile.
- **Cause:** The adaptive runner chose a variant before walking, so an approximate object tile could stay stale even after the player arrived beside the real obstacle.
- **Use instead:** After walking to an agility step's approach tile, refresh nearby objects and overwrite the step's object tile before interacting; if the first interact fails, refresh once and retry against the newly observed tile.
- **Validation:** Cache-derived course definitions such as the Barbarian Outpost course can use server hotspot approach tiles plus observed nearby-object correction instead of requiring perfect hand-guessed object coordinates on the first pass.

### Resume bank material loops from carried state, not assumed empty state

- **Observed:** The Guam cleaner failed after withdrawing a full inventory of grimy herbs, then immediately tried to continue the bank loop and raised `No inventory space available`.
- **Cause:** The script assumed each loop iteration started from an empty inventory and bank-ready interface instead of handling already-carried materials first.
- **Use instead:** For bank-side conversion/cleanup loops, first detect carried work items, close interfaces, process them, re-observe with XS or a focused helper such as `food_bank_XS`, then reopen or resume banking. Use full state only if compact output lacks a specific required field.
- **Validation:** The patched herb-cleaning flow can restart mid-trip with a full carried inventory and continue depositing cleaned output instead of failing on the next withdrawal.

### Refresh leather-crafting state after dead clicks instead of stopping the trip

- **Observed:** The Al Kharid leather runner sometimes hit one or two no-progress `click_interface_button` rounds at the Tanner, especially right after recipe changes, and could abort a healthy trip.
- **Cause:** `use_item_on_item` plus the recipe button can race the interface state; a dead click does not always mean the trip is stuck.
- **Use instead:** After a no-progress leather craft round, close interfaces, wait a tick, re-observe, and retry before declaring the trip failed.
- **Validation:** The patched runner logged `craft_retry_refresh` on a dead leather-cowl click, then resumed gaining Crafting XP on the next batch instead of exiting.

### Retry transient bridge tick timeouts before killing a live loop

- **Observed:** `al_kharid_crafting_runner.py` died after a successful craft batch because a follow-up `observe_state` inside route execution returned `HTTP 400 {"message":"Timed out waiting for the next game tick."}`.
- **Cause:** A transient bridge read timeout during route startup was treated as fatal even though the player was safe and the next retry could continue normally.
- **Use instead:** In long primitive-backed loops, wrap post-route or recovery-state observes in a small retry helper and re-attempt the affected route once before aborting the whole run.
- **Validation:** The patched leather runner retried the Tanner-to-bank handoff, banked the carried `25` leather vambraces, and resumed the normal Al Kharid crafting loop.

### Restock thread during leather-loop resumes, not only at startup

- **Observed:** The leather runner resumed mid-trip with carried soft leather or started a new bank cycle with only a few banked thread left, then failed once `craft_batch` needed thread again.
- **Cause:** Thread/shop recovery originally ran only in the initial setup path, so restart and later-cycle material checks could carry leather without a viable thread reserve.
- **Use instead:** Before crafting carried leather and before each new cowhide/leather batch, verify `bank+inventory` thread against the target reserve and run the Dommik restock path when low.
- **Validation:** The patched runner resumed at Al Kharid bank with carried leather/chaps, deposited finished goods, routed to Dommik for thread, and continued the leather phase instead of stopping on `thread is required to craft leather goods`.

### Refresh after post-craft stale inventory reads before treating leather as missing

- **Observed:** The leather runner could finish a batch, then die on the next `use_item_on_item` with `No matching target inventory item found` while the inventory already held only finished leather goods plus thread and needle.
- **Cause:** A carried-state observe lagged behind the completed craft, so the next batch still believed leather remained and treated the stale mismatch as fatal.
- **Use instead:** When leather crafting reports a missing target item, re-observe once, log the refresh, and continue if the leather stack is already gone.
- **Validation:** A restarted Al Kharid leather run resumed from `25` carried leather chaps, deposited them, withdrew fresh leather, and continued crafting after the missing-target refresh path was added.

### Treat note-mode bank withdrawals as moved stock even when the bridge returns HTTP 400

- **Observed:** `withdraw_bank_items` in bank note mode could raise HTTP 400 `No matching bank item was withdrawn` even though the target stock had actually moved into inventory as notes.
- **Cause:** The server-side withdraw result can report zero normal withdrawals while still materializing noted items, so a direct bridge exception is not reliable evidence that nothing moved.
- **Use instead:** For noted sale loops, observe before and after the withdraw, count both normal and noted item ids, and accept the move when either delta is positive.
- **Validation:** The patched Al Kharid leather seller withdrew `56` noted leather bodies after a 400 response, then sold all `56` in one general-store batch instead of crashing.

### Treat exact-tile ML1 mining routes as partial-progress loops, not single-shot arrivals

- **Observed:** ML1 route definitions to raw mine tiles could return repeated `status:"partial"` / `returncode:4` while still moving the player a few tiles closer on each attempt, and eventually stall on suspicious one-tile frontier steps.
- **Cause:** The planner may only have short learned/frontier fragments toward an exact tile even when the broader place route is proven, so a single execute result is not enough to classify the route as failed or safe.
- **Use instead:** For mining/site travel, compare before/after tile distance and continue only while distance is materially shrinking; cap retries, watch for oscillation/suspicious quality, and prefer named proven places over raw exact tiles when possible.
- **Validation:** The patched `mining_runner.py` now records `route_bridge_failure` with before/after distance and keeps stepping through partial ML1 progress instead of failing on the first partial result.

### Bronze-balanced mining needs both single-ore batches and a hard preferred-ore bias

- **Observed:** A `bronze-balanced` mining loop could keep taking copper even with a copper-heavy inventory because the ore preference was overwritten by the later live-rock score sort.
- **Cause:** The loop selected a preferred ore from carried counts, but then rescored copper and tin normally and sorted by score, so the preference never actually controlled the choice.
- **Use instead:** For bronze balancing, mine only one ore per batch, then re-evaluate counts, and give the currently needed ore a decisive score bonus so the live-rock chooser cannot drift back to the wrong ore.
- **Validation:** The patched `mining_runner.py` logs `ore_choice` with tin scoring far above copper when the inventory is copper-heavy, and the live runner mined `tin` from the Al Kharid-linked mixed site instead of another copper round.

### The north Al Kharid bronze cluster at 3295,3313 is a primitive-mining trap

- **Observed:** A live bronze run reached `3295,3313,0`, found visible copper rocks, then looped forever with `interactSuccess:false`; direct `interact_object_XS` said the rock was visible but not reachable, and `walk_to_tile_until_arrived_XS` to the reported nearest interaction tile oscillated in place.
- **Cause:** That cache cluster exists visually, but at least its nearest primitive interaction tiles are clipped from the approach side, so a cache/manual site choice can look valid while being unusable for normal mining clicks.
- **Use instead:** Do not hard-code `3295,3313,0` for bronze mining. Prefer the proven Varrock east bank bronze cluster, or require a live reachability proof before trusting this Al Kharid-adjacent cluster.
- **Validation:** `interact_object_XS` on rock `2090` at `3296,3314` returned `visible but not reachable`, and the metals wrapper was corrected to use the Varrock east bank bronze site path instead.

### Detached gameplay runners need a Python launcher, not shell `&` or `nohup`

- **Observed:** Launching `al_kharid_metals_runner.py` with shell backgrounding returned a pid, but the process died immediately and left MrFlame idle at `3270,3167,0`.
- **Cause:** In this Codex shell environment, long gameplay runners did not survive reliably when detached through plain shell job control.
- **Use instead:** Launch detached gameplay runners through a small Python wrapper that uses `subprocess.Popen(..., start_new_session=True)` and writes pid/log files, following the same pattern as `runtime_doctor.py`.
- **Validation:** `agent-navigation/tools/launch_detached_runner.py` successfully kept the relaunched metals runner alive, and MrFlame resumed moving out of Al Kharid instead of staying idle at the bank.
