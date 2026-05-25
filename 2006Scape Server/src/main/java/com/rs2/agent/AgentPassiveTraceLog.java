package com.rs2.agent;

import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;
import java.util.UUID;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.rs2.Constants;
import com.rs2.game.content.skills.SkillHandler;
import com.rs2.game.objects.Objects;
import com.rs2.game.players.Player;
import com.rs2.world.Boundary;

import org.apollo.cache.def.ObjectDefinition;

public class AgentPassiveTraceLog {

    public static final AgentPassiveTraceLog INSTANCE = new AgentPassiveTraceLog();

    private static final Gson GSON = new Gson();
    private static final String LOG_DIR = "player-movement-traces";
    private static final int IDLE_HEARTBEAT_TICKS = 25;

    private final Object lock = new Object();
    private final Map<Integer, Snapshot> snapshots = new HashMap<Integer, Snapshot>();
    private final Map<Integer, PendingMovement> pendingMovements = new HashMap<Integer, PendingMovement>();
    private final Map<Integer, ObjectInteraction> pendingObjectInteractions = new HashMap<Integer, ObjectInteraction>();
    private File logDirectoryForTests;

    public void captureBeforeMovement(Player player, long serverTick) {
        if (player == null || player.playerName == null || player.playerName.trim().isEmpty()) {
            return;
        }
        synchronized (lock) {
            pendingMovements.put(player.playerId, new PendingMovement(serverTick, player.absX, player.absY,
                    player.heightLevel, safeHitpoints(player), safeRunEnergy(player)));
        }
    }

    public void recordAfterUpdate(Player player, long serverTick) {
        if (player == null || player.playerName == null || player.playerName.trim().isEmpty()) {
            return;
        }
        PendingMovement pending;
        synchronized (lock) {
            pending = pendingMovements.remove(player.playerId);
        }
        if (pending == null) {
            recordTick(player, serverTick, player.absX, player.absY, player.heightLevel, safeHitpoints(player),
                    safeRunEnergy(player));
            return;
        }
        recordTick(player, pending.serverTick, pending.x, pending.y, pending.height, pending.hitpoints,
                pending.runEnergy);
    }

    public void recordTick(Player player, long serverTick, int previousX, int previousY, int previousHeight,
            int previousHitpoints, int previousRunEnergy) {
        if (player == null || player.playerName == null || player.playerName.trim().isEmpty()) {
            return;
        }

        int hitpoints = safeHitpoints(player);
        int runEnergy = safeRunEnergy(player);
        boolean moved = previousX != player.absX || previousY != player.absY || previousHeight != player.heightLevel;
        boolean teleported = player.didTeleport;
        boolean inCombat = isInCombat(player);
        String activityHash = activityHash(player, moved, inCombat);

        synchronized (lock) {
            Snapshot previous = snapshots.get(player.playerId);
            boolean shouldWrite = shouldWrite(previous, serverTick, moved, teleported, hitpoints, runEnergy, inCombat,
                    activityHash, player.isDead);
            snapshots.put(player.playerId, new Snapshot(player.absX, player.absY, player.heightLevel, hitpoints,
                    runEnergy, inCombat, activityHash, player.isDead, shouldWrite ? serverTick
                            : previous == null ? serverTick : previous.lastWrittenTick));
            if (!shouldWrite) {
                return;
            }
            JsonObject event = buildEvent(player, serverTick, previousX, previousY, previousHeight, previousHitpoints,
                    previousRunEnergy, hitpoints, runEnergy, moved, teleported, inCombat, activityHash);
            write(player, System.currentTimeMillis(), event);
        }
    }

    void recordForTests(Player player, long now, JsonObject event) {
        if (player == null || event == null || player.playerName == null || player.playerName.trim().isEmpty()) {
            return;
        }
        synchronized (lock) {
            write(player, now, event);
        }
    }

    void setLogDirectoryForTests(File directory) {
        synchronized (lock) {
            logDirectoryForTests = directory;
            snapshots.clear();
            pendingMovements.clear();
            pendingObjectInteractions.clear();
        }
    }

