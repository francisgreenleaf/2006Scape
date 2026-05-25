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
python3 agent-navigation/tools/script_registry.py search "route*"
python3 agent-navigation/tools/script_registry.py show agility_runner --json
python3 agent-navigation/tools/script_registry.py run agility -- --target-agility-level 25
```

The catalog lives at `agent-navigation/data/script_registry.json`. Keep this skill context-light: add script metadata there, not here.
