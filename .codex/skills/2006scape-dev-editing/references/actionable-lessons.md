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

### Package from a clean target when archive creation stalls

- **Observed:** `scripts/validate-network-auth-chat.sh` passed focused tests and the full Maven test suite, then hung inside `mvn -q -DskipTests package` while Maven's jar archiver waited on stale duplicate numbered `.class` files under `2006Scape Server/target/classes`.
- **Cause:** The package step reused an old target directory containing generated/stale class artifacts that did not exist in source.
- **Use instead:** For branch-level package proof, run `mvn -q clean -DskipTests package` or make wrapper validators clean before packaging so the jar is built from current source output only.
- **Validation:** The clean package command should complete quickly and leave `2006Scape Server/target/server-1.0-jar-with-dependencies.jar` rebuilt.

### Clean before full-suite validation after focused Maven runs

- **Observed:** After focused module tests, `scripts/validate-network-auth-chat.sh` failed at the later full `mvn test` step with missing `com.rs2.game.players.Player` and `PacketType` symbols even though `Player.java` still existed and compiled in a focused clean server compile.
- **Cause:** The full-suite step reused an incomplete/stale `target/classes` tree left by earlier Maven invocations; `Client.class` existed but superclass `Player.class` did not.
- **Use instead:** In validation wrappers that run focused Maven checks before a broad suite, make the broad suite `mvn -q clean test` instead of plain `mvn -q test`.
- **Validation:** `scripts/validate-network-auth-chat.sh` should run the full Maven suite from a clean target and no longer fail from missing inherited `Player` fields.

### Check interaction tiles before treating a gate click as proof

- **Observed:** The Barbarian Outpost gate and pipe could be clicked, but the player would sometimes remain in place because the handler only recognized a narrow set of exact coordinates.
- **Cause:** The server-side transition logic was keyed to the object id and old hard-coded player tiles instead of the actual adjacent interaction tiles reported by live object search.
- **Use instead:** When debugging or adding gate-style transitions, verify the object id, the nearby `nearestInteractionTile`/`interactionWalkTarget`, and the expected post-tile before assuming a successful click means the transition worked.
- **Validation:** `mvn -q -pl "2006Scape Server" -Dtest=DoubleGatesTest test` covers the Agility 35 gate crossing and the unsupported-side fallback.

## Codex Agent Bridge

### Never interrupt another player to complete a trade

- **Observed:** During a cross-profile coin transfer, stopping the other profile's active Seers fletching runner and closing its interfaces made the trade faster but interrupted that player's productive work.
- **Cause:** The trade workflow treated "the other profile can be controlled" as permission to pause or repurpose that profile, instead of treating it as another player with its own active task.
- **Use instead:** Control only the selected profile. Send or answer trade requests from that profile and wait patiently for the other player to respond; if the other side is busy, poll compact trade status at human-scale intervals and report a blocker rather than cancelling actions, killing runners, banking, moving, or closing interfaces on the other profile.
- **Validation:** Before using `RS_PROFILE=OTHER_PROFILE` for live actions, confirm the user explicitly named that profile and asked you to take it over; otherwise no process or gameplay state belonging to the other profile should change.

### Runtime bridge changes need a restart before tool calls can prove them

- **Observed:** Adding a new bridge tool to Java source and client tool metadata compiles locally, but the currently running server/client keep using the old jar.
- **Cause:** The live bridge is served by the already-running JVM, not by modified source files.
- **Use instead:** Treat `mvn -q -DskipTests package` as compile validation only. Restart the server/client through `agent-navigation/tools/runtime_doctor.py` before testing new bridge tools through `agent-navigation/tools/rs-tool_XXS.sh` or `agent-navigation/tools/rs-tool_XS.sh`; use full `rs-tool.sh` only when compact proof omits a required field.
- **Validation:** After restart, call the new compact alias through `rs-tool_XXS.sh`/`rs-tool_XS.sh` and confirm the response shape matches the source change.

### Use trade primitives instead of generic trade-button clicks

