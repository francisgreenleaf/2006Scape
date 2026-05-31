package com.rs2.agent;

import java.io.File;

import com.rs2.game.players.Player;
import com.rs2.game.players.PlayerHandler;
import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

public class AgentSessionManagerTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    private Player previousZero;
    private Player previousOne;
    private Player previousTwo;
    private Player previousSeven;
    private String token;

    @Before
    public void setUp() throws Exception {
        File logDirectory = temporaryFolder.newFolder("agent-sessions");
        AgentSessionLog.INSTANCE.setLogDirectoryForTests(logDirectory);
        previousZero = PlayerHandler.players[0];
        previousOne = PlayerHandler.players[1];
        previousTwo = PlayerHandler.players[2];
        previousSeven = PlayerHandler.players[7];
    }

    @After
    public void tearDown() {
        if (token != null) {
            AgentSessionManager.INSTANCE.invalidate(token, "test");
            token = null;
        }
        PlayerHandler.players[0] = previousZero;
        PlayerHandler.players[1] = previousOne;
        PlayerHandler.players[2] = previousTwo;
        PlayerHandler.players[7] = previousSeven;
        AgentSessionLog.INSTANCE.resetLogDirectoryForTests();
    }

    @Test
    public void claimBindsToOnlinePlayerAndReturnsSessionToken() {
        TestPlayer player = new TestPlayer(7);
        player.playerName = "agent_tester";
        player.disconnected = false;
        PlayerHandler.players[7] = player;

        token = AgentSessionManager.INSTANCE.registerClaim(player, "nonce-a");
        AgentSessionManager.ClaimResult claim = AgentSessionManager.INSTANCE.consumeClaim("nonce-a");

        assertNotNull(token);
        assertTrue(claim.isSuccess());
        assertEquals("agent_tester", claim.getSession().getPlayerName());
        assertNotNull(AgentSessionManager.INSTANCE.getSession(token));
    }

    @Test
    public void unknownNonceFailsClaim() {
        AgentSessionManager.ClaimResult claim = AgentSessionManager.INSTANCE.consumeClaim("missing");

        assertFalse(claim.isSuccess());
    }

    @Test
    public void sessionsStayScopedToClaimedPlayer() {
        Player flame = new TestPlayer(0);
        flame.playerName = "MrFlame";
        Player gem = new TestPlayer(1);
        gem.playerName = "MrGem";
        PlayerHandler.players[0] = flame;
        PlayerHandler.players[1] = gem;

        AgentSessionManager manager = new AgentSessionManager();
        String flameToken = manager.registerClaim(flame, "claim-flame");
        String gemToken = manager.registerClaim(gem, "claim-gem");

        assertNotNull(flameToken);
        assertNotNull(gemToken);
        assertFalse(flameToken.equals(gemToken));

        AgentSessionManager.ClaimResult flameClaim = manager.consumeClaim("claim-flame");
        AgentSessionManager.ClaimResult gemClaim = manager.consumeClaim("claim-gem");

        assertEquals("MrFlame", flameClaim.getSession().getPlayerName());
        assertEquals("MrGem", gemClaim.getSession().getPlayerName());
        assertEquals(0, manager.getSession(flameToken).getPlayerId());
        assertEquals(1, manager.getSession(gemToken).getPlayerId());
        assertEquals("MrFlame", manager.getSession(flameToken).getPlayer().playerName);
        assertEquals("MrGem", manager.getSession(gemToken).getPlayer().playerName);

        PlayerHandler.players[0] = gem;

        assertNotNull(manager.getSession(flameToken));
        assertNull(manager.getSession(flameToken).getPlayer());
        assertNotNull(manager.getSession(gemToken));
    }

    @Test
    public void sessionRebindsToSamePlayerAfterReconnect() {
        Player original = new TestPlayer(0);
        original.playerName = "MrFlame";
        original.disconnected = false;
        PlayerHandler.players[0] = original;

        AgentSessionManager manager = new AgentSessionManager();
        String flameToken = manager.registerClaim(original, "claim-flame");
        assertTrue(manager.consumeClaim("claim-flame").isSuccess());

        original.disconnected = true;
        PlayerHandler.players[0] = null;
        Player replacement = new TestPlayer(2);
        replacement.playerName = "MrFlame";
        replacement.disconnected = false;
        PlayerHandler.players[2] = replacement;

        AgentSession session = manager.getSession(flameToken);

        assertNotNull(session);
        assertEquals(2, session.getPlayerId());
        assertEquals(replacement, session.getPlayer());
    }

    @Test
    public void repeatedSameNonceClaimRegistersOnlyOneSession() {
        Player player = new TestPlayer(0);
        player.playerName = "Mrwood";
        player.disconnected = false;
        PlayerHandler.players[0] = player;

        AgentSessionManager manager = new AgentSessionManager();
        String firstToken = manager.registerClaim(player, "same-nonce");
        String secondToken = manager.registerClaim(player, "same-nonce");

        assertEquals(firstToken, secondToken);
        assertEquals(1, manager.getSessionCount());
        assertTrue(manager.consumeClaim("same-nonce").isSuccess());

        String thirdToken = manager.registerClaim(player, "same-nonce");

        assertEquals(firstToken, thirdToken);
        assertEquals(1, manager.getSessionCount());
    }

    @Test
    public void newClaimForSamePlayerReplacesOlderClaimedSession() {
        Player player = new TestPlayer(0);
        player.playerName = "Mrfish";
        player.disconnected = false;
        PlayerHandler.players[0] = player;

        AgentSessionManager manager = new AgentSessionManager();
        String oldToken = manager.registerClaim(player, "old-claim");
        assertTrue(manager.consumeClaim("old-claim").isSuccess());
        String newToken = manager.registerClaim(player, "new-claim");
        assertTrue(manager.consumeClaim("new-claim").isSuccess());

        assertFalse(oldToken.equals(newToken));
        assertNull(manager.getSession(oldToken));
        assertNotNull(manager.getSession(newToken));
        assertEquals(1, manager.getSessionCount());
    }

    private static class TestPlayer extends Player {
        private TestPlayer(int playerId) {
            super(playerId);
        }
    }
}
