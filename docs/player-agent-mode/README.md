# Playing 2006Scape With Codex Agents

This README describes the player experience for joining a shared
2006Scape server and optionally letting Codex control your logged-in character.
The server address, packaged client download, account name, password, and agent
gateway URL are supplied privately by the server operator. Do not commit private
server hosts, account passwords, bridge tokens, API keys, or deployment secrets.

The goal is a simple setup:

- Download the client, log in, and play normally.
- Or download the client, log in, and use `/agent ...` from inside the game.
- Or clone the repo, open Codex in the repo, and let that Codex thread control
  your logged-in character through the repo tools and skills.

## What You Need

For normal play:

- Java 8 or newer.
- A packaged 2006Scape client from the server operator.
- A username and password created for this server.
- The server host or client package configured by the operator.

For agent play:

- A Codex/OpenAI API key or an already-authenticated Codex installation.
- An agent gateway URL supplied by the server operator.
- A logged-in 2006Scape character. The agent can only control the character
  whose game session claimed the agent bridge.

## Option 1: Download Client And Play

1. Unzip the packaged client.
2. Run the setup checker:

   ```sh
   ./check-setup-macos-linux.sh
   ```

   On macOS you can also double-click `Check-Setup.command`. On Windows, run
   `check-setup-windows.bat`.

3. Launch the client:

   ```sh
   ./run-macos-linux.sh
   ```

   On macOS you can also double-click `Run-2006Scape.command`. On Windows, run
   `run-windows.bat`.

4. Log in with the username and password supplied by the server operator.
5. Play normally.

Use a password unique to this 2006Scape server. Do not reuse a RuneScape.com
password or a password from another service.

## Option 2: Use Agent Mode In The Game Client

This is the easiest agent flow for players who do not want to use repo scripts.
The Java client starts Codex locally and exposes game tools to that Codex turn.
The server still owns the game state, and every action is scoped to the logged-in
player that claimed the bridge.

1. Launch the packaged client and log in.
2. Check agent status from the in-game chatbox:

   ```text
   /agent status
   ```

3. If Codex needs authentication, enter your API key:

   ```text
   /agent key
   ```

4. Give the character a bounded gameplay task:

   ```text
   /agent travel to Lumbridge cows
   /agent mine iron ore and bank it
   /agent catch and cook food near Catherby
   /agent train combat safely for a while
   ```

5. Stop the active Codex turn if needed:

   ```text
   /agent stop
   ```

Behavior: the packaged client reads an `agent.bridge.url` value from
`client.properties`, claims the logged-in player through the normal game
connection, and sends Codex tool calls to the operator's HTTPS agent gateway.
The raw local bridge port stays private on the server.

## Option 3: Clone The Repo And Let Codex Control Your Character

This is the power-user flow. You keep the game client open, but the Codex thread
running in the cloned repo uses the 2006Scape skills and repo tools directly.
This gives the agent richer navigation, runner, memory, map, and script context.

1. Clone the repo and open it in Codex.
2. Launch the packaged client and log in to your character.
3. In Codex, ask it to use the 2006Scape skill and claim your remote character.
4. Codex runs the remote claim helper:

   ```sh
   python3 agent-navigation/tools/remote_claim.py \
     --profile YOUR_CHARACTER \
     --bridge-url "$AGENT_BRIDGE_URL"
   ```

5. The helper prints a short claim command. Type exactly that command in the
   game client, for example:

   ```text
   ::agent claim ABCD-1234
   ```

   Older running servers that have not restarted onto the new alias can use the
   fallback command printed by the helper:

   ```text
   ::agentbridge claim ABCD-1234
   ```

6. The helper stores an ignored local session file under `agent-navigation/.local/`.
7. Codex can now use compact bridge tools and scripts for your character, for
   example:

   ```sh
   RS_PROFILE=YOUR_CHARACTER agent-navigation/tools/observe_XS.sh
   RS_PROFILE=YOUR_CHARACTER agent-navigation/tools/rs-tool_XS.sh bank_item_count '{"names":["coal","iron ore"]}'
   ```

