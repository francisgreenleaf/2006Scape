package org.apollo.game.session;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.net.InetAddress;
import java.net.InetSocketAddress;

import org.apollo.util.security.PlayerCredentials;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

import com.rs2.Constants;

public class LoginSessionPasswordHandlingTest {

    private boolean previousAccountAuthEnabled;

    @Before
    public void setUp() {
        previousAccountAuthEnabled = Constants.ACCOUNT_AUTH_ENABLED;
    }

    @After
    public void tearDown() {
        Constants.ACCOUNT_AUTH_ENABLED = previousAccountAuthEnabled;
    }

    @Test
    public void submittedPasswordPreservesWhitespaceForAccountAuth() {
        PlayerCredentials credentials = new PlayerCredentials("MrFlame", "  exact horse  ", 0, 0, "127.0.0.1");

        assertEquals("  exact horse  ", LoginSession.submittedPassword(credentials));
    }

    @Test
    public void legacyPasswordKeepsHistoricalTrimBehavior() {
        assertEquals("exact horse", LoginSession.legacyPassword("  exact horse  "));
    }

    @Test
    public void accountAuthOnlyRejectsTrulyEmptySubmittedPasswords() {
        Constants.ACCOUNT_AUTH_ENABLED = true;

        assertFalse(LoginSession.isMissingPassword(" ", ""));
        assertTrue(LoginSession.isMissingPassword("", ""));
    }

    @Test
    public void legacyAuthRejectsWhitespaceOnlyPasswordsAfterTrim() {
        Constants.ACCOUNT_AUTH_ENABLED = false;

        assertTrue(LoginSession.isMissingPassword(" ", ""));
        assertFalse(LoginSession.isMissingPassword(" legacy ", "legacy"));
    }

    @Test
    public void remoteHostAddressPrefersCredentialAddress() throws Exception {
        PlayerCredentials credentials = new PlayerCredentials("MrFlame", "password", 0, 0, "  203.0.113.8  ");
        InetSocketAddress socketAddress = new InetSocketAddress(InetAddress.getByName("203.0.113.9"), 43594);

        assertEquals("203.0.113.8", LoginSession.remoteHostAddress(credentials, socketAddress));
    }

    @Test
    public void remoteHostAddressFallsBackToNumericSocketAddress() throws Exception {
        PlayerCredentials credentials = new PlayerCredentials("MrFlame", "password", 0, 0, "");
        InetSocketAddress socketAddress = new InetSocketAddress(InetAddress.getByName("203.0.113.9"), 43594);

        assertEquals("203.0.113.9", LoginSession.remoteHostAddress(credentials, socketAddress));
    }

    @Test
    public void remoteHostAddressFallsBackToUnresolvedHostString() {
        InetSocketAddress socketAddress = InetSocketAddress.createUnresolved("Example-Tailnet-Host", 43594);

        assertEquals("example-tailnet-host", LoginSession.remoteHostAddress(null, socketAddress));
    }
}
