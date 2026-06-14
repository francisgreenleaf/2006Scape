package com.rs2.net.packets.impl;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import com.rs2.game.players.Client;

public class CommandsPasswordPolicyTest {

    @Test
    public void passwordCommandIsBlockedForAccountAuthenticatedPlayers() {
        Client player = new Client(null, -1);
        player.accountAuthVerified = true;

        assertTrue(Commands.usesAccountAuth(player));
    }

    @Test
    public void passwordCommandIsStillAvailableForLegacyCharacterAuthPlayers() {
        Client player = new Client(null, -1);
        player.accountAuthVerified = false;

        assertFalse(Commands.usesAccountAuth(player));
    }
}