- **Observed:** `click_interface_button_XS {"buttonId":13092}` could return `success:true` on a trade accept button while `trade_status_XS` still showed the player on the first trade screen.
- **Cause:** Trade accept cases live in the packet button handler path, while the generic bridge interface-button primitive only routes selected server interfaces and can acknowledge a click without invoking trade confirmation logic.
- **Use instead:** For player-to-player trades, use `request_player_trade_XS`, `offer_trade_item_XS`, `accept_trade_XS`, and `trade_status_XS`. `accept_trade_XS '{"expectPartner":"NAME","expectItemId":995,"minAmount":N}'` is the normal one-call agent accept and records auto-final intent; avoid manually clicking first and final trade-confirmation buttons except as an explicit stale-runtime debug fallback.
- **Validation:** `trade_status_XS` should progress through `first_screen`, `first_accepted`, `confirm_screen`, and completion, and `mvn -q -DskipTests package` should pass after bridge changes.

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
- **Validation:** `agent-navigation/tools/observe_XXS.sh` or `agent-navigation/tools/observe_XS.sh` returns `success:true` for the selected player.

### Use Python detached launch instead of shell backgrounding

- **Observed:** `nohup ./scripts/start-server.sh > /tmp/2006scape-server.log 2>&1 &` reported a PID but the server exited silently and no usable Java process remained.
- **Cause:** Background processes launched from transient Codex shell commands can lose the intended process/session ownership.
- **Use instead:** Use `agent-navigation/tools/runtime_doctor.py`, which launches server/client processes with Python `subprocess.Popen(..., start_new_session=True)` and writes pid/log files under predictable paths. If hand-launching is unavoidable, use the same Python detached-launch pattern.
- **Validation:** `runtime_doctor.py status --observe` shows both ports open and a valid selected-profile bridge session.

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

### Promote discovered doors into runner primitives

- **Observed:** `road_to_99_fishing_cooking.py` reached 25,000 coins but failed buying Cooking gauntlets because the route to Caleb's spawn tile stopped at the Catherby range area, and a nearby shop door was easy to confuse with Caleb's house door.
- **Cause:** The wrapper treated Caleb as an ordinary coordinate route instead of a building/object transition, and compact object search returned the nearest door rather than the intended house entrance.
- **Use instead:** When a runner fails near a door or object blocker, inspect `2006Scape Server/data/doors.json`, context-map markers, compact object search, and live post-state to identify the exact object. Then add a location helper in `bridge_script.py` and call it from the runner instead of leaving a manual recovery path.
- **Validation:** `bridge_script.enter_catherby_caleb_house(...)` now opens Door `1530` at `2815,3448,0`, steps to `2816,3448,0`, and the Road-to-99 wrapper uses Caleb's purchase button `9157` before equipping item `775`.

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

### Use tiny shutdown status for cooperative stop polling

- **Observed:** Polling Seers runner `--status` while waiting for a cooperative stop repeatedly dumped full JSON payloads with player, args, counts, and route fields into Codex context.
- **Cause:** The diagnostic status surface was reused as a high-frequency stop check, even though the agent only needed to know whether the stop file had been honored and the runner had reached a terminal phase.
- **Use instead:** For cooperative long runners, keep `--status` for occasional diagnosis, use `--request-stop` to ask for a safe-boundary stop, and poll a tiny `--shutdown-status`/XS control wrapper that reports only `phase`, `stopRequested`, `shutdownComplete`, `pid`, and `updatedAt`.
- **Validation:** `python3 agent-navigation/tools/seers_yew_longbow_runner.py --profile PROFILE --shutdown-status` prints one compact JSON line instead of the full runner status blob.

### Launching the GUI client from Codex requires escalation; sandboxed claim runs can fake progress

- **Observed:** `runtime_doctor.py claim` could print `client_starting ...` and leave only `Launching 2006Scape client against localhost...` in `/tmp/2006scape-client.log`, but never create `agent-navigation/.local/rsbridge-session.json` or connect the player.
- **Cause:** The launcher shell script can run inside the sandbox, but the actual GUI client launch needs to happen outside the sandbox; otherwise the bridge claim loop waits on a client that never really comes up.
- **Use instead:** When recovering a dead bridge session from Codex, run `python3 agent-navigation/tools/runtime_doctor.py claim --profile ... --verify` with escalated permissions so the Java client can actually open and log in.
- **Validation:** The escalated claim path produced `session_ready ...`, `observe_slim_ok`, and a fresh default session file, while repeated sandboxed claim attempts never did.

