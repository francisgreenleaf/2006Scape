package com.rs2.agent;

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
import static org.junit.Assert.assertTrue;

public class AgentSessionManagerTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    private String token;

    @Before
    public void setUp() throws Exception {
        AgentSessionLog.INSTANCE.setLogDirectoryForTests(temporaryFolder.newFolder("agent-sessions"));
    }

    @After
    public void tearDown() {
        if (token != null) {
            AgentSessionManager.INSTANCE.invalidate(token, "test");
            token = null;
        }
        AgentSessionLog.INSTANCE.resetLogDirectoryForTests();
        PlayerHandler.players[7] = null;
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

    private static class TestPlayer extends Player {
        private TestPlayer(int playerId) {
            super(playerId);
        }
    }
}
