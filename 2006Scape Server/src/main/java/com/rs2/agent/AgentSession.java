package com.rs2.agent;

import com.rs2.game.players.Player;
import com.rs2.game.players.PlayerHandler;

public class AgentSession {

    private final String token;
    private final String sessionId;
    private final int playerId;
    private final String playerName;
    private final long createdAt;
    private volatile long lastUsedAt;

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

    public Player getPlayer() {
        if (playerId < 0 || playerId >= PlayerHandler.players.length) {
            return null;
        }
        Player player = PlayerHandler.players[playerId];
        if (player == null || player.disconnected || !player.playerName.equalsIgnoreCase(playerName)) {
            return null;
        }
        return player;
    }
}