### Sandboxed `pgrep`/`pkill` can miss live client processes on this macOS setup

- **Observed:** `start-client.sh` and `runtime_doctor.py` emitted `sysmond service not found` / `Cannot get process list`, failed to detect an existing client, and allowed stale client instances to keep the selected profile logged in.
- **Cause:** macOS process enumeration from the sandbox is incomplete here, so `pgrep -f client-1.0-jar-with-dependencies.jar` is not reliable for single-instance enforcement or cleanup.
- **Use instead:** Prefer the tracked client pid files for first-pass cleanup, and if the server still shows the player online, use an escalated `pkill -f client-1.0-jar-with-dependencies.jar` before retrying the bridge claim.
- **Validation:** After the elevated `pkill`, the server log showed the selected profile deregistered and `Players: 0`, which allowed the next escalated claim to succeed cleanly.

### Keep profile client relaunches scoped to that profile

- **Observed:** While hardening multi-character support, `runtime_doctor.py claim --profile PROFILE` and non-runtime `--replace-client` flows could still choose broad client cleanup for the default profile, which would stop another profile's active client.
- **Cause:** The helper treated the legacy default profile as a single-client runtime and delegated to process-pattern cleanup instead of only the selected profile's pid file.
- **Use instead:** For profile-scoped `claim` or client replacement, stop only `agent-navigation/.local/client.pid` or `client-<profile>.pid` for the selected profile, and launch with `CLIENT_SINGLE_INSTANCE=0`; reserve broad process cleanup for explicit full `--replace-runtime` work.
- **Validation:** `python3 agent-navigation/tools/runtime_doctor.py status --profile PROFILE` reports `client-<profile>.pid` and `/tmp/2006scape-client-<profile>.log`, while `mvn -q -DskipTests package` and focused bridge tests still pass.

### Target remote claims by character-titled windows

- **Observed:** During VPS multi-character testing, a fresh `remote_claim.py --profile MrFlame --verify` command was typed into the wrong Java client because both windows previously had the same generic title, and the AppleScript targeted the last Java process.
- **Cause:** Window-order targeting is ambiguous when several 2006Scape clients are open; a valid claim nonce proves whichever logged-in client receives it, not the profile the operator intended.
- **Use instead:** Use a client build that shows the logged-in character in the title bar, such as `2006Scape - MrFlame World: 1`, and target the window whose title contains the requested profile. If the helper reports a claimed-player mismatch, discard that nonce and rerun `remote_claim.py` for a fresh claim.
- **Validation:** `osascript` listing of Java windows should show distinct character titles before typing the claim, and `remote_claim.py --verify` should report the expected claimed player.

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

### Prefer nearby Brimhaven progress over far approach walks

- **Observed:** `agent-navigation/tools/agility_brimhaven_runner.py` could spend 6-9 ticks oscillating while walking toward a farther preferred obstacle, then fallback-click a nearby obstacle that moved away from the next dispenser or repeated a weak rope/handhold edge.
- **Cause:** The scorer overvalued avoiding recent objects/tiles and the failed-approach fallback treated any nearby click as useful recovery, even when `targetDistanceDelta` was positive.
- **Use instead:** Keep per-choice `currentTargetDistance`, `predictedTargetDistance`, and `targetDistanceDelta` in logs; after a failed approach, prefer a safe nearby candidate with negative target-distance delta and suppress nearby fallbacks only when they combine away movement with loop-risk or repeated-edge penalties.
- **Validation:** A fresh Brimhaven sample after the fallback suppression showed steady XP and saved tickets with `fallbackClicks:0` during the clean window; a follow-up check caught over-suppression, so the final guard allows small non-looping away fallbacks while still blocking repeated away edges.

### Resume bank material loops from carried state, not assumed empty state

