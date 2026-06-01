package com.rs2.game.content.custom;

import org.junit.Test;

import static org.junit.Assert.assertFalse;

public class CustomFeatureFlagsTest {

    @Test
    public void catherbyTraderStanAndGlassmakingDefaultsToDisabled() {
        assertFalse(CustomFeatureFlags.CATHERBY_TRADER_STAN_AND_GLASSMAKING_ENABLED);
    }
}