For normal gameplay tasks, tell Codex what you want in plain English:

```text
Use the 2006scape skill. Control my logged-in character through the remote
bridge session and train fishing for a short safe run.
```

Behavior: Codex in the repo uses the same scoped server bridge as the
in-client flow, but it controls the player from the repo's scripts instead of
from the Java client's embedded Codex app-server.

## Operator Gateway Setup

The raw bridge still belongs on loopback only:

```json
"agent_bridge_bind_host": "127.0.0.1",
"agent_bridge_port": 43610
```

Expose only an HTTPS reverse proxy that forwards the approved `/agent/*`
endpoints to that loopback bridge:

```sh
scripts/render-agent-bridge-gateway-config.py \
  --server-name agents.example.com \
  --cert-path /etc/letsencrypt/live/agents.example.com/fullchain.pem \
  --key-path /etc/letsencrypt/live/agents.example.com/privkey.pem \
  --output /etc/nginx/sites-available/2006scape-agent-bridge.conf
```

The generated Nginx template includes approved endpoint allow-listing, request
body caps, per-IP rate limits, forwarded-IP headers, and access logging. Enable
it with the normal Nginx site/symlink workflow, run `nginx -t`, reload Nginx,
and keep the host firewall closed for public TCP `43610`.

For packaged clients, set the public gateway URL during packaging or in the
server config used by the package:

```sh
CLIENT_AGENT_BRIDGE_URL=https://agents.example.com \
CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.json" \
scripts/package-client.sh
```

Config keys `agent_bridge_public_url`, `agent_bridge_url`, and
`agent_gateway_url` are also accepted by the package script. Do not put private
hosts, bearer tokens, account passwords, API keys, or secrets in tracked config.

After the remote server and gateway are intentionally running, prove the public
gateway is reachable and the raw bridge is still private:

```sh
scripts/probe-agent-bridge-gateway.py --gateway-url https://agents.example.com
```

To prove repo-side control end to end, claim a logged-in character and run a
harmless compact observe:

```sh
python3 agent-navigation/tools/remote_claim.py \
  --profile YOUR_CHARACTER \
  --bridge-url https://agents.example.com \
  --verify
RS_PROFILE=YOUR_CHARACTER agent-navigation/tools/observe_XXS.sh
```

## Safety Model

- A bridge session belongs to one logged-in player.
- A claim must be proven through that player's active game connection.
- Tool calls must use the scoped bridge token returned by the claim.
- The server executes gameplay actions through normal game mechanics and server
  ticks. Agents do not teleport, spawn items, edit stats, or bypass gameplay.
- The public path should be HTTPS. The raw local bridge port must not be exposed
  directly.
- Session files, passwords, API keys, and tokens stay local and ignored by git.

## Troubleshooting

If the client will not launch, run the setup checker first and confirm Java is on
your PATH.

If login fails, verify the username and password with the server operator. Account
passwords are managed by the operator, not by the in-game `::password` command.

If `/agent status` cannot connect to the bridge, confirm the client package has
the operator-provided agent gateway URL and that the server operator has enabled
remote agent mode.

If repo Codex tools fail with an invalid session, rerun the remote claim helper
and type the new claim command while your character is logged in.

If the agent is doing the wrong thing, use `/agent stop` in the client or ask
Codex to call `cancel_current_action` for the claimed profile.

## Live Proof Checklist

Before calling a deployment ready for player-agent mode, collect real proof that:

- the packaged client can log in through the configured game/cache path;
- `/agent status` in that packaged client reaches the configured HTTPS gateway;
- `/agent key`, `/agent stop`, and `/agent <task>` still use the same in-client UX;
- `remote_claim.py --verify` writes a profile-scoped ignored session file and
  completes `observe_state_XXS` through the gateway;
- `scripts/probe-agent-bridge-gateway.py` passes from an external network path;
- raw TCP `43610` is not reachable from the public network.