- **Observed:** The Guam cleaner failed after withdrawing a full inventory of grimy herbs, then immediately tried to continue the bank loop and raised `No inventory space available`.
- **Cause:** The script assumed each loop iteration started from an empty inventory and bank-ready interface instead of handling already-carried materials first.
- **Use instead:** For bank-side conversion/cleanup loops, first detect carried work items, close interfaces, process them, re-observe with XS or a focused helper such as `food_bank_XS`, then reopen or resume banking. Use full state only if compact output lacks a specific required field.
- **Validation:** The patched herb-cleaning flow can restart mid-trip with a full carried inventory and continue depositing cleaned output instead of failing on the next withdrawal.

### Prove exact-tick production waits before trusting optimistic counts

- **Observed:** An optimized yew-longbow stringing loop in `agent-navigation/tools/yew_longbow_stringer.py` waited a guessed exact tick count, assumed all 14 bows were done, and banked with 8 finished yew longbows plus 6 unstrung bows and 6 bow strings still in inventory.
- **Cause:** `wait_ticks_XS` timing did not map cleanly to the server skill event cadence, and optimistic post-wait counts hid an under-waited inventory.
- **Use instead:** Calibrate exact waits against live run logs, keep a fallback that checks the compact wait result for unfinished inputs, and verify bank/product deltas before removing idle waits from production loops.
- **Validation:** A proof cycle should deposit only the finished product id, with no remaining input ids in `deposit_relevant_inventory`, before launching a long `screen` runner.

### Keep full observe out of runner hot loops

- **Observed:** Mining and Seers woodcutting runners repeatedly did `wait_until_idle_XS -> observe_state -> find_nearest_rock/tree`, creating large raw logs even though the script only needed free slots, tile, skills, and compact inventory.
- **Cause:** Local runner helpers and old `bridge_script.observe()` treated full `observe_state` as the easy default, so narrow helper calls inherited a full-state refresh before every resource interaction.
- **Use instead:** Use `observe_xs()`/`observe_xxs()` or the compact `observe()` compatibility alias, carry forward compact `player` results from wait/action tools, and reserve `observe_full()` for complete bank/equipment/evidence fields. Direct `rs-tool.sh observe_state` now requires `RS_ALLOW_FULL_OBSERVE=1` for explicit debug/evidence work.
- **Validation:** `python3 -m py_compile agent-navigation/tools/bridge_script.py agent-navigation/tools/route_runner.py agent-navigation/tools/route_recorder.py agent-navigation/tools/observe_slim.py agent-navigation/tools/cowhide_combat_runner.py agent-navigation/tools/marathon_runner.py agent-navigation/tools/combat_trip_lib.py agent-navigation/tools/execute_route_definition.py agent-navigation/ml2-routing/tools/execute_route_definition.py agent-navigation/tools/rs-tool_XS.py` and `git diff --check` pass after migrating hot loops.

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

- **Observed:** Launching `al_kharid_metals_runner.py` with shell backgrounding returned a pid, but the process died immediately and left the selected profile idle at `3270,3167,0`.
- **Cause:** In this Codex shell environment, long gameplay runners did not survive reliably when detached through plain shell job control.
- **Use instead:** Launch detached gameplay runners through a small Python wrapper that uses `subprocess.Popen(..., start_new_session=True)` and writes pid/log files, following the same pattern as `runtime_doctor.py`.
- **Validation:** `agent-navigation/tools/launch_detached_runner.py` successfully kept the relaunched metals runner alive, and the selected profile resumed moving out of Al Kharid instead of staying idle at the bank.

### XS wrapper names must hit server aliases, not client-side full observes

- **Observed:** `observe_XS.sh` and `rs-tool_XS.sh observe_state ...` looked compact, but still called full `observe_state` and compacted the large result locally.
- **Cause:** The XS wrappers passed base tool names through `rs-tool.sh` instead of mapping known compact-capable names to server-side `_XS` aliases.
- **Use instead:** Keep `rs-tool_XS.py` mapping known aliases such as `observe_state`, `wait_until_idle`, and `walk_to_tile_until_arrived` to their `_XS` bridge tools; use full tool names only when compact output lacks a specific field.
- **Validation:** `python3 -m py_compile agent-navigation/tools/rs-tool_XS.py agent-navigation/tools/observe_XS.py agent-navigation/tools/xs_common.py` passes, and `xs_tool_name('observe_state')` returns `observe_state_XS`.

