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
python3 agent-navigation/tools/script_registry.py run cowhide -- --stop-when-inventory-full --quiet
python3 agent-navigation/tools/script_registry.py run character-memory -- show --profile MrFlame --json
```

The catalog lives at `agent-navigation/data/script_registry.json`. Keep this skill context-light: add script metadata there, not here.

For new gameplay scripts, read `agent-navigation/scripting-primitives.md` and compose bridge primitives from Python before considering Java bridge changes.
