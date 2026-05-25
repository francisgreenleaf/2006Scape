# Custom Content

This package is the home for user-requested content that should not be mixed into the older core game-content classes. The server still needs a small amount of wiring in core handlers, but quest-specific and feature-specific behavior belongs here in standalone folders.

The goal is simple: new custom content should be easy to add, test, review, and remove without scattering one-off imports through `DialogueHandler`, `NpcActions`, `ObjectsActions`, `ItemOnNpc`, `Player`, or `PlayerSave`.

## Current Structure

```text
com/rs2/game/content/custom/
  CustomContent.java                 # Registry and dispatcher for custom content.
  CustomQuest.java                   # Interface implemented by custom quests.
  CustomQuestState.java              # Generic player quest-stage storage helper.
  quests/
    lumbridge/
      pantrypanic/
        PantryPanicQuest.java        # Standalone custom quest implementation.
```

Tests for this package live under:

```text
2006Scape Server/src/test/java/com/rs2/game/content/custom/
```

## Core Wiring Policy

Existing server code should know about the custom-content system, not about individual custom quests.

Acceptable core hooks look like this:

```java
if (CustomContent.handleNpcClick(player, npcType)) {
    return;
}
```

Avoid this in core classes:

```java
if (PantryPanicQuest.handleNpcClick(player, npcType)) {
    return;
}
```

The current generic hooks are:

- `CustomContent.handleDialogue(...)`
- `CustomContent.handleDialogueOption(...)`
- `CustomContent.handleNpcClick(...)`
- `CustomContent.handleObjectClick(...)`
- `CustomContent.handleItemOnNpc(...)`
- `CustomContent.sendQuestTabs(...)`
- `CustomContent.showQuestInformation(...)`
- `CustomContent.loadPlayerSaveValue(...)`
- `CustomContent.savePlayerQuestStages(...)`

If new custom content needs another server event, add one generic hook to `CustomContent` and one minimal call site in the relevant core handler. Do not add a custom quest import to the core handler.

## Adding A Custom Quest

Create a standalone folder by area and quest name:

```text
quests/<area>/<questname>/<QuestName>Quest.java
```

Implement `CustomQuest`:

```java
public final class ExampleQuest implements CustomQuest {
    public static final ExampleQuest INSTANCE = new ExampleQuest();

    private static final String KEY = "exampleQuest";

    @Override
    public String getKey() {
        return KEY;
    }

    @Override
    public boolean handleNpcClick(Player player, int npcType) {
        return false;
    }
}
```

Register it in `CustomContent`:

```java
private static final CustomQuest[] QUESTS = {
        PantryPanicQuest.INSTANCE,
        ExampleQuest.INSTANCE
};
```

The quest file should own its:

- quest name, button id, and quest-tab line id
- dialogue ids and dialogue flow
- NPC/object/item ids used by the quest
- stage constants
- reward logic
- quest journal text
- local helper methods

Keep these details out of core classes.

## Quest State And Saves

Custom quest progress is stored in `player.customQuestStages` through `CustomQuestState`.

Use:

```java
int stage = CustomQuestState.get(player, KEY);
CustomQuestState.set(player, KEY, NEXT_STAGE);
```

Do not add new fields like this to `Player`:

```java
public int exampleQuest;
```

Custom quest stages save as generic player-save keys:

```text
customQuestStage-exampleQuest = 3
```

For compatibility with old saves, a quest may accept a legacy key by overriding `handlesLegacySaveKey`. New content should not add new quest-specific cases to `PlayerSave`.

## Dialogue And Interaction Practices

Custom quest dialogue should be readable as a story and mechanically explicit:

- Use named constants for every dialogue id.
- Keep stage transitions close to the dialogue branch that causes them.
- Call `QuestAssistant.sendStages(player)` after changing a quest stage that affects the quest tab.
- Return `true` only when the custom content fully handled the event.
- Return `false` quickly for unrelated NPCs, objects, items, buttons, and dialogue ids.
- Prefer existing mechanics: inventory deletion/addition, dialogue handlers, quest rewards, skill XP, object boundaries, and normal NPC/object click paths.
- Do not teleport players, spawn admin items, or mutate state outside the normal server mechanics unless the quest specifically requires an established in-game behavior.

When using existing world objects, check both object id and location. A broad object id without a location check can hijack unrelated objects elsewhere in the world.

## Rewards

Reward code should be in the quest implementation and should be guarded against duplicate completion:

```java
if (stage(player) == COMPLETE) {
    player.getPacketSender().closeAllWindows();
    return;
}
```

If a custom quest grants quest points, include that count in `getQuestPoints()`. `QuestAssistant.MAXIMUM_QUESTPOINTS` includes custom quest points through `CustomContent.getTotalQuestPoints()`, so related systems and tests should use the constant instead of hard-coded totals.

## Testing Expectations

Every new custom quest should have a focused test. The test should prove both the standalone quest behavior and the integration points.

At minimum, test:

- the quest is registered in `CustomContent`
- quest-point contribution, if any
- quest journal / quest button dispatch
- start dialogue and option selection
- stage transitions
- item hand-ins or object clicks
- reward delivery
- save/load of `customQuestStage-*`
- unrelated hooks return `false`

Pantry Panic is covered by `CustomContentTest`, which drives the quest through the public `CustomContent` hooks rather than calling private helpers.

Useful commands from the repository root:

```sh
mvn -q -pl "2006Scape Server" -Dtest=CustomContentTest test
mvn -q -pl "2006Scape Server" test
git diff --check
```

These commands compile and test source code only. They do not restart the running server. Live gameplay validation requires rebuilding and restarting the runtime deliberately, which should only happen when requested.

## Review Checklist

Before finishing custom content work, check:

- Core classes only contain generic `CustomContent` calls.
- The custom quest is in its own area/name folder.
- No quest-specific fields were added to `Player`.
- No quest-specific save cases were added to `PlayerSave`.
- Stage keys are stable and lower camel case.
- Dialogue ids do not collide with another custom quest.
- Inventory/object/NPC checks fail closed for unrelated content.
- Rewards cannot be claimed twice.
- Tests cover the happy path and unrelated hook behavior.
- `git diff --check` passes.