### Long production waits must account for the 25-tick bridge cap

- **Observed:** `yew_longbow_stringer.py` requested an 84-tick `wait_ticks_XS`, but the server capped the wait at 25 ticks, then the runner spent roughly 12 extra seconds in a fallback `wait_until_idle_XS`.
- **Cause:** `AgentActionService` clamps `wait_ticks` requests to `1..25` ticks, so a single long wait can return early while production is still active.
- **Use instead:** Chunk exact production waits into 25-tick-or-smaller `wait_ticks_XS` calls, log each chunk's wall time, and only use `wait_until_idle_XS` as a verified fallback. Avoid separate bank-open calls when the next deposit/withdraw primitive already opens the bank.
- **Validation:** A two-cycle yew-longbow stringing proof completed `14` bows per cycle with `25+17` tick chunks, no fallback wait, final deposits containing only item `855`, and a steady-state cycle of `28.2s` / about `1,787` bows per hour.

### Use launcher Docker discovery for Java 8 validation on macOS

- **Observed:** Docker Desktop was installed, but `docker compose run --rm rsps-2006scape-build` failed in the Codex shell because `docker` was not on `PATH`; using the bundled Docker CLI then failed to pull because `docker-credential-desktop` was also not on `PATH`.
- **Cause:** Docker Desktop for macOS can bundle the CLI, Compose plugin, and credential helper under `/Applications/Docker.app/Contents/Resources/` without exposing them to non-interactive shells.
- **Use instead:** Run `RUN_DOCKER_BUILD=1 scripts/validate-network-auth-chat.sh`; it calls `launcher_docker_compose`, which discovers Docker Desktop's bundled CLI/plugin and prepends the credential-helper directory when needed. If calling launcher functions directly, invoke them through Bash, for example `bash -lc 'source scripts/lib/launcher-common.sh && launcher_docker_compose run --rm rsps-2006scape-build'`; sourcing Bash helpers from the default zsh shell can fail with `bad substitution`.
- **Validation:** `bash -lc 'source scripts/lib/launcher-common.sh; launcher_docker_compose version'` returned Docker Compose v5.1.4, and `RUN_DOCKER_BUILD=1 scripts/validate-network-auth-chat.sh` completed the Docker Java 8 build successfully.

### Test final deployment proof with non-placeholder fixtures

- **Observed:** After `--require-full-proof` was hardened to reject source/test-only allowances, `scripts/validate-network-auth-chat.sh` failed because its partial-proof smoke still used the tracked sample config with `--allow-placeholder-network-config`.
- **Cause:** The smoke conflated two cases: a final-proof report that is missing live evidence, and a source-validation report that needs placeholder allowances.
- **Use instead:** Exercise missing-live-proof behavior with a temporary non-placeholder package/config, and keep placeholder/source-only allowance rejection as a separate expected-failure assertion.
- **Validation:** `RUN_DOCKER_BUILD=1 scripts/validate-network-auth-chat.sh` passed after the partial-proof smoke used the generated `client_tls_tunnel` fixture and the placeholder allowance check stayed separate.

### Refresh compact skill state after XXS recovery calls

- **Observed:** `agility_brimhaven_runner.py` logged one obstacle as gaining millions of Agility XP immediately after eating.
- **Cause:** `eat_best_food_XXS` returned only critical state and omitted `skills`, so the next before/after XP calculation treated the pre-action Agility XP as zero.
- **Use instead:** After XXS recovery calls such as food, refresh with `observe_xs()` before computing XP deltas or other skill-derived progress.
- **Validation:** `python3 -m py_compile agent-navigation/tools/agility_brimhaven_runner.py` passed, and the relaunched Brimhaven runner logged normal per-obstacle XP deltas while continuing live course progress.