    void resetLogDirectoryForTests() {
        synchronized (lock) {
            logDirectoryForTests = null;
            snapshots.clear();
            pendingMovements.clear();
            pendingObjectInteractions.clear();
        }
    }

    public void recordObjectClickQueued(Player player, int objectOption, int packetOpcode, Objects object) {
        if (player == null || player.playerName == null || player.playerName.trim().isEmpty()) {
            return;
        }
        ObjectInteraction interaction = newObjectInteraction(player, objectOption, packetOpcode, object);
        synchronized (lock) {
            pendingObjectInteractions.put(player.playerId, interaction);
            JsonObject event = buildObjectEvent(player, interaction, "queued", player.absX, player.absY,
                    player.heightLevel);
            write(player, System.currentTimeMillis(), event);
        }
    }

    public void recordObjectClickCompleted(Player player, int objectId, int objectX, int objectY, int objectHeight,
            int objectOption, int beforeX, int beforeY, int beforeHeight, Objects object) {
        if (player == null || player.playerName == null || player.playerName.trim().isEmpty()) {
            return;
        }
        synchronized (lock) {
            ObjectInteraction interaction = pendingObjectInteractions.remove(player.playerId);
            if (interaction == null || !interaction.matches(objectId, objectX, objectY, objectHeight, objectOption)) {
                interaction = new ObjectInteraction(UUID.randomUUID().toString(), objectId, objectX, objectY,
                        objectHeight, objectOption, -1, object);
            } else if (object != null) {
                interaction = interaction.withObject(object);
            }
            JsonObject event = buildObjectEvent(player, interaction, "completed", beforeX, beforeY, beforeHeight);
            write(player, System.currentTimeMillis(), event);
        }
    }

    private boolean shouldWrite(Snapshot previous, long serverTick, boolean moved, boolean teleported, int hitpoints,
            int runEnergy, boolean inCombat, String activityHash, boolean isDead) {
        if (previous == null || moved || teleported || isDead) {
            return true;
        }
        if (previous.hitpoints != hitpoints || previous.runEnergy != runEnergy || previous.inCombat != inCombat) {
            return true;
        }
        if (!previous.activityHash.equals(activityHash)) {
            return true;
        }
        return serverTick - previous.lastWrittenTick >= IDLE_HEARTBEAT_TICKS;
    }

    private JsonObject buildEvent(Player player, long serverTick, int previousX, int previousY, int previousHeight,
            int previousHitpoints, int previousRunEnergy, int hitpoints, int runEnergy, boolean moved,
            boolean teleported, boolean inCombat, String activityHash) {
        JsonObject event = new JsonObject();
        event.addProperty("schemaVersion", 2);
        event.addProperty("source", "server-passive-player-tick");
        event.addProperty("event", eventName(player, moved, teleported, previousHitpoints, hitpoints, inCombat));
        event.addProperty("tool", "server_passive_tick");
        event.addProperty("controlSource", "server_tick");
        event.addProperty("serverTick", serverTick);
        event.addProperty("playerId", player.playerId);
        event.addProperty("playerName", player.playerName);
        event.addProperty("traceId", safeFileStem(player) + "-passive");
        event.add("tile", tile(player.absX, player.absY, player.heightLevel));
        event.add("previousTile", tile(previousX, previousY, previousHeight));
        if (moved || teleported) {
            event.addProperty("edgeKey", previousX + "," + previousY + "," + previousHeight
                    + "->" + player.absX + "," + player.absY + "," + player.heightLevel);
        }
        event.addProperty("moved", moved);
        event.addProperty("teleported", teleported);
        event.addProperty("mapRegionChanged", player.mapRegionDidChange);
        event.addProperty("dir1", player.dir1);
        event.addProperty("dir2", player.dir2);
        event.addProperty("runEnabled", player.isRunning2);
        event.addProperty("runEnergy", runEnergy);
        event.addProperty("runEnergyDelta", runEnergy - previousRunEnergy);
        event.addProperty("runEnergySpent", Math.max(0, previousRunEnergy - runEnergy));
        event.addProperty("hitpoints", hitpoints);
        event.addProperty("maxHitpoints", safeMaxHitpoints(player));
        event.addProperty("hitpointsDelta", hitpoints - previousHitpoints);
        event.addProperty("hitpointsLost", Math.max(0, previousHitpoints - hitpoints));
        event.addProperty("isDead", player.isDead);
        event.addProperty("isMoving", moved || player.dir1 != -1 || player.dir2 != -1 || player.isMoving);
        event.addProperty("isInCombat", inCombat);
        event.addProperty("npcIndex", player.npcIndex);
        event.addProperty("killingNpcIndex", player.killingNpcIndex);
        event.addProperty("underAttackBy", player.underAttackBy);
        event.addProperty("underAttackBy2", player.underAttackBy2);
        event.addProperty("foodCount", AgentToolService.countInventoryFood(player));
        event.addProperty("freeInventorySlots", player.getItemAssistant().freeSlots());
        event.addProperty("combatLevel", player.combatLevel);
        event.addProperty("fightMode", player.fightMode);
        event.addProperty("inBankArea", Boundary.isIn(player, Boundary.BANK_AREA));
        event.addProperty("inTrade", player.inTrade);
        event.addProperty("isShopping", player.isShopping);
        event.addProperty("dialogueAction", player.dialogueAction);
        event.addProperty("nextChat", player.nextChat);
        event.addProperty("talkingNpc", player.talkingNpc);
        event.addProperty("activityHash", activityHash);
        event.add("activity", activity(player, moved, inCombat));
        return event;
    }

