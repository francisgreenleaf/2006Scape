package com.rs2;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.Set;

import org.json.JSONObject;
import org.junit.Assume;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public class ConfigLoaderSecretsTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    @Test
    public void defaultSecretsFileKeepsExpectedShape() throws Exception {
        File secretsFile = new File(temporaryFolder.newFolder("data"), "secrets.json");

        ConfigLoader.writeDefaultSecretsFileForTest(secretsFile);

        JSONObject secrets = new JSONObject(new String(Files.readAllBytes(secretsFile.toPath()),
                StandardCharsets.UTF_8));
        assertEquals("", secrets.getString("bot-token"));
        assertEquals("", secrets.getString("websitepass"));
        assertEquals("", secrets.getString("erssecret"));
        assertTrue(secrets.has("agent-discord-bots"));
        assertEquals(0, secrets.getJSONArray("agent-discord-bots").length());
    }

    @Test
    public void defaultSecretsFileUsesOwnerOnlyPermissionsWhenSupported() throws Exception {
        File dataDirectory = temporaryFolder.newFolder("data");
        Assume.assumeTrue(Files.getFileStore(dataDirectory.toPath()).supportsFileAttributeView("posix"));
        File secretsFile = new File(dataDirectory, "secrets.json");

        ConfigLoader.writeDefaultSecretsFileForTest(secretsFile);

        Set<PosixFilePermission> filePermissions = Files.getPosixFilePermissions(secretsFile.toPath());
        assertEquals(PosixFilePermissions.fromString("rw-------"), filePermissions);
    }

    @Test
    public void existingSecretsFileIsRestrictedBeforeRuntimeLoad() throws Exception {
        File dataDirectory = temporaryFolder.newFolder("data");
        Assume.assumeTrue(Files.getFileStore(dataDirectory.toPath()).supportsFileAttributeView("posix"));
        File secretsFile = new File(dataDirectory, "secrets.json");
        Files.write(secretsFile.toPath(), "{}".getBytes(StandardCharsets.UTF_8));
        Files.setPosixFilePermissions(secretsFile.toPath(), PosixFilePermissions.fromString("rw-r--r--"));

        ConfigLoader.prepareExistingSecretsFileForTest(secretsFile);

        Set<PosixFilePermission> filePermissions = Files.getPosixFilePermissions(secretsFile.toPath());
        assertEquals(PosixFilePermissions.fromString("rw-------"), filePermissions);
    }

    @Test
    public void symlinkedExistingSecretsFileIsRejected() throws Exception {
        File dataDirectory = temporaryFolder.newFolder("data");
        Path target = new File(dataDirectory, "target-secrets.json").toPath();
        Path link = new File(dataDirectory, "secrets.json").toPath();
        Files.write(target, "{}".getBytes(StandardCharsets.UTF_8));
        try {
            Files.createSymbolicLink(link, target);
        } catch (IOException | UnsupportedOperationException | SecurityException e) {
            Assume.assumeNoException(e);
        }

        try {
            ConfigLoader.prepareExistingSecretsFileForTest(link.toFile());
            fail("symlinked secrets file should be rejected");
        } catch (IOException e) {
            assertTrue(e.getMessage().contains("symlinked secrets file"));
        }
    }
}
