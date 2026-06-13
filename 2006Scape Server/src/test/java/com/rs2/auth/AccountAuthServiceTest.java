package com.rs2.auth;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.attribute.PosixFilePermission;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;
import java.util.Set;

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;

import org.junit.After;
import org.junit.Assume;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import com.rs2.Constants;

public class AccountAuthServiceTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    private boolean previousAutoCreate;
    private boolean previousLegacyFallback;
    private boolean previousExternalPlayers;
    private int previousIterations;
    private AccountAuthService service;

    @Before
    public void setUp() throws Exception {
        previousAutoCreate = Constants.ACCOUNT_AUTH_AUTO_CREATE;
        previousLegacyFallback = Constants.ACCOUNT_AUTH_LEGACY_FALLBACK;
        previousExternalPlayers = Constants.EXTERNAL_PLAYERS_ENABLED;
        previousIterations = Constants.ACCOUNT_AUTH_PBKDF2_ITERATIONS;
        Constants.ACCOUNT_AUTH_AUTO_CREATE = false;
        Constants.ACCOUNT_AUTH_LEGACY_FALLBACK = true;
        Constants.EXTERNAL_PLAYERS_ENABLED = false;
        Constants.ACCOUNT_AUTH_PBKDF2_ITERATIONS = 10000;
        File accounts = temporaryFolder.newFolder("accounts");
        service = new AccountAuthService(accounts, new SecureRandom());
    }

    @After
    public void tearDown() {
        Constants.ACCOUNT_AUTH_AUTO_CREATE = previousAutoCreate;
        Constants.ACCOUNT_AUTH_LEGACY_FALLBACK = previousLegacyFallback;
        Constants.EXTERNAL_PLAYERS_ENABLED = previousExternalPlayers;
        Constants.ACCOUNT_AUTH_PBKDF2_ITERATIONS = previousIterations;
    }

    @Test
    public void createsSaltedPbkdf2RecordAndVerifiesPassword() throws Exception {
        AccountAuthService.AccountRecord record = service.create("MrFlame", "correct horse");

        assertNotNull(record.passwordHash);
        assertNotNull(record.passwordSalt);
        assertNotEquals("correct horse", record.passwordHash);
        assertTrue(service.authenticate("mrflame", "correct horse").success);
        assertFalse(service.authenticate("mrflame", "wrong").success);
    }

    @Test
    public void accountPasswordsAreVerifiedExactlyWithoutTrimmingWhitespace() throws Exception {
        service.create("MrFlame", "  exact horse  ");

        assertTrue(service.authenticate("mrflame", "  exact horse  ").success);
        assertFalse(service.authenticate("mrflame", "exact horse").success);
    }

    @Test
    public void missingAccountFailsWhenAutoCreateIsDisabled() {
        AccountAuthService.AuthResult result = service.authenticate("missing", "password");

        assertFalse(result.success);
        assertTrue(result.legacyFallbackAllowed);
    }

    @Test
    public void missingAccountAttemptsAreNotRemoteRateLimitedWhenLegacyFallbackIsEnabled() {
        for (int i = 0; i < 21; i++) {
            AccountAuthService.AuthResult result = service.authenticate("miss" + i, "password", "203.0.113.5");
            assertFalse(result.success);
            assertEquals("account_not_found", result.status);
            assertTrue(result.legacyFallbackAllowed);
        }
    }

    @Test
    public void missingAccountAttemptsRateLimitRemoteAddressWhenLegacyFallbackIsDisabled() {
        Constants.ACCOUNT_AUTH_LEGACY_FALLBACK = false;
        for (int i = 0; i < 20; i++) {
            AccountAuthService.AuthResult result = service.authenticate("none" + i, "password", "203.0.113.5");
            assertFalse(result.success);
            assertEquals("account_not_found", result.status);
            assertFalse(result.legacyFallbackAllowed);
        }

        AccountAuthService.AuthResult result = service.authenticate("nonefinal", "password", "203.0.113.5");

        assertFalse(result.success);
        assertEquals("rate_limited", result.status);
        assertFalse(result.legacyFallbackAllowed);
    }

    @Test
    public void missingAccountCanAutoCreateWhenConfigured() {
        Constants.ACCOUNT_AUTH_AUTO_CREATE = true;

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "new password");

        assertTrue(result.success);
        assertNotNull(service.load("mrgem"));
    }

    @Test
    public void disabledAccountCannotAuthenticate() throws Exception {
        AccountAuthService.AccountRecord record = service.create("Mrwood", "password");
        record.disabled = true;
        service.save(record);

        AccountAuthService.AuthResult result = service.authenticate("mrwood", "password");

        assertFalse(result.success);
        assertFalse(result.legacyFallbackAllowed);
    }

    @Test
    public void existingAccountRejectsWrongPasswordWithoutLegacyFallback() throws Exception {
        service.create("MrGem", "new password");

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "old legacy password");

        assertFalse(result.success);
        assertFalse(result.legacyFallbackAllowed);
    }

    @Test
    public void invalidExistingAccountRecordDoesNotAllowLegacyFallback() throws Exception {
        File file = service.accountFile("MrGem");
        Files.createDirectories(file.getParentFile().toPath());
        Files.write(file.toPath(), "{}".getBytes(StandardCharsets.UTF_8));

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "old legacy password");

        assertFalse(result.success);
        assertEquals("account_record_invalid", result.status);
        assertFalse(result.legacyFallbackAllowed);
    }

    @Test
    public void symlinkedAccountRecordDoesNotAllowLegacyFallback() throws Exception {
        File file = service.accountFile("MrGem");
        File target = temporaryFolder.newFile("target-account.json");
        Files.createDirectories(file.getParentFile().toPath());
        try {
            Files.createSymbolicLink(file.toPath(), target.toPath());
        } catch (UnsupportedOperationException | java.io.IOException | SecurityException e) {
            Assume.assumeNoException(e);
        }

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "old legacy password");

        assertFalse(result.success);
        assertEquals("account_record_invalid", result.status);
        assertFalse(result.legacyFallbackAllowed);
    }

    @Test
    public void saveRefusesSymlinkedAccountRecord() throws Exception {
        File file = service.accountFile("MrGem");
        File target = temporaryFolder.newFile("target-save.json");
        Files.createDirectories(file.getParentFile().toPath());
        try {
            Files.createSymbolicLink(file.toPath(), target.toPath());
        } catch (UnsupportedOperationException | java.io.IOException | SecurityException e) {
            Assume.assumeNoException(e);
        }
        AccountAuthService.AccountRecord record = new AccountAuthService.AccountRecord();
        record.username = "mrgem";

        try {
            service.save(record);
        } catch (java.io.IOException e) {
            assertTrue(e.getMessage().contains("symlinked account file"));
            return;
        }
        assertFalse("save should refuse symlinked account records", true);
    }

    @Test
    public void malformedAccountRoleMetadataFailsClosed() throws Exception {
        AccountAuthService.AccountRecord record = service.create("MrGem", "new password");
        record.roles = Arrays.asList("player", "bad role!");
        service.save(record);

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "new password");

        assertFalse(result.success);
        assertEquals("account_record_invalid", result.status);
        assertFalse(result.legacyFallbackAllowed);
    }

    @Test
    public void malformedAllowedCharacterMetadataFailsClosed() throws Exception {
        AccountAuthService.AccountRecord record = service.create("MrGem", "new password");
        record.allowedCharacters = Arrays.asList("MrGem", "Not@Valid");
        service.save(record);

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "new password");

        assertFalse(result.success);
        assertEquals("account_record_invalid", result.status);
        assertFalse(result.legacyFallbackAllowed);
    }

    @Test
    public void malformedDiscordUserIdMetadataFailsClosed() throws Exception {
        AccountAuthService.AccountRecord record = service.create("MrGem", "new password");
        record.discordUserId = "not-a-snowflake";
        service.save(record);

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "new password");

        assertFalse(result.success);
        assertEquals("account_record_invalid", result.status);
        assertFalse(result.legacyFallbackAllowed);
    }

    @Test
    public void accountRecordWithShortSaltFailsClosed() throws Exception {
        AccountAuthService.AccountRecord record = service.create("MrGem", "new password");
        record.passwordSalt = Base64.getEncoder().encodeToString("shortsal".getBytes(StandardCharsets.UTF_8));
        service.save(record);

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "new password");

        assertFalse(result.success);
        assertEquals("account_record_invalid", result.status);
        assertFalse(result.legacyFallbackAllowed);
    }

    @Test
    public void emptyAllowedCharactersDoesNotRestrictAccountLogin() throws Exception {
        service.create("MrGem", "new password");

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "new password");

        assertTrue(result.success);
    }

    @Test
    public void nonEmptyAllowedCharactersMustIncludeLoginCharacter() throws Exception {
        AccountAuthService.AccountRecord record = service.create("MrGem", "new password");
        record.allowedCharacters = Arrays.asList("MrFlame");
        service.save(record);

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "new password");

        assertFalse(result.success);
        assertEquals("character_not_allowed", result.status);
        assertFalse(result.legacyFallbackAllowed);
    }

    @Test
    public void allowedCharactersCanAuthorizeLoginCharacter() throws Exception {
        AccountAuthService.AccountRecord record = service.create("MrGem", "new password");
        record.allowedCharacters = Arrays.asList("MrFlame", "MrGem");
        service.save(record);

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "new password");

        assertTrue(result.success);
    }

    @Test
    public void externalModeRejectsWeakAccountRecordHash() throws Exception {
        service.create("MrGem", "new password");
        Constants.EXTERNAL_PLAYERS_ENABLED = true;
        Constants.ACCOUNT_AUTH_PBKDF2_ITERATIONS = 120000;

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "new password");

        assertFalse(result.success);
        assertEquals("account_record_weak_hash", result.status);
        assertFalse(result.legacyFallbackAllowed);
    }

    @Test
    public void localRecordVerifiesWithStoredIterationsAfterConfigIsRaised() throws Exception {
        service.create("MrGem", "new password");
        Constants.ACCOUNT_AUTH_PBKDF2_ITERATIONS = 120000;

        AccountAuthService.AuthResult result = service.authenticate("MrGem", "new password");

        assertTrue(result.success);
    }

    @Test
    public void authenticatesSha1Pbkdf2CompatibilityRecord() throws Exception {
        byte[] salt = "fixed test salt!".getBytes(StandardCharsets.UTF_8);
        AccountAuthService.AccountRecord record = new AccountAuthService.AccountRecord();
        record.username = "oldjava";
        record.algorithm = "PBKDF2WithHmacSHA1";
        record.passwordSalt = Base64.getEncoder().encodeToString(salt);
        record.passwordIterations = 10000;
        record.passwordHash = pbkdf2("compatible password", salt, record.passwordIterations, record.algorithm);
        service.save(record);

        assertTrue(service.authenticate("oldjava", "compatible password").success);
        assertFalse(service.authenticate("oldjava", "wrong password").success);
    }

    @Test
    public void repeatedWrongPasswordsRateLimitExistingAccount() throws Exception {
        service.create("MrGem", "new password");

        for (int i = 0; i < 5; i++) {
            AccountAuthService.AuthResult result = service.authenticate("MrGem", "wrong " + i);
            assertFalse(result.success);
            assertEquals("invalid_password", result.status);
        }
        AccountAuthService.AuthResult rateLimited = service.authenticate("MrGem", "new password");

        assertFalse(rateLimited.success);
        assertEquals("rate_limited", rateLimited.status);
        assertFalse(rateLimited.legacyFallbackAllowed);
    }

    @Test
    public void repeatedWrongPasswordsRateLimitRemoteAddressAcrossAccounts() throws Exception {
        String remoteAddress = "203.0.113.5";
        for (int i = 0; i < 20; i++) {
            String username = "remote" + i;
            service.create(username, "new password");
            AccountAuthService.AuthResult result = service.authenticate(username, "wrong password", remoteAddress);
            assertFalse(result.success);
            assertEquals("invalid_password", result.status);
        }
        service.create("remotefinal", "new password");

        AccountAuthService.AuthResult result = service.authenticate("remotefinal", "new password", remoteAddress);

        assertFalse(result.success);
        assertEquals("rate_limited", result.status);
        assertFalse(result.legacyFallbackAllowed);
    }

    @Test
    public void remoteAddressRateLimitDoesNotAffectOtherSources() throws Exception {
        String remoteAddress = "203.0.113.5";
        for (int i = 0; i < 20; i++) {
            String username = "source" + i;
            service.create(username, "new password");
            AccountAuthService.AuthResult result = service.authenticate(username, "wrong password", remoteAddress);
            assertFalse(result.success);
            assertEquals("invalid_password", result.status);
        }
        service.create("sourcefinal", "new password");

        AccountAuthService.AuthResult result = service.authenticate("sourcefinal", "new password", "203.0.113.6");

        assertTrue(result.success);
    }

    @Test
    public void missingAccountSprayDoesNotGrowFailedAuthStateWithoutBound() {
        Constants.ACCOUNT_AUTH_LEGACY_FALLBACK = false;

        for (int i = 0; i < 4200; i++) {
            String remoteAddress = "203.0." + (i / 256) + "." + (i % 256);
            AccountAuthService.AuthResult result = service.authenticate("missing", "password", remoteAddress);
            assertFalse(result.success);
        }

        assertTrue(service.failedAuthStateCountForTest() <= 4096);
    }

    @Test
    public void successfulLoginClearsFailedAttemptCounter() throws Exception {
        service.create("MrGem", "new password");

        for (int i = 0; i < 4; i++) {
            assertFalse(service.authenticate("MrGem", "wrong " + i).success);
        }
        assertTrue(service.authenticate("MrGem", "new password").success);
        for (int i = 0; i < 4; i++) {
            AccountAuthService.AuthResult result = service.authenticate("MrGem", "wrong again " + i);
            assertFalse(result.success);
            assertEquals("invalid_password", result.status);
        }

        assertTrue(service.authenticate("MrGem", "new password").success);
    }

    @Test
    public void createdAccountFilesUseOwnerOnlyPermissionsWhenSupported() throws Exception {
        Assume.assumeTrue(Files.getFileStore(service.accountFile("MrFlame").getParentFile().toPath())
                .supportsFileAttributeView("posix"));

        service.create("MrFlame", "correct horse");

        Set<PosixFilePermission> directoryPermissions = Files.getPosixFilePermissions(
                service.accountFile("MrFlame").getParentFile().toPath());
        Set<PosixFilePermission> filePermissions = Files.getPosixFilePermissions(
                service.accountFile("MrFlame").toPath());

        assertEquals(PosixFilePermissions.fromString("rwx------"), directoryPermissions);
        assertEquals(PosixFilePermissions.fromString("rw-------"), filePermissions);
    }

    private static String pbkdf2(String password, byte[] salt, int iterations, String algorithm) throws Exception {
        PBEKeySpec spec = new PBEKeySpec(password.toCharArray(), salt, iterations, 256);
        SecretKeyFactory factory = SecretKeyFactory.getInstance(algorithm);
        return Base64.getEncoder().encodeToString(factory.generateSecret(spec).getEncoded());
    }
}
