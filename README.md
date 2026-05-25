# 2006Scape - an open source, actively developed emulation server. Pull requests welcome! ![Gameplay Image](https://i.imgur.com/WHnQz2W.png)

## Discord Link: https://discord.gg/hZ6VfWG

## How to Play

### Client/Launcher Download: https://2006Scape.org/
### Rune-Server project thread: [Project thread](https://www.rune-server.ee/runescape-development/rs2-server/projects/686444-2006rebotted-remake-server-will-allow-supply-creatable-bots.html)

# About This Fork

This fork adds a local Codex RuneScape agent bridge on top of the 2006Scape client and server. After logging into a local world, a player can type `/agent ...` in the normal chatbox to ask Codex to perform gameplay tasks through server-authoritative tools instead of screen automation or admin shortcuts.

The agent bridge currently supports:

- Local client-to-Codex app-server sessions started from the game client.
- A server-side HTTP bridge on `127.0.0.1:43610` that exposes only the logged-in player's scoped session.
- Dynamic `rs` tools for observing state, walking to known landmarks, dialogue/object interaction, NPC combat, food use, shops, banking, mining, woodcutting, smelting, and smithing.
- Server-side batch tools for long-running actions such as landmark travel, tile walking, mining to a full inventory, woodcutting to a full inventory, and waiting until movement/skilling/combat activity settles. These avoid slow one-tick polling from the client or in-app chat.
- Combat-training planning toward melee goals, including training-style selection, safer target choice, food thresholds, gear recommendations, and excess-coin banking.
- Starter world knowledge for Lumbridge, Varrock, Barbarian Village, Al Kharid shops, Falador, rock crabs, banks, mines, trees, and combat areas.
- Agent session logs under `2006Scape Server/data/logs/agent-sessions/<yyyy-MM-dd>/`, with raw JSONL events and a readable Markdown summary.

The bridge is intentionally constrained. Agent actions go through existing game mechanics such as walking, combat, shops, banking, mining, and smithing. It does not add admin teleports, item spawning, direct player-stat edits, or screen automation.

For a contributor-oriented summary of the fork work, see [canvrno's additions so far](docs/canvrno-additions.md).

# Installation + Running (Developers)

## One-command local launch on macOS

From the repository root:

```sh
./scripts/run-local.sh
```

This builds both Maven modules, starts the server from `2006Scape Server`, waits for the local game port, and launches the client with `-local -s localhost`. Closing the client stops the background server process started by the script.

The server uses `2006Scape Server/ServerConfig.json` when it exists, otherwise it falls back to `2006Scape Server/ServerConfig.Sample.json`. To use a specific config:

```sh
SERVER_CONFIG="2006Scape Server/ServerConfig.Sample.json" ./scripts/run-local.sh
```

Useful focused scripts:

```sh
./scripts/build-local.sh
./scripts/start-server.sh
./scripts/start-client.sh
```

`start-server.sh` copies the built server jar to `/tmp/2006scape-run/` before launching it. Keep that behavior on during local work: do not run the live server directly from `2006Scape Server/target/server-1.0-jar-with-dependencies.jar` while rebuilding with Maven, because replacing a jar under a running Java 8 process can crash lazy class loading.

Launcher JVM options can be passed through environment variables:

```sh
SERVER_JAVA_OPTS="-Dsun.zip.disableMemoryMapping=true" ./scripts/start-server.sh
CLIENT_JAVA_OPTS="-Dsun.java2d.uiScale=2" ./scripts/start-client.sh -u "MrFlame"
CLIENT_SINGLE_INSTANCE=0 ./scripts/start-client.sh -u "MrGem"
```

The client also supports a repo-native scale flag that doubles the game canvas while preserving normal in-game mouse coordinates:

```sh
./scripts/start-client.sh -u "MrFlame" -scale 2 -no-nav
```

Client arguments can be appended to either client launcher, for example:

```sh
./scripts/run-local.sh -u myname -p mypass
```

For current agent testing, prefill the default local profile, or choose another profile explicitly:

```sh
./scripts/run-local.sh -u "MrFlame"
./scripts/run-local.sh -u "MrGem"
```

For Codex-controlled exploration where repo tools such as `agent-navigation/tools/rs-tool.sh` need an active bridge session, use the dedicated startup runbook:

- [Local Agent Startup](docs/local-agent-startup.md)

## Using the Codex Agent Bridge

Prerequisites:

- Build and run both modules locally.
- Start the client with `-local`, `-dev`, or `-offline` so it connects to localhost and disables CRC checking.
- Log into a local account before using `/agent`.
- Have the Codex CLI/app-server available on your `PATH`; the client launches `codex app-server --listen stdio://` when an agent session starts.

Basic flow:

1. Start the local server and client:

   ```sh
   ./scripts/run-local.sh -u "MrFlame"
   ```

   For another profile, use that profile name and set `RS_PROFILE=<name>` for repo-side bridge tools.

2. Log into the game world.
3. Type `/agent key` once per local setup and enter your API key in the Swing password dialog. The key is passed to Codex auth and is not written to repository files.
4. Type `/agent status` to confirm the app-server, auth, and session state.
5. Type a task, for example:

   ```text
   /agent travel to varrock east bank
   /agent mine iron ore and bank it
   /agent smelt bronze bars
   /agent train combat safely toward 50 attack strength and defence
   /agent buy kebabs, bank extra coins, then train on a safe nearby target
   ```

6. Use `/agent stop` to interrupt the active turn and clear the current server-side action.

Agent sessions are local gameplay runs. The model is expected to observe first, prefer server-side batch tools for repeated travel and resource gathering, use `wait_until_idle` for production batches such as smelting or smithing, and adapt to game state such as missing tools, low hitpoints, full inventory, unreachable targets, closed interfaces, or insufficient skill levels.

Current navigation work is tracked in `agent-navigation/`. That folder stores places, route memories, hazards, route tests, and live observations. The most recent focus is safe travel, including run-energy requirements around south Varrock and the verified Varrock square to Champions' Guild stairs route.

To discover repo helper scripts without knowing exact filenames, use the lightweight registry:

```sh
python3 agent-navigation/tools/script_registry.py search "route*"
python3 agent-navigation/tools/script_registry.py show agility --json
```

Useful checks while developing the bridge:

```sh
mvn -q clean test
mvn -q -DskipTests package
```

1. Import Project in IntelliJ

2. Hit File > Project Settings > Set SDK to Java 8 (Download [Java 8 SDK](https://adoptopenjdk.net/?variant=openjdk8) if you don't have one already)

3. Navigate to `2006Scape Server` > `src` > `main` > `java` > `com.rs2`, right click GameEngine and hit Run [Image](https://i.imgur.com/HHooeVu.png)

   [(You Can Also Run The Server With The -c/-config Argument)](https://wiki.2006scape.org/books/getting-setup/page/server-arguments)
5. Navigate to `2006Scape Client` > `src` > `main` > `java`, right click Client and hit Run [Image](https://i.imgur.com/gSmqGLn.png)

*Advanced*

To compile any module from the command line, run `mvn clean install`

## Using Parabot with your local server:
- **1:** Download the latest Parabot Client from [here](https://github.com/2006-Scape/Parabot/releases)
- **2:** Run the parabot client with the following arg:
```fix
java -jar Parabot.jar -local
```
- **3:** ???
- **4:** PROFIT

### Server source layout

- `2006Scape Server` contains all the server code; mark `src` as the Sources directory
- `2006Scape Client` contains all the client code; likewise mark `src`
  - If more than 2 arguments are passed in (can be anything), the client runs locally

## Building from command line

Run `mvn -B clean install`
