package com.rs2.game.globalworldobjects;

import com.rs2.Constants;
import com.rs2.game.players.Client;
import com.rs2.game.players.PlayerHandler;
import org.apollo.util.security.IsaacRandom;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

import static org.junit.Assert.assertEquals;

public class DoubleGatesTest {

    private static final int TEST_PLAYER_ID = 11;

    private TestClient player;

    @Before
    public void setUp() {
        player = new TestClient(TEST_PLAYER_ID);
        player.playerName = "gate-tester";
        player.outStream.packetEncryption = new IsaacRandom(new int[] {0, 0, 0, 0});
        player.heightLevel = 0;
        PlayerHandler.players[TEST_PLAYER_ID] = player;
    }

    @After
    public void tearDown() {
        PlayerHandler.players[TEST_PLAYER_ID] = null;
    }

    @Test
    public void barbarianOutpostGateRejectsLowAgility() {
        configureGateInteraction(2544, 3569, 2545, 3569);
        player.playerLevel[Constants.AGILITY] = 34;
        player.teleportToX = -1;
        player.teleportToY = -1;

        new DoubleGates().useDoubleGate(player, 2116);

        assertEquals(-1, player.teleportToX);
        assertEquals(-1, player.teleportToY);
    }

    @Test
    public void barbarianOutpostGateCrossesFromOutsideToInside() {
        configureGateInteraction(2544, 3569, 2545, 3569);
        player.playerLevel[Constants.AGILITY] = 35;
        player.teleportToX = -1;
        player.teleportToY = -1;

        new DoubleGates().useDoubleGate(player, 2116);

        assertEquals(2546, player.teleportToX);
        assertEquals(3569, player.teleportToY);
    }

    @Test
    public void barbarianOutpostGateCrossesFromInsideToOutside() {
        configureGateInteraction(2546, 3569, 2545, 3569);
        player.playerLevel[Constants.AGILITY] = 35;
        player.teleportToX = -1;
        player.teleportToY = -1;

        new DoubleGates().useDoubleGate(player, 2116);

        assertEquals(2544, player.teleportToX);
        assertEquals(3569, player.teleportToY);
    }

    @Test
    public void unsupportedAdjacentPositionsDoNotTeleportThePlayer() {
        configureGateInteraction(2545, 3571, 2545, 3570);
        player.playerLevel[Constants.AGILITY] = 35;
        player.teleportToX = -1;
        player.teleportToY = -1;

        new DoubleGates().useDoubleGate(player, 2115);

        assertEquals(-1, player.teleportToX);
        assertEquals(-1, player.teleportToY);
    }

    private void configureGateInteraction(int playerX, int playerY, int objectX, int objectY) {
        player.absX = playerX;
        player.absY = playerY;
        player.objectX = objectX;
        player.objectY = objectY;
    }

    private static final class TestClient extends Client {
        private TestClient(int playerId) {
            super(null, playerId);
        }

        @Override
        public void stopMovement() {
            // Keep this unit test independent from live movement processing.
        }

        @Override
        public void flushOutStream() {
            // Keep this unit test independent from a network session.
        }
    }
}
