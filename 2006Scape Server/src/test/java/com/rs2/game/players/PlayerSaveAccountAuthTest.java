package com.rs2.game.players;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotEquals;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public class PlayerSaveAccountAuthTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    private String previousUserDir;

    @Before
    public void setUp() throws Exception {
        previousUserDir = System.getProperty("user.dir");
        System.setProperty("user.dir", temporaryFolder.getRoot().getAbsolutePath());
        Files.createDirectories(new File(temporaryFolder.getRoot(), "data/characters").toPath());
    }

    @After
    public void tearDown() {
        System.setProperty("user.dir", previousUserDir);
    }

    @Test
    public void accountAuthLoadPreservesExistingLegacyCharacterPasswordWithoutValidatingIt() throws Exception {
        File character = new File(temporaryFolder.getRoot(), "data/characters/mrflame.txt");
        Files.write(character.toPath(), (
                "[ACCOUNT]\n"
                        + "character-username = mrflame\n"
                        + "character-password = existing-legacy-token\n"
                        + "\n"
                        + "[CHARACTER]\n"
                        + "character-posx = 3222\n"
                        + "character-posy = 3218\n"
                        + "[EOF]\n").getBytes(StandardCharsets.UTF_8));
        Client player = new Client(null, 1);
        player.playerName = "mrflame";

        int load = PlayerSave.loadPlayerInfo(player, "mrflame", "submitted-account-password", false);

        assertEquals(1, load);
        assertEquals("existing-legacy-token", player.playerPass);
    }

    @Test
    public void accountAuthNewCharacterReplacesSubmittedPasswordWithRandomLegacyPlaceholder() {
        Client player = new Client(null, 1);
        player.accountAuthVerified = true;
        player.playerPass = "submitted-account-password";

        PlayerSave.protectAccountAuthPassword(player, "submitted-account-password", 0);

        assertNotEquals("submitted-account-password", player.playerPass);
        assertNotEquals(PlayerSave.passwordHash("submitted-account-password"), player.playerPass);
    }

    @Test
    public void accountAuthExistingCharacterKeepsLoadedLegacyToken() {
        Client player = new Client(null, 1);
        player.accountAuthVerified = true;
        player.playerPass = "existing-legacy-token";

        PlayerSave.protectAccountAuthPassword(player, "submitted-account-password", 1);

        assertEquals("existing-legacy-token", player.playerPass);
    }
}
