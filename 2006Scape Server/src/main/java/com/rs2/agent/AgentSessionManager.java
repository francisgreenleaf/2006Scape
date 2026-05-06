package com.rs2.agent;

import java.security.SecureRandom;
import java.util.Iterator;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import com.rs2.game.players.Player;

public class AgentSessionManager {

    public static final AgentSessionManager INSTANCE = new AgentSessionManager();

    private static final long CLAIM_TTL_MS = 30_000L;
    private static final long SESSION_TTL_MS = 8L * 60L * 60L * 1000L;

    private final SecureRandom secureRandom = new SecureRandom();
    private final Map<String, PendingClaim> claimsByNonce = new ConcurrentHashMap<String, PendingClaim>();
    private final Map<String, AgentSession> sessionsByToken = new ConcurrentHashMap<String, AgentSession>();

    public String registerClaim(Player player, String nonce) {
        cleanupExpired();
        if (player == null || nonce == null || nonce.trim().isEmpty()) {
            return null;
        }
        long now = System.currentTimeMillis();
        String token = randomHex(32);
        String sessionId = randomHex(8);
        AgentSession session = new AgentSession(token, sessionId, player.playerId, player.playerName, now);
        sessionsByToken.put(token, session);
        claimsByNonce.put(nonce, new PendingClaim(nonce, token, player.playerId, player.playerName, now));
        AgentSessionLog.INSTANCE.sessionRegistered(session);
        return token;
    }

    public ClaimResult consumeClaim(String nonce) {
        cleanupExpired();
        if (nonce == null || nonce.trim().isEmpty()) {
            return ClaimResult.failure("Missing session nonce.");
        }
        PendingClaim claim = claimsByNonce.remove(nonce);
        if (claim == null) {
            return ClaimResult.failure("No pending agent bridge claim was found.");
        }
        AgentSession session = sessionsByToken.get(claim.token);
        if (session == null || session.getPlayer() == null) {
            return ClaimResult.failure("The claimed player session is no longer online.");
        }
        session.touch(System.currentTimeMillis());
        AgentSessionLog.INSTANCE.sessionClaimed(session);
        return ClaimResult.success(session);
    }

    public AgentSession getSession(String token) {
        cleanupExpired();
        if (token == null || token.trim().isEmpty()) {
            return null;
        }
        AgentSession session = sessionsByToken.get(token);
        if (session == null || session.getPlayer() == null) {
            return null;
        }
        session.touch(System.currentTimeMillis());
        return session;
    }

    public void invalidate(String token) {
        invalidate(token, "invalidated");
    }

    public void invalidate(String token, String reason) {
        if (token != null) {
            AgentSession session = sessionsByToken.remove(token);
            if (session != null) {
                AgentSessionLog.INSTANCE.sessionInvalidated(session, reason);
            }
        }
    }

    public int getSessionCount() {
        cleanupExpired();
        return sessionsByToken.size();
    }

    private String randomHex(int bytes) {
        byte[] data = new byte[bytes];
        secureRandom.nextBytes(data);
        StringBuilder builder = new StringBuilder(data.length * 2);
        for (byte b : data) {
            builder.append(String.format("%02x", b & 0xff));
        }
        return builder.toString();
    }

    private void cleanupExpired() {
        long now = System.currentTimeMillis();
        for (Iterator<Map.Entry<String, PendingClaim>> it = claimsByNonce.entrySet().iterator(); it.hasNext();) {
            Map.Entry<String, PendingClaim> entry = it.next();
            if (now - entry.getValue().createdAt > CLAIM_TTL_MS) {
                it.remove();
                AgentSession session = sessionsByToken.remove(entry.getValue().token);
                if (session != null) {
                    AgentSessionLog.INSTANCE.sessionExpired(session, "claim_expired");
                }
            }
        }
        for (Iterator<Map.Entry<String, AgentSession>> it = sessionsByToken.entrySet().iterator(); it.hasNext();) {
            Map.Entry<String, AgentSession> entry = it.next();
            AgentSession session = entry.getValue();
            String reason = null;
            if (now - session.getLastUsedAt() > SESSION_TTL_MS) {
                reason = "session_idle_timeout";
            } else if (session.getPlayer() == null) {
                reason = "player_offline";
            }
            if (reason != null) {
                it.remove();
                AgentSessionLog.INSTANCE.sessionExpired(session, reason);
            }
        }
    }

    private static class PendingClaim {
        private final String nonce;
        private final String token;
        private final int playerId;
        private final String playerName;
        private final long createdAt;

        private PendingClaim(String nonce, String token, int playerId, String playerName, long createdAt) {
            this.nonce = nonce;
            this.token = token;
            this.playerId = playerId;
            this.playerName = playerName;
            this.createdAt = createdAt;
        }
    }

    public static class ClaimResult {
        private final boolean success;
        private final AgentSession session;
        private final String error;

        private ClaimResult(boolean success, AgentSession session, String error) {
            this.success = success;
            this.session = session;
            this.error = error;
        }

        public static ClaimResult success(AgentSession session) {
            return new ClaimResult(true, session, null);
        }

        public static ClaimResult failure(String error) {
            return new ClaimResult(false, null, error);
        }

        public boolean isSuccess() {
            return success;
        }

        public AgentSession getSession() {
            return session;
        }

        public String getError() {
            return error;
        }
    }
}
