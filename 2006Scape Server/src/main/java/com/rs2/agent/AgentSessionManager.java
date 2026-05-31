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
    private static final long CONSUMED_CLAIM_TTL_MS = 2L * 60L * 1000L;
    private static final long PLAYER_RECONNECT_GRACE_MS = 2L * 60L * 1000L;

    private final SecureRandom secureRandom = new SecureRandom();
    private final Map<String, ClaimRecord> claimsByNonce = new ConcurrentHashMap<String, ClaimRecord>();
    private final Map<String, AgentSession> sessionsByToken = new ConcurrentHashMap<String, AgentSession>();

    public synchronized String registerClaim(Player player, String nonce) {
        cleanupExpired();
        if (player == null || nonce == null || nonce.trim().isEmpty()) {
            return null;
        }
        String canonicalPlayerName = canonicalName(player.playerName);
        if (canonicalPlayerName.isEmpty()) {
            return null;
        }
        ClaimRecord existingClaim = claimsByNonce.get(nonce);
        if (existingClaim != null) {
            if (!existingClaim.playerName.equals(canonicalPlayerName)) {
                return null;
            }
            AgentSession existingSession = sessionsByToken.get(existingClaim.token);
            if (existingSession != null) {
                existingSession.bindTo(player);
                return existingSession.getToken();
            }
            claimsByNonce.remove(nonce);
        }
        long now = System.currentTimeMillis();
        String token = randomHex(32);
        String sessionId = randomHex(8);
        AgentSession session = new AgentSession(token, sessionId, player.playerId, player.playerName, now);
        sessionsByToken.put(token, session);
        claimsByNonce.put(nonce, new ClaimRecord(token, canonicalPlayerName, now));
        AgentSessionLog.INSTANCE.sessionRegistered(session);
        return token;
    }

    public synchronized ClaimResult consumeClaim(String nonce) {
        cleanupExpired();
        if (nonce == null || nonce.trim().isEmpty()) {
            return ClaimResult.failure("Missing session nonce.");
        }
        ClaimRecord claim = claimsByNonce.get(nonce);
        if (claim == null) {
            return ClaimResult.failure("No pending agent bridge claim was found.");
        }
        AgentSession session = sessionsByToken.get(claim.token);
        if (session == null || session.getPlayer() == null) {
            claimsByNonce.remove(nonce);
            return ClaimResult.failure("The claimed player session is no longer online.");
        }
        long now = System.currentTimeMillis();
        boolean firstConsumption = !claim.isConsumed();
        claim.consumedAt = now;
        session.touch(now);
        if (firstConsumption) {
            AgentSessionLog.INSTANCE.sessionClaimed(session);
            invalidateOtherSessionsForPlayer(session);
        }
        return ClaimResult.success(session);
    }

    public synchronized AgentSession getSession(String token) {
        cleanupExpired();
        if (token == null || token.trim().isEmpty()) {
            return null;
        }
        AgentSession session = sessionsByToken.get(token);
        if (session == null) {
            return null;
        }
        session.touch(System.currentTimeMillis());
        return session;
    }

    public void invalidate(String token) {
        invalidate(token, "invalidated");
    }

    public synchronized void invalidate(String token, String reason) {
        if (token != null) {
            AgentSession session = sessionsByToken.remove(token);
            if (session != null) {
                removeClaimsForToken(token);
                AgentSessionLog.INSTANCE.sessionInvalidated(session, reason);
            }
        }
    }

    public synchronized int getSessionCount() {
        cleanupExpired();
        return sessionsByToken.size();
    }

    public synchronized int getPendingClaimCount() {
        cleanupExpired();
        int count = 0;
        for (ClaimRecord claim : claimsByNonce.values()) {
            if (!claim.isConsumed()) {
                count++;
            }
        }
        return count;
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
        for (Iterator<Map.Entry<String, ClaimRecord>> it = claimsByNonce.entrySet().iterator(); it.hasNext();) {
            Map.Entry<String, ClaimRecord> entry = it.next();
            ClaimRecord claim = entry.getValue();
            if (!claim.isConsumed() && now - claim.createdAt > CLAIM_TTL_MS) {
                it.remove();
                AgentSession session = sessionsByToken.remove(claim.token);
                if (session != null) {
                    AgentSessionLog.INSTANCE.sessionExpired(session, "claim_expired");
                }
            } else if (claim.isConsumed() && now - claim.consumedAt > CONSUMED_CLAIM_TTL_MS) {
                it.remove();
            }
        }
        for (Iterator<Map.Entry<String, AgentSession>> it = sessionsByToken.entrySet().iterator(); it.hasNext();) {
            Map.Entry<String, AgentSession> entry = it.next();
            AgentSession session = entry.getValue();
            String reason = null;
            if (now - session.getLastUsedAt() > SESSION_TTL_MS) {
                reason = "session_idle_timeout";
            } else {
                long missingSince = session.notePlayerMissing(now);
                if (missingSince >= 0L && now - missingSince > PLAYER_RECONNECT_GRACE_MS) {
                    reason = "player_offline";
                }
            }
            if (reason != null) {
                it.remove();
                removeClaimsForToken(session.getToken());
                AgentSessionLog.INSTANCE.sessionExpired(session, reason);
            }
        }
    }

    private void invalidateOtherSessionsForPlayer(AgentSession claimedSession) {
        String canonicalPlayerName = canonicalName(claimedSession.getPlayerName());
        for (Iterator<Map.Entry<String, AgentSession>> it = sessionsByToken.entrySet().iterator(); it.hasNext();) {
            Map.Entry<String, AgentSession> entry = it.next();
            AgentSession session = entry.getValue();
            if (session == claimedSession || !canonicalName(session.getPlayerName()).equals(canonicalPlayerName)) {
                continue;
            }
            it.remove();
            removeClaimsForToken(session.getToken());
            AgentSessionLog.INSTANCE.sessionInvalidated(session, "replaced_by_new_claim");
        }
    }

    private void removeClaimsForToken(String token) {
        for (Iterator<Map.Entry<String, ClaimRecord>> it = claimsByNonce.entrySet().iterator(); it.hasNext();) {
            if (it.next().getValue().token.equals(token)) {
                it.remove();
            }
        }
    }

    private static String canonicalName(String playerName) {
        return playerName == null ? "" : playerName.trim().toLowerCase();
    }

    private static class ClaimRecord {
        private final String token;
        private final String playerName;
        private final long createdAt;
        private long consumedAt = -1L;

        private ClaimRecord(String token, String playerName, long createdAt) {
            this.token = token;
            this.playerName = playerName;
            this.createdAt = createdAt;
        }

        private boolean isConsumed() {
            return consumedAt >= 0L;
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
