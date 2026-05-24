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
    private Player previousSeven;
    private String token;

    @Before
    public void setUp() throws Exception {
        File logDirectory = temporaryFolder.newFolder("agent-sessions");
        AgentSessionLog.INSTANCE.setLogDirectoryForTests(logDirectory);
        previousZero = PlayerHandler.players[0];
        previousOne = PlayerHandler.players[1];
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

        assertNull(manager.getSession(flameToken));
        assertNotNull(manager.getSession(gemToken));
    }

    private static class TestPlayer extends Player {
        private TestPlayer(int playerId) {
            super(playerId);
        }
    }
}