    private JsonObject tile(int x, int y, int height) {
        JsonObject tile = new JsonObject();
        tile.addProperty("x", x);
        tile.addProperty("y", y);
        tile.addProperty("height", height);
        return tile;
    }

    private JsonObject activity(Player player, boolean moved, boolean inCombat) {
        JsonObject activity = new JsonObject();
        activity.addProperty("moving", moved || player.dir1 != -1 || player.dir2 != -1 || player.isMoving);
        activity.addProperty("runningStep", player.dir2 != -1);
        activity.addProperty("skilling", SkillHandler.isSkilling(player));
        activity.addProperty("mining", player.isMining);
        activity.addProperty("woodcutting", player.isWoodcutting);
        activity.addProperty("fishing", player.playerSkilling[Constants.FISHING] || player.playerIsFishing);
        activity.addProperty("cooking", player.playerIsCooking || player.playerSkilling[Constants.COOKING]);
        activity.addProperty("fletching", player.playerIsFletching || player.isFletching);
        activity.addProperty("crafting", player.isCrafting || player.playerSkilling[Constants.CRAFTING]);
        activity.addProperty("firemaking", player.isFiremaking);
        activity.addProperty("herblore", player.isPotionMaking || player.playerSkilling[Constants.HERBLORE]);
        activity.addProperty("smelting", player.isSmelting);
        activity.addProperty("smithing", player.isSmithing || player.playerSkilling[Constants.SMITHING]);
        activity.addProperty("banking", Boundary.isIn(player, Boundary.BANK_AREA));
        activity.addProperty("shopping", player.isShopping);
        activity.addProperty("trading", player.inTrade);
        activity.addProperty("dialogue", player.dialogueAction != 0 || player.nextChat != 0 || player.talkingNpc >= 0);
        activity.addProperty("combat", inCombat);
        return activity;
    }

    private ObjectInteraction newObjectInteraction(Player player, int objectOption, int packetOpcode, Objects object) {
        return new ObjectInteraction(UUID.randomUUID().toString(), player.objectId, player.objectX, player.objectY,
                player.heightLevel, objectOption, packetOpcode, object);
    }

