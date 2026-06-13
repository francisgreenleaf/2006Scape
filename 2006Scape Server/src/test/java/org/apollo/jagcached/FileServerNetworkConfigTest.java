package org.apollo.jagcached;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.net.InetSocketAddress;
import java.net.SocketAddress;
import java.util.List;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;

import com.rs2.Constants;

public class FileServerNetworkConfigTest {

    private int previousGamePort;
    private int previousWorld;
    private boolean previousExternalPlayers;

    @Before
    public void setUp() {
        previousGamePort = Constants.GAME_PORT;
        previousWorld = Constants.WORLD;
        previousExternalPlayers = Constants.EXTERNAL_PLAYERS_ENABLED;
    }

    @After
    public void tearDown() {
        Constants.GAME_PORT = previousGamePort;
        Constants.WORLD = previousWorld;
        Constants.EXTERNAL_PLAYERS_ENABLED = previousExternalPlayers;
    }

    @Test
    public void bindAddressUsesWildcardForBlankOrStarHost() {
        InetSocketAddress blank = (InetSocketAddress) FileServer.bindAddress(" ", 43594);
        InetSocketAddress star = (InetSocketAddress) FileServer.bindAddress("*", 43595);

        assertEquals(43594, blank.getPort());
        assertEquals(43595, star.getPort());
        assertTrue(blank.getAddress().isAnyLocalAddress());
        assertTrue(star.getAddress().isAnyLocalAddress());
    }

    @Test
    public void bindAddressUsesTrimmedExplicitHost() {
        InetSocketAddress address = (InetSocketAddress) FileServer.bindAddress(" 127.0.0.1 ", 43594);

        assertEquals("127.0.0.1", address.getHostString());
        assertEquals(43594, address.getPort());
    }

    @Test
    public void bindAddressesUsesConfiguredHostsBeforeFallback() {
        List<SocketAddress> addresses = FileServer.bindAddresses(new String[] {
                "127.0.0.1", "100.64.0.10", "127.0.0.1"
        }, "0.0.0.0", 43594);

        assertEquals(2, addresses.size());
        assertEquals("127.0.0.1", ((InetSocketAddress) addresses.get(0)).getHostString());
        assertEquals("100.64.0.10", ((InetSocketAddress) addresses.get(1)).getHostString());
    }

    @Test
    public void bindAddressesFallsBackToSingleHostWhenListIsEmpty() {
        List<SocketAddress> addresses = FileServer.bindAddresses(new String[0], "127.0.0.1", 43594);

        assertEquals(1, addresses.size());
        assertEquals("127.0.0.1", ((InetSocketAddress) addresses.get(0)).getHostString());
    }

    @Test
    public void gamePortPrefersConfiguredPort() {
        Constants.GAME_PORT = 44444;
        Constants.WORLD = 2;

        assertEquals(44444, FileServer.gamePort());
    }

    @Test
    public void gamePortFallsBackToWorldPortWhenUnset() {
        Constants.GAME_PORT = -1;
        Constants.WORLD = 1;
        assertEquals(43594, FileServer.gamePort());

        Constants.WORLD = 2;
        assertEquals(43598, FileServer.gamePort());
    }

    @Test
    public void httpBindFailureIsOnlyFatalForExternalPlayerMode() {
        Constants.EXTERNAL_PLAYERS_ENABLED = false;
        assertFalse(FileServer.httpBindFailureIsFatal());

        Constants.EXTERNAL_PLAYERS_ENABLED = true;
        assertTrue(FileServer.httpBindFailureIsFatal());
    }
}
