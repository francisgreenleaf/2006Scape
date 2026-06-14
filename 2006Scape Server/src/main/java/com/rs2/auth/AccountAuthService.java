package com.rs2.auth;

import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.PosixFilePermission;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.GeneralSecurityException;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Base64;
import java.util.EnumSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.rs2.Constants;

/**
 * File-backed account authentication using salted PBKDF2 password hashes.
 */
public class AccountAuthService {

    public static final AccountAuthService INSTANCE = new AccountAuthService();

    private static final String DEFAULT_ALGORITHM = "PBKDF2WithHmacSHA256";
    private static final String FALLBACK_ALGORITHM = "PBKDF2WithHmacSHA1";
    private static final int SALT_BYTES = 16;
    private static final int HASH_BITS = 256;
    private static final int MIN_EXTERNAL_ITERATIONS = 120000;
    private static final int MAX_FAILED_AUTH_ATTEMPTS = 5;
    private static final int MAX_REMOTE_FAILED_AUTH_ATTEMPTS = 20;
    private static final int MAX_FAILED_AUTH_STATES = 4096;
    private static final long FAILED_AUTH_WINDOW_MS = 10L * 60L * 1000L;
    private static final long FAILED_AUTH_LOCKOUT_MS = 60L * 1000L;
    private static final int EXPECTED_HASH_BYTES = HASH_BITS / 8;
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static final Set<PosixFilePermission> PRIVATE_DIR_PERMISSIONS = EnumSet.of(
            PosixFilePermission.OWNER_READ,
            PosixFilePermission.OWNER_WRITE,
            PosixFilePermission.OWNER_EXECUTE);
    private static final Set<PosixFilePermission> PRIVATE_FILE_PERMISSIONS = EnumSet.of(
            PosixFilePermission.OWNER_READ,
            PosixFilePermission.OWNER_WRITE);

    private final File accountDirectory;
    private final SecureRandom secureRandom;
    private final ConcurrentMap<String, FailedAuthState> failedAuthStates = new ConcurrentHashMap<String, FailedAuthState>();

    public AccountAuthService() {
        this(new File(System.getProperty("user.dir"), "data/accounts"), new SecureRandom());
    }

    AccountAuthService(File accountDirectory, SecureRandom secureRandom) {
        this.accountDirectory = accountDirectory;
        this.secureRandom = secureRandom;
    }

    public AuthResult authenticate(String username, String password) {
        return authenticate(username, password, "");
    }

    public AuthResult authenticate(String username, String password, String remoteAddress) {
        String normalized = normalizeUsername(username);
        if (normalized.isEmpty()) {
            return AuthResult.failure("invalid_username");
        }
        if (password == null || password.isEmpty()) {
            return AuthResult.failure("empty_password");
        }
        String remoteFailureKey = remoteFailureKey(remoteAddress);
        AccountRecord record;
        File file = accountFile(normalized);
        if (isSymbolicLink(accountDirectory) || isSymbolicLink(file)) {
            return AuthResult.failure("account_record_invalid");
        }
        if (!file.isFile()) {
            if (!Constants.ACCOUNT_AUTH_AUTO_CREATE) {
                if (!Constants.ACCOUNT_AUTH_LEGACY_FALLBACK) {
                    AuthResult throttled = throttleResult(remoteFailureKey);
                    if (throttled != null) {
                        return throttled;
                    }
                    recordFailedAuth(remoteFailureKey, MAX_REMOTE_FAILED_AUTH_ATTEMPTS);
                }
                return AuthResult.failure("account_not_found", Constants.ACCOUNT_AUTH_LEGACY_FALLBACK);
            }
            try {
                record = create(normalized, password);
            } catch (IOException | GeneralSecurityException e) {
                return AuthResult.failure("account_create_failed");
            }
            return AuthResult.success("created", record);
        }
        record = load(normalized);
        if (record == null) {
            return AuthResult.failure("account_record_invalid");
        }
        if (!isStrongEnoughForCurrentMode(record)) {
            return AuthResult.failure("account_record_weak_hash");
        }
        String accountFailureKey = accountFailureKey(normalized);
        AuthResult throttled = throttleResult(accountFailureKey);
        if (throttled == null) {
            throttled = throttleResult(remoteFailureKey);
        }
        if (throttled != null) {
            return throttled;
        }
        if (record.disabled) {
            return AuthResult.failure("account_disabled");
        }
        try {
            if (!verify(password, record)) {
                recordFailedAuth(accountFailureKey, MAX_FAILED_AUTH_ATTEMPTS);
                recordFailedAuth(remoteFailureKey, MAX_REMOTE_FAILED_AUTH_ATTEMPTS);
                return AuthResult.failure("invalid_password");
            }
        } catch (GeneralSecurityException | RuntimeException e) {
            recordFailedAuth(accountFailureKey, MAX_FAILED_AUTH_ATTEMPTS);
            recordFailedAuth(remoteFailureKey, MAX_REMOTE_FAILED_AUTH_ATTEMPTS);
            return AuthResult.failure("password_verify_failed");
        }
        if (!isCharacterAllowed(record, normalized)) {
            return AuthResult.failure("character_not_allowed");
        }
        clearFailedAuth(accountFailureKey);
        return AuthResult.success("verified", record);
    }