    private JsonObject buildObjectEvent(Player player, ObjectInteraction interaction, String phase, int previousX,
            int previousY, int previousHeight) {
        int hitpoints = safeHitpoints(player);
        int runEnergy = safeRunEnergy(player);
        boolean moved = previousX != player.absX || previousY != player.absY || previousHeight != player.heightLevel;
        JsonObject event = new JsonObject();
        event.addProperty("schemaVersion", 2);
        event.addProperty("source", "server-passive-object-interaction");
        event.addProperty("event", "object_interaction");
        event.addProperty("tool", "server_passive_object_click");
        event.addProperty("controlSource", "object_packet");
        event.addProperty("traceId", interaction.traceId);
        event.addProperty("objectInteractionPhase", phase);
        event.addProperty("playerId", player.playerId);
        event.addProperty("playerName", player.playerName);
        event.add("tile", tile(player.absX, player.absY, player.heightLevel));
        event.add("previousTile", tile(previousX, previousY, previousHeight));
        if (moved || player.didTeleport) {
            event.addProperty("edgeKey", previousX + "," + previousY + "," + previousHeight
                    + "->" + player.absX + "," + player.absY + "," + player.heightLevel);
        }
        event.addProperty("moved", moved);
        event.addProperty("teleported", player.didTeleport);
        event.addProperty("runEnabled", player.isRunning2);
        event.addProperty("runEnergy", runEnergy);
        event.addProperty("hitpoints", hitpoints);
        event.addProperty("maxHitpoints", safeMaxHitpoints(player));
        event.addProperty("isDead", player.isDead);
        event.addProperty("isMoving", moved || player.dir1 != -1 || player.dir2 != -1 || player.isMoving);
        event.addProperty("isInCombat", isInCombat(player));
        event.addProperty("foodCount", AgentToolService.countInventoryFood(player));
        event.addProperty("freeInventorySlots", player.getItemAssistant().freeSlots());
        event.add("objectTile", tile(interaction.objectX, interaction.objectY, interaction.objectHeight));
        event.addProperty("objectId", interaction.objectId);
        String objectName = objectName(interaction.objectId);
        if (objectName != null && objectName.trim().length() > 0) {
            event.addProperty("objectName", objectName);
        }
        event.addProperty("option", optionName(interaction.objectOption));
        event.addProperty("objectOption", interaction.objectOption);
        if (interaction.packetOpcode >= 0) {
            event.addProperty("packetOpcode", interaction.packetOpcode);
        }
        event.addProperty("objectDistance", Math.max(Math.abs(player.absX - interaction.objectX),
                Math.abs(player.absY - interaction.objectY)));
        event.add("object", objectJson(interaction, objectName));
        return event;
    }

    private JsonObject objectJson(ObjectInteraction interaction, String objectName) {
        JsonObject object = new JsonObject();
        object.addProperty("objectId", interaction.objectId);
        object.addProperty("x", interaction.objectX);
        object.addProperty("y", interaction.objectY);
        object.addProperty("height", interaction.objectHeight);
        if (objectName != null && objectName.trim().length() > 0) {
            object.addProperty("name", objectName);
        }
        if (interaction.object != null) {
            object.addProperty("face", interaction.object.objectFace);
            object.addProperty("type", interaction.object.objectType);
            int[] size = safeObjectSize(interaction.object);
            object.addProperty("width", size[0]);
            object.addProperty("length", size[1]);
        }
        ObjectDefinition definition = objectDefinition(interaction.objectId);
        if (definition != null) {
            object.addProperty("definitionWidth", definition.getWidth());
            object.addProperty("definitionLength", definition.getLength());
            object.addProperty("interactive", definition.isInteractive());
            object.addProperty("solid", definition.isSolid());
            object.addProperty("clipped", definition.isClipped());
            object.addProperty("impenetrable", definition.isImpenetrable());
            object.addProperty("obstructive", definition.isObstructive());
            String[] actions = definition.getMenuActions();
            if (actions != null) {
                JsonArray actionArray = new JsonArray();
                for (String action : actions) {
                    if (action != null && action.trim().length() > 0) {
                        actionArray.add(action);
                    }
                }
                if (actionArray.size() > 0) {
                    object.add("actions", actionArray);
                }
            }
        }
        return object;
    }

