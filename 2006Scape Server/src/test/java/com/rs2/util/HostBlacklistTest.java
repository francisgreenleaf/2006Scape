package com.rs2.util;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;

public class HostBlacklistTest {

    @Before
    public void setUp() {
        HostBlacklist.getBlockedHostnames().clear();
    }

    @After
    public void tearDown() {
        HostBlacklist.getBlockedHostnames().clear();
    }

    @Test
    public void isBlockedNormalizesCaseAndWhitespace() {
        HostBlacklist.getBlockedHostnames().add("203.0.113.8");
        HostBlacklist.getBlockedHostnames().add("example-tailnet-host");

        assertTrue(HostBlacklist.isBlocked("  203.0.113.8  "));
        assertTrue(HostBlacklist.isBlocked("Example-Tailnet-Host"));
    }

    @Test
    public void isBlockedTreatsNullAndBlankAsNotBlocked() {
        HostBlacklist.getBlockedHostnames().add("203.0.113.8");

        assertFalse(HostBlacklist.isBlocked(null));
        assertFalse(HostBlacklist.isBlocked(""));
        assertFalse(HostBlacklist.isBlocked("   "));
    }

    @Test
    public void normalizeHostSkipsCommentLines() {
        assertEquals("", HostBlacklist.normalizeHost("# comment"));
        assertEquals("", HostBlacklist.normalizeHost("// comment"));
        assertEquals("203.0.113.8", HostBlacklist.normalizeHost("  203.0.113.8  "));
    }
}