    public AccountRecord create(String username, String password) throws IOException, GeneralSecurityException {
        String normalized = normalizeUsername(username);
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException("invalid username");
        }
        if (password == null || password.isEmpty()) {
            throw new IllegalArgumentException("password is required");
        }
        accountDirectory.mkdirs();
        AccountRecord record = new AccountRecord();
        record.username = normalized;
        record.algorithm = selectAlgorithm();
        record.passwordIterations = Math.max(localMinimumIterations(), Constants.ACCOUNT_AUTH_PBKDF2_ITERATIONS);
        byte[] salt = new byte[SALT_BYTES];
        secureRandom.nextBytes(salt);
        record.passwordSalt = Base64.getEncoder().encodeToString(salt);
        record.passwordHash = hash(password.toCharArray(), salt, record.passwordIterations, record.algorithm);
        record.createdAt = System.currentTimeMillis();
        record.disabled = false;
        save(record);
        return record;
    }

    public AccountRecord load(String username) {
        String normalized = normalizeUsername(username);
        if (normalized.isEmpty()) {
            return null;
        }
        File file = accountFile(normalized);
        if (isSymbolicLink(accountDirectory) || isSymbolicLink(file) || !file.isFile()) {
            return null;
        }
        try (FileReader reader = new FileReader(file)) {
            AccountRecord record = GSON.fromJson(reader, AccountRecord.class);
            if (!isValidRecord(record, normalized)) {
                return null;
            }
            return record;
        } catch (IOException | RuntimeException e) {
            return null;
        }
    }

    public void save(AccountRecord record) throws IOException {
        File file = accountFile(record.username);
        preparePrivateAccountFile(file);
        try (Writer writer = Files.newBufferedWriter(file.toPath(), StandardCharsets.UTF_8,
                StandardOpenOption.WRITE, StandardOpenOption.TRUNCATE_EXISTING)) {
            GSON.toJson(record, writer);
        }
        restrictFile(file);
    }

    public File accountFile(String username) {
        return new File(accountDirectory, safeFileName(normalizeUsername(username)) + ".json");
    }

    static String normalizeUsername(String username) {
        String normalized = username == null ? "" : username.trim().toLowerCase(Locale.US);
        if (!normalized.matches("[a-z0-9 .]{1,12}")) {
            return "";
        }
        return normalized;
    }

    private boolean verify(String password, AccountRecord record) throws GeneralSecurityException {
        byte[] salt = Base64.getDecoder().decode(record.passwordSalt);
        String algorithm = record.algorithm == null || record.algorithm.trim().isEmpty()
                ? DEFAULT_ALGORITHM : record.algorithm;
        String actual = hash(password.toCharArray(), salt, record.passwordIterations, algorithm);
        byte[] expectedBytes = Base64.getDecoder().decode(record.passwordHash);
        byte[] actualBytes = Base64.getDecoder().decode(actual);
        return constantTimeEquals(expectedBytes, actualBytes);
    }

    private String hash(char[] password, byte[] salt, int iterations, String algorithm) throws GeneralSecurityException {
        PBEKeySpec spec = new PBEKeySpec(password, salt, iterations, HASH_BITS);
        SecretKeyFactory factory = SecretKeyFactory.getInstance(algorithm);
        return Base64.getEncoder().encodeToString(factory.generateSecret(spec).getEncoded());
    }

    private String selectAlgorithm() {
        try {
            SecretKeyFactory.getInstance(DEFAULT_ALGORITHM);
            return DEFAULT_ALGORITHM;
        } catch (GeneralSecurityException e) {
            return FALLBACK_ALGORITHM;
        }
    }

    private static boolean isStrongEnoughForCurrentMode(AccountRecord record) {
        if (!Constants.EXTERNAL_PLAYERS_ENABLED) {
            return true;
        }
        return record != null && record.passwordIterations >= externalMinimumIterations();
    }

    private static int localMinimumIterations() {
        return 10000;
    }

    private static int externalMinimumIterations() {
        return Math.max(MIN_EXTERNAL_ITERATIONS, Constants.ACCOUNT_AUTH_PBKDF2_ITERATIONS);
    }

    private static boolean isValidRecord(AccountRecord record, String expectedUsername) {
        if (record == null || !expectedUsername.equals(normalizeUsername(record.username))) {
            return false;
        }
        if (!isSupportedAlgorithm(record.algorithm)) {
            return false;
        }
        if (record.passwordIterations < localMinimumIterations()) {
            return false;
        }
        if (!isExpectedBase64Length(record.passwordSalt, SALT_BYTES)
                || !isExpectedBase64Length(record.passwordHash, EXPECTED_HASH_BYTES)) {
            return false;
        }
        if (!isValidRoleList(record.roles) || !isValidCharacterList(record.allowedCharacters)) {
            return false;
        }
        return isValidDiscordUserId(record.discordUserId);
    }

    private static boolean isSupportedAlgorithm(String algorithm) {
        return DEFAULT_ALGORITHM.equals(algorithm) || FALLBACK_ALGORITHM.equals(algorithm);
    }

    private static boolean isExpectedBase64Length(String value, int expectedLength) {
        if (value == null || value.trim().isEmpty()) {
            return false;
        }
        try {
            return Base64.getDecoder().decode(value.trim()).length == expectedLength;
        } catch (IllegalArgumentException e) {
            return false;
        }
    }

    private static boolean isValidRoleList(List<String> roles) {
        if (roles == null) {
            return false;
        }
        for (String role : roles) {
            if (role == null || !role.trim().matches("[A-Za-z0-9_.:-]{1,32}")) {
                return false;
            }
        }
        return true;
    }

    private static boolean isValidCharacterList(List<String> characters) {
        if (characters == null) {
            return false;
        }
        for (String character : characters) {
            if (normalizeUsername(character).isEmpty()) {
                return false;
            }
        }
        return true;
    }

    private static boolean isValidDiscordUserId(String discordUserId) {
        return discordUserId == null || discordUserId.trim().matches("\\d{15,25}");
    }

    private static boolean isCharacterAllowed(AccountRecord record, String normalizedUsername) {
        if (record.allowedCharacters.isEmpty()) {
            return true;
        }
        for (String character : record.allowedCharacters) {
            if (normalizedUsername.equals(normalizeUsername(character))) {
                return true;
            }
        }
        return false;
    }

    private static boolean constantTimeEquals(byte[] expected, byte[] actual) {
        if (expected == null || actual == null) {
            return false;
        }
        int diff = expected.length ^ actual.length;
        int length = Math.min(expected.length, actual.length);
        for (int i = 0; i < length; i++) {
            diff |= expected[i] ^ actual[i];
        }
        return diff == 0;
    }

    private static String safeFileName(String normalizedUsername) {
        return normalizedUsername.replace(' ', '_').replaceAll("[^a-z0-9._-]", "_");
    }

    private static String accountFailureKey(String normalizedUsername) {
        return "account:" + normalizedUsername;
    }

    private static String remoteFailureKey(String remoteAddress) {
        String normalized = normalizeRemoteAddress(remoteAddress);
        return normalized.isEmpty() ? "" : "remote:" + normalized;
    }

    private static String normalizeRemoteAddress(String remoteAddress) {
        String normalized = remoteAddress == null ? "" : remoteAddress.trim().toLowerCase(Locale.US);
        if (normalized.length() > 128) {
            normalized = normalized.substring(0, 128);
        }
        return normalized;
    }

    private AuthResult throttleResult(String failureKey) {
        if (failureKey == null || failureKey.isEmpty()) {
            return null;
        }
        FailedAuthState state = failedAuthStates.get(failureKey);
        if (state == null) {
            return null;
        }
        long now = System.currentTimeMillis();
        synchronized (state) {
            if (state.lockedUntil > now) {
                return AuthResult.failure("rate_limited");
            }
            if (now - state.windowStartedAt > FAILED_AUTH_WINDOW_MS) {
                failedAuthStates.remove(failureKey, state);
            }
        }
        return null;
    }

    private void recordFailedAuth(String failureKey, int maxFailures) {
        if (failureKey == null || failureKey.isEmpty()) {
            return;
        }
        long now = System.currentTimeMillis();
        FailedAuthState state = failedAuthStates.get(failureKey);
        if (state == null) {
            pruneExpiredFailedAuthStates(now);
            if (isRemoteFailureKey(failureKey) && failedAuthStates.size() >= MAX_FAILED_AUTH_STATES) {
                return;
            }
            FailedAuthState created = new FailedAuthState(now);
            FailedAuthState previous = failedAuthStates.putIfAbsent(failureKey, created);
            state = previous == null ? created : previous;
        }
        synchronized (state) {
            if (now - state.windowStartedAt > FAILED_AUTH_WINDOW_MS) {
                state.windowStartedAt = now;
                state.failures = 0;
                state.lockedUntil = 0L;
            }
            state.failures++;
            if (state.failures >= maxFailures) {
                state.lockedUntil = now + FAILED_AUTH_LOCKOUT_MS;
            }
        }
    }

    private void pruneExpiredFailedAuthStates(long now) {
        if (failedAuthStates.size() < MAX_FAILED_AUTH_STATES) {
            return;
        }
        for (Map.Entry<String, FailedAuthState> entry : failedAuthStates.entrySet()) {
            FailedAuthState state = entry.getValue();
            synchronized (state) {
                if (state.lockedUntil <= now && now - state.windowStartedAt > FAILED_AUTH_WINDOW_MS) {
                    failedAuthStates.remove(entry.getKey(), state);
                }
            }
        }
    }

    private static boolean isRemoteFailureKey(String failureKey) {
        return failureKey != null && failureKey.startsWith("remote:");
    }

    private void clearFailedAuth(String failureKey) {
        if (failureKey != null && !failureKey.isEmpty()) {
            failedAuthStates.remove(failureKey);
        }
    }

    int failedAuthStateCountForTest() {
        return failedAuthStates.size();
    }

    private static void preparePrivateAccountFile(File file) throws IOException {
        File parent = file.getParentFile();
        if (parent != null) {
            if (isSymbolicLink(parent)) {
                throw new IOException("Refusing to use symlinked account directory: " + parent.getPath());
            }
            Files.createDirectories(parent.toPath());
            restrictDirectory(parent);
        }
        Path path = file.toPath();
        if (Files.isSymbolicLink(path)) {
            throw new IOException("Refusing to use symlinked account file: " + file.getPath());
        }
        if (!Files.exists(path)) {
            try {
                Files.createFile(path, PosixFilePermissions.asFileAttribute(PRIVATE_FILE_PERMISSIONS));
            } catch (UnsupportedOperationException e) {
                Files.createFile(path);
            }
        }
        restrictFile(file);
    }

    private static boolean isSymbolicLink(File file) {
        return file != null && Files.isSymbolicLink(file.toPath());
    }

    private static void restrictDirectory(File directory) {
        try {
            Files.setPosixFilePermissions(directory.toPath(), PRIVATE_DIR_PERMISSIONS);
        } catch (IOException | UnsupportedOperationException ignored) {
            directory.setReadable(false, false);
            directory.setWritable(false, false);
            directory.setExecutable(false, false);
            directory.setReadable(true, true);
            directory.setWritable(true, true);
            directory.setExecutable(true, true);
        }
    }

    private static void restrictFile(File file) {
        try {
            Files.setPosixFilePermissions(file.toPath(), PRIVATE_FILE_PERMISSIONS);
        } catch (IOException | UnsupportedOperationException ignored) {
            file.setReadable(false, false);
            file.setWritable(false, false);
            file.setExecutable(false, false);
            file.setReadable(true, true);
            file.setWritable(true, true);
        }
    }

    public static class AuthResult {
        public final boolean success;
        public final String status;
        public final AccountRecord account;
        public final boolean legacyFallbackAllowed;

        private AuthResult(boolean success, String status, AccountRecord account, boolean legacyFallbackAllowed) {
            this.success = success;
            this.status = status;
            this.account = account;
            this.legacyFallbackAllowed = legacyFallbackAllowed;
        }

        private static AuthResult success(String status, AccountRecord account) {
            return new AuthResult(true, status, account, false);
        }

        private static AuthResult failure(String status) {
            return failure(status, false);
        }

        private static AuthResult failure(String status, boolean legacyFallbackAllowed) {
            return new AuthResult(false, status, null, legacyFallbackAllowed);
        }
    }

    public static class AccountRecord {
        public String username;
        public String passwordHash;
        public String passwordSalt;
        public int passwordIterations;
        public String algorithm;
        public long createdAt;
        public boolean disabled;
        public List<String> roles = new ArrayList<String>();
        public List<String> allowedCharacters = new ArrayList<String>();
        public String discordUserId;
    }

    private static class FailedAuthState {
        private long windowStartedAt;
        private int failures;
        private long lockedUntil;

        private FailedAuthState(long windowStartedAt) {
            this.windowStartedAt = windowStartedAt;
        }
    }
}