    private ObjectDefinition objectDefinition(int objectId) {
        try {
            return ObjectDefinition.lookup(objectId);
        } catch (RuntimeException e) {
            return null;
        } catch (Error e) {
            return null;
        }
    }

    private String objectName(int objectId) {
        ObjectDefinition definition = objectDefinition(objectId);
        return definition == null ? null : definition.getName();
    }

    private int[] safeObjectSize(Objects object) {
        try {
            return object.getObjectSize();
        } catch (RuntimeException e) {
            return new int[] {1, 1};
        } catch (Error e) {
            return new int[] {1, 1};
        }
    }

    private String optionName(int objectOption) {
        switch (objectOption) {
        case 1:
            return "first";
        case 2:
            return "second";
        case 3:
            return "third";
        case 4:
            return "fourth";
        case 5:
            return "fifth";
        default:
            return "unknown";
        }
    }

    private String activityHash(Player player, boolean moved, boolean inCombat) {
        StringBuilder builder = new StringBuilder();
        builder.append(moved || player.dir1 != -1 || player.dir2 != -1 || player.isMoving).append('|');
        builder.append(player.dir2 != -1).append('|');
        builder.append(SkillHandler.isSkilling(player)).append('|');
        builder.append(player.isMining).append('|');
        builder.append(player.isWoodcutting).append('|');
        builder.append(player.playerSkilling[Constants.FISHING] || player.playerIsFishing).append('|');
        builder.append(player.playerIsCooking || player.playerSkilling[Constants.COOKING]).append('|');
        builder.append(player.playerIsFletching || player.isFletching).append('|');
        builder.append(player.isCrafting || player.playerSkilling[Constants.CRAFTING]).append('|');
        builder.append(player.isFiremaking).append('|');
        builder.append(player.isPotionMaking || player.playerSkilling[Constants.HERBLORE]).append('|');
        builder.append(player.isSmelting).append('|');
        builder.append(player.isSmithing || player.playerSkilling[Constants.SMITHING]).append('|');
        builder.append(Boundary.isIn(player, Boundary.BANK_AREA)).append('|');
        builder.append(player.isShopping).append('|');
        builder.append(player.inTrade).append('|');
        builder.append(player.dialogueAction != 0 || player.nextChat != 0 || player.talkingNpc >= 0).append('|');
        builder.append(inCombat);
        return builder.toString();
    }

    private String eventName(Player player, boolean moved, boolean teleported, int previousHitpoints,
            int hitpoints, boolean inCombat) {
        if (player.isDead) {
            return "player_dead";
        }
        if (teleported) {
            return "teleport";
        }
        if (hitpoints < previousHitpoints) {
            return "hitpoints_lost";
        }
        if (inCombat) {
            return "combat";
        }
        if (moved) {
            return "movement";
        }
        return "state";
    }

    private boolean isInCombat(Player player) {
        if (player.isDead || player.respawnTimer > 0) {
            return false;
        }
        return player.npcIndex > 0 || player.underAttackBy > 0 || player.underAttackBy2 > 0;
    }

    private int safeHitpoints(Player player) {
        return safeSkillLevel(player, Constants.HITPOINTS);
    }

