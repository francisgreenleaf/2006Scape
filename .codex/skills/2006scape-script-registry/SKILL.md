---
name: 2006scape-script-registry
description: Use when an agent needs to discover, search, identify, or run existing 2006Scape helper scripts without loading broad repo context, including fuzzy/wildcard script lookup, metadata descriptions, and registered script execution through agent-navigation/tools/script_registry.py.
---

# 2006Scape Script Registry

Use the registry first when you need a repo helper script but do not know its exact name.

Commands:

```sh
python3 agent-navigation/tools/script_registry.py list
python3 agent-navigation/tools/script_registry.py search "agility"
python3 agent-navigation/tools/script_registry.py search "mining"
python3 agent-navigation/tools/script_registry.py search "fletching"
python3 agent-navigation/tools/script_registry.py search "woodcutting"
python3 agent-navigation/tools/script_registry.py search "combat"
python3 agent-navigation/tools/script_registry.py search "food"
python3 agent-navigation/tools/script_registry.py search "smithing"
python3 agent-navigation/tools/script_registry.py search "bank"
python3 agent-navigation/tools/script_registry.py search "chat"
python3 agent-navigation/tools/script_registry.py search "backup"
python3 agent-navigation/tools/script_registry.py search "deployment"
python3 agent-navigation/tools/script_registry.py search "external"
python3 agent-navigation/tools/script_registry.py search "client"
python3 agent-navigation/tools/script_registry.py search "tls tunnel"
python3 agent-navigation/tools/script_registry.py search "proof"
python3 agent-navigation/tools/script_registry.py search "cowhide"
python3 agent-navigation/tools/script_registry.py search "memory"
python3 agent-navigation/tools/script_registry.py search "route*"
python3 agent-navigation/tools/script_registry.py show agility_runner --json
python3 agent-navigation/tools/script_registry.py show mining_runner --json
python3 agent-navigation/tools/script_registry.py show fletching_runner --json
python3 agent-navigation/tools/script_registry.py show woodcutting_runner --json
python3 agent-navigation/tools/script_registry.py show combat_runner --json
python3 agent-navigation/tools/script_registry.py show food_runner --json
python3 agent-navigation/tools/script_registry.py show smithing_runner --json
python3 agent-navigation/tools/script_registry.py show bank-loadout --json
python3 agent-navigation/tools/script_registry.py show agent_chat_xs --json
python3 agent-navigation/tools/script_registry.py show runtime_data_backup --json
python3 agent-navigation/tools/script_registry.py show desktop_client_proof --json
python3 agent-navigation/tools/script_registry.py show deployment_proof_bundle --json
python3 agent-navigation/tools/script_registry.py show external_deployment_prepare --json
python3 agent-navigation/tools/script_registry.py show standalone_client_package --json
python3 agent-navigation/tools/script_registry.py show player_kit_package --json
python3 agent-navigation/tools/script_registry.py show player_kit_verify --json
python3 agent-navigation/tools/script_registry.py show client_tls_tunnel_config --json
python3 agent-navigation/tools/script_registry.py show server_deployment_files --json
python3 agent-navigation/tools/script_registry.py show external_deployment_verify --json
python3 agent-navigation/tools/script_registry.py show deployment_network_probe --json
python3 agent-navigation/tools/script_registry.py show deployment_readiness_report --json
python3 agent-navigation/tools/script_registry.py show deployment_proof_manifest_check --json
python3 agent-navigation/tools/script_registry.py show external_account_create --json
python3 agent-navigation/tools/script_registry.py show external_account_admin --json
python3 agent-navigation/tools/script_registry.py show game_login_probe --json
python3 agent-navigation/tools/script_registry.py show concurrent_login_probe --json
python3 agent-navigation/tools/script_registry.py show agent_chat_log_verify --json
python3 agent-navigation/tools/script_registry.py show discord_channel_message_verify --json
python3 agent-navigation/tools/script_registry.py show discord_agent_probe --json
python3 agent-navigation/tools/script_registry.py show cowhide_combat_runner --json
python3 agent-navigation/tools/script_registry.py show character-memory --json
python3 agent-navigation/tools/script_registry.py run agility -- --target-agility-level 25
python3 agent-navigation/tools/script_registry.py run mining -- --target-mining-level 20 --auto-buy-bronze-pickaxe
python3 agent-navigation/tools/script_registry.py run fletching -- --target-fletching-level 50 --quiet
python3 agent-navigation/tools/script_registry.py run woodcutting -- --tree oak --stop-when-inventory-full --quiet
python3 agent-navigation/tools/script_registry.py run combat -- --npc goblin --target-level 10 --quiet
python3 agent-navigation/tools/script_registry.py run food -- --mode fish-cook --quiet
python3 agent-navigation/tools/script_registry.py run smithing -- --mode smith --item sword --amount 10
python3 agent-navigation/tools/script_registry.py run bank-loadout -- --preset cowhide-trip --dry-run --json
python3 agent-navigation/tools/script_registry.py run agent chat -- --profile PROFILE status --since-id 0
read -s ACCOUNT_PASSWORD && export ACCOUNT_PASSWORD && python3 agent-navigation/tools/script_registry.py run external_account_create -- ExternalTest --password-env ACCOUNT_PASSWORD --allowed-character ExternalTest
read -s ACCOUNT_PASSWORD && export ACCOUNT_PASSWORD && python3 agent-navigation/tools/script_registry.py run external_account_create -- ExternalTest --password-env ACCOUNT_PASSWORD --overwrite --preserve-metadata
python3 agent-navigation/tools/script_registry.py run external_account_admin -- --require-password-policy audit
python3 agent-navigation/tools/script_registry.py run runtime_data_backup -- --data-dir "2006Scape Server/data" --proof-manifest dist/external-deployment/deployment-proof-manifest.json
python3 agent-navigation/tools/script_registry.py run desktop_client_proof -- --same-host-client LocalTest --external-client ExternalTest --transport tailscale --public-host HOST --evidence /path/to/evidence.png --proof-manifest dist/external-deployment/deployment-proof-manifest.json
python3 agent-navigation/tools/script_registry.py run deployment_proof_bundle -- --prepared-dir dist/external-deployment --require-full-proof
python3 agent-navigation/tools/script_registry.py run prepare external deployment -- --config "2006Scape Server/ServerConfig.json"
CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.json" python3 agent-navigation/tools/script_registry.py run package client
python3 agent-navigation/tools/script_registry.py run player kit -- PLAYER --character CHARACTER --prepared-dir dist/external-deployment
python3 agent-navigation/tools/script_registry.py run verify player kit -- --kit dist/external-deployment/player-kit-PLAYER.zip --prepared-dir dist/external-deployment --username PLAYER --character CHARACTER
python3 agent-navigation/tools/script_registry.py run client tls tunnel -- --config "2006Scape Server/ServerConfig.json" --output-dir dist/client-tls-tunnel-operator
python3 agent-navigation/tools/script_registry.py run server deployment files -- --config "2006Scape Server/ServerConfig.json" --output-dir dist/server-deployment
python3 agent-navigation/tools/script_registry.py run network proof -- --config "2006Scape Server/ServerConfig.json"
python3 agent-navigation/tools/script_registry.py run deployment readiness -- --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --client-tls-tunnel-dir dist/client-tls-tunnel-operator
python3 agent-navigation/tools/script_registry.py run deployment readiness -- --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live --update-proof-manifest dist/external-deployment/deployment-proof-manifest.json
python3 agent-navigation/tools/script_registry.py show deployment_readiness_status --json
python3 agent-navigation/tools/script_registry.py run deployment_readiness_status -- --prepared-dir dist/external-deployment --show-next-commands
python3 agent-navigation/tools/script_registry.py run proof manifest check -- dist/external-deployment/deployment-proof-manifest.json --require-full-proof
python3 agent-navigation/tools/script_registry.py run concurrent login proof -- --external-host HOST --external-username EXTERNAL_TEST --external-password-env EXTERNAL_PASSWORD --local-username LOCAL_TEST --local-password-env LOCAL_PASSWORD
python3 agent-navigation/tools/script_registry.py run agent chat log proof -- --text-contains MARKER --from-type discord --from-bot false --channel agent --proof-manifest dist/external-deployment/deployment-proof-manifest.json
python3 agent-navigation/tools/script_registry.py run agent chat log proof -- --event agent_chat_player_delivery --text-contains MARKER --to-type player --to-name PLAYER --delivered-to PLAYER --no-undelivered --channel agent --proof-manifest dist/external-deployment/deployment-proof-manifest.json
python3 agent-navigation/tools/script_registry.py run discord channel proof -- --text-contains MARKER --agent PROFILE --proof-manifest dist/external-deployment/deployment-proof-manifest.json
python3 agent-navigation/tools/script_registry.py run cowhide -- --stop-when-inventory-full --quiet
python3 agent-navigation/tools/script_registry.py run character-memory -- show --profile PROFILE --json
```

The catalog lives at `agent-navigation/data/script_registry.json`. Keep this skill context-light: add script metadata there, not here.

For new gameplay scripts, read `agent-navigation/scripting-primitives.md` and compose bridge primitives from Python before considering Java bridge changes.
