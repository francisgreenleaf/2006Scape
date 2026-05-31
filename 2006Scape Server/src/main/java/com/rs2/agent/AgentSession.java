package com.rs2.agent;

import com.rs2.game.players.Player;
import com.rs2.game.players.PlayerHandler;

public class AgentSession {

    private final String token;
    private final String sessionId;
    private volatile int playerId;
    private final String playerName;
    private final long createdAt;
    private volatile long lastUsedAt;
    private volatile long playerMissingSinceAt = -1L;

    AgentSession(String token, String sessionId, int playerId, String playerName, long createdAt) {
        this.token = token;
        this.sessionId = sessionId;
        this.playerId = playerId;
        this.playerName = playerName;
        this.createdAt = createdAt;
        this.lastUsedAt = createdAt;
    }

    public String getToken() {
        return token;
    }

    public String getSessionId() {
        return sessionId;
    }

    public int getPlayerId() {
        return playerId;
    }

    public String getPlayerName() {
        return playerName;
    }

    public long getCreatedAt() {
        return createdAt;
    }

    public long getLastUsedAt() {
        return lastUsedAt;
    }

    void touch(long now) {
        lastUsedAt = now;
    }

    void bindTo(Player player) {
        if (player != null && player.playerName != null && player.playerName.equalsIgnoreCase(playerName)) {
            playerId = player.playerId;
            playerMissingSinceAt = -1L;
        }
    }

    long notePlayerMissing(long now) {
        if (getPlayer() != null) {
            return -1L;
        }
        if (playerMissingSinceAt < 0L) {
            playerMissingSinceAt = now;
        }
        return playerMissingSinceAt;
    }

    public Player getPlayer() {
        Player player = playerAt(playerId);
        if (isMatchingLivePlayer(player)) {
            playerMissingSinceAt = -1L;
            return player;
        }
        Player rebound = findUniqueLivePlayerByName();
        if (rebound != null) {
            bindTo(rebound);
            return rebound;
        }
        return null;
    }

    private Player playerAt(int id) {
        if (id < 0 || id >= PlayerHandler.players.length) {
            return null;
        }
        return PlayerHandler.players[id];
    }

    private boolean isMatchingLivePlayer(Player player) {
        return player != null
                && !player.disconnected
                && player.playerName != null
                && player.playerName.equalsIgnoreCase(playerName);
    }

    private Player findUniqueLivePlayerByName() {
        Player match = null;
        for (int i = 0; i < PlayerHandler.players.length; i++) {
            Player candidate = PlayerHandler.players[i];
            if (!isMatchingLivePlayer(candidate)) {
                continue;
            }
            if (match != null) {
                return null;
            }
            match = candidate;
        }
        return match;
    }
}