    private int safeMaxHitpoints(Player player) {
        try {
            return player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.HITPOINTS]);
        } catch (RuntimeException e) {
            return safeHitpoints(player);
        }
    }

    private int safeSkillLevel(Player player, int skill) {
        if (skill >= 0 && skill < player.playerLevel.length) {
            return player.playerLevel[skill];
        }
        return 0;
    }

    private int safeRunEnergy(Player player) {
        return (int) Math.ceil(player.playerEnergy);
    }

    private void write(Player player, long now, JsonObject event) {
        event.addProperty("timestamp", timestamp(now));
        event.addProperty("timestampMs", now);
        File dayDirectory = new File(resolveLogDirectory(), dateStamp(now));
        if (!dayDirectory.exists() && !dayDirectory.mkdirs()) {
            System.err.println("Unable to create passive player trace directory: " + dayDirectory.getAbsolutePath());
            return;
        }
        File logFile = new File(dayDirectory, safeFileStem(player) + ".jsonl");
        try (BufferedWriter writer = Files.newBufferedWriter(logFile.toPath(), StandardCharsets.UTF_8,
                StandardOpenOption.CREATE, StandardOpenOption.APPEND)) {
            writer.write(GSON.toJson(event));
            writer.newLine();
        } catch (IOException e) {
            System.err.println("Unable to write passive player trace: " + e.getMessage());
        }
    }

    private File resolveLogDirectory() {
        if (logDirectoryForTests != null) {
            return logDirectoryForTests;
        }
        File defaultDirectory = new File(Constants.SERVER_LOG_DIR, LOG_DIR);
        File defaultParent = defaultDirectory.getParentFile();
        if (defaultParent == null || defaultParent.exists() || new File("data").isDirectory()) {
            return defaultDirectory;
        }
        File repoServerLogs = new File("2006Scape Server/data/logs");
        if (repoServerLogs.isDirectory()) {
            return new File(repoServerLogs, LOG_DIR);
        }
        return defaultDirectory;
    }

    private String safeFileStem(Player player) {
        String name = player.playerName == null || player.playerName.trim().isEmpty()
                ? "player-" + player.playerId
                : player.playerName.trim().toLowerCase(Locale.ENGLISH);
        return name.replaceAll("[^a-z0-9._-]+", "_");
    }

    private String timestamp(long now) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.ENGLISH);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(now));
    }

    private String dateStamp(long now) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd", Locale.ENGLISH);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(now));
    }

    private static class Snapshot {
        private final int x;
        private final int y;
        private final int height;
        private final int hitpoints;
        private final int runEnergy;
        private final boolean inCombat;
        private final String activityHash;
        private final boolean dead;
        private final long lastWrittenTick;

        private Snapshot(int x, int y, int height, int hitpoints, int runEnergy, boolean inCombat,
                String activityHash, boolean dead, long lastWrittenTick) {
            this.x = x;
            this.y = y;
            this.height = height;
            this.hitpoints = hitpoints;
            this.runEnergy = runEnergy;
            this.inCombat = inCombat;
            this.activityHash = activityHash == null ? "" : activityHash;
            this.dead = dead;
            this.lastWrittenTick = lastWrittenTick;
        }
    }

    private static class PendingMovement {
        private final long serverTick;
        private final int x;
        private final int y;
        private final int height;
        private final int hitpoints;
        private final int runEnergy;

        private PendingMovement(long serverTick, int x, int y, int height, int hitpoints, int runEnergy) {
            this.serverTick = serverTick;
            this.x = x;
            this.y = y;
            this.height = height;
            this.hitpoints = hitpoints;
            this.runEnergy = runEnergy;
        }
    }

    private static class ObjectInteraction {
        private final String traceId;
        private final int objectId;
        private final int objectX;
        private final int objectY;
        private final int objectHeight;
        private final int objectOption;
        private final int packetOpcode;
        private final Objects object;

        private ObjectInteraction(String traceId, int objectId, int objectX, int objectY, int objectHeight,
                int objectOption, int packetOpcode, Objects object) {
            this.traceId = traceId;
            this.objectId = objectId;
            this.objectX = objectX;
            this.objectY = objectY;
            this.objectHeight = objectHeight;
            this.objectOption = objectOption;
            this.packetOpcode = packetOpcode;
            this.object = object;
        }

        private boolean matches(int otherObjectId, int otherObjectX, int otherObjectY, int otherObjectHeight,
                int otherObjectOption) {
            return objectId == otherObjectId && objectX == otherObjectX && objectY == otherObjectY
                    && objectHeight == otherObjectHeight && objectOption == otherObjectOption;
        }

        private ObjectInteraction withObject(Objects newObject) {
            return new ObjectInteraction(traceId, objectId, objectX, objectY, objectHeight, objectOption,
                    packetOpcode, newObject);
        }
    }
}
