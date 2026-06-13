package com.rs2;

import com.rs2.integrations.PlayersOnlineWebsite;
import com.rs2.integrations.RegisteredAccsWebsite;
import com.rs2.integrations.discord.DiscordAgentTransport;
import com.rs2.integrations.discord.JavaCord;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.PosixFilePermission;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

public class ConfigLoader {

    private static final int MIN_EXTERNAL_ACCOUNT_AUTH_PBKDF2_ITERATIONS = 120000;
    private static final Set<PosixFilePermission> PRIVATE_FILE_PERMISSIONS = EnumSet.of(
            PosixFilePermission.OWNER_READ,
            PosixFilePermission.OWNER_WRITE);

    public static void loadSettings(String config) throws IOException {
        String out;
        try (BufferedReader br = new BufferedReader(new FileReader(config))) {
            out = br.lines().collect(Collectors.joining("\n"));
        }
        JSONObject obj = new JSONObject(out);

        if (obj.has("server_name"))
            Constants.SERVER_NAME = obj.getString("server_name");
        if (obj.has("server_test_version"))
            Constants.TEST_VERSION = obj.getDouble("server_test_version");
        if (obj.has("gui_enabled"))
            Constants.GUI_ENABLED = obj.getBoolean("gui_enabled");
        if (obj.has("website_link"))
            Constants.WEBSITE_LINK = obj.getString("website_link");
        if (obj.has("server_debug"))
            Constants.SERVER_DEBUG = obj.getBoolean("server_debug");
        if (obj.has("file_server"))
            Constants.FILE_SERVER = obj.getBoolean("file_server");
        if (obj.has("game_bind_host"))
            Constants.GAME_BIND_HOST = readSingleLineString(obj, "game_bind_host");
        if (obj.has("game_bind_hosts"))
            Constants.GAME_BIND_HOSTS = readStringList(obj, "game_bind_hosts");
        else if (obj.has("game_bind_host"))
            Constants.GAME_BIND_HOSTS = new String[0];
        if (obj.has("game_port"))
            Constants.GAME_PORT = obj.getInt("game_port");
        if (obj.has("http_bind_host"))
            Constants.HTTP_BIND_HOST = readSingleLineString(obj, "http_bind_host");
        if (obj.has("http_bind_hosts"))
            Constants.HTTP_BIND_HOSTS = readStringList(obj, "http_bind_hosts");
        else if (obj.has("http_bind_host"))
            Constants.HTTP_BIND_HOSTS = new String[0];
        if (obj.has("http_port"))
            Constants.HTTP_PORT = obj.getInt("http_port");
        if (obj.has("jaggrab_bind_host"))
            Constants.JAGGRAB_BIND_HOST = readSingleLineString(obj, "jaggrab_bind_host");
        if (obj.has("jaggrab_bind_hosts"))
            Constants.JAGGRAB_BIND_HOSTS = readStringList(obj, "jaggrab_bind_hosts");
        else if (obj.has("jaggrab_bind_host"))
            Constants.JAGGRAB_BIND_HOSTS = new String[0];
        if (obj.has("jaggrab_port"))
            Constants.JAGGRAB_PORT = obj.getInt("jaggrab_port");
        if (obj.has("public_game_host"))
            Constants.PUBLIC_GAME_HOST = readSingleLineString(obj, "public_game_host");
        if (obj.has("external_players_enabled"))
            Constants.EXTERNAL_PLAYERS_ENABLED = obj.getBoolean("external_players_enabled");
        if (obj.has("external_transport_mode"))
            Constants.EXTERNAL_TRANSPORT_MODE = readSingleLineString(obj, "external_transport_mode");
        if (obj.has("require_secure_external_transport"))
            Constants.REQUIRE_SECURE_EXTERNAL_TRANSPORT = obj.getBoolean("require_secure_external_transport");
        if (obj.has("secure_external_transport_confirmed"))
            Constants.SECURE_EXTERNAL_TRANSPORT_CONFIRMED = obj.getBoolean("secure_external_transport_confirmed");
        if (obj.has("direct_tcp_external_transport_confirmed"))
            Constants.DIRECT_TCP_EXTERNAL_TRANSPORT_CONFIRMED = obj.getBoolean("direct_tcp_external_transport_confirmed");
        if (obj.has("wildcard_bind_confirmed"))
            Constants.WILDCARD_BIND_CONFIRMED = obj.getBoolean("wildcard_bind_confirmed");
        if (obj.has("agent_chat_discord_enabled"))
            Constants.AGENT_CHAT_DISCORD_ENABLED = obj.getBoolean("agent_chat_discord_enabled");
        if (obj.has("agent_chat_log_enabled"))
            Constants.AGENT_CHAT_LOG_ENABLED = obj.getBoolean("agent_chat_log_enabled");
        if (obj.has("agent_bridge_bind_host"))
            Constants.AGENT_BRIDGE_BIND_HOST = readSingleLineString(obj, "agent_bridge_bind_host");
        if (obj.has("agent_bridge_port"))
            Constants.AGENT_BRIDGE_PORT = obj.getInt("agent_bridge_port");
        if (obj.has("account_auth_enabled"))
            Constants.ACCOUNT_AUTH_ENABLED = obj.getBoolean("account_auth_enabled");
        if (obj.has("account_auth_auto_create"))
            Constants.ACCOUNT_AUTH_AUTO_CREATE = obj.getBoolean("account_auth_auto_create");
        if (obj.has("account_auth_legacy_fallback"))
            Constants.ACCOUNT_AUTH_LEGACY_FALLBACK = obj.getBoolean("account_auth_legacy_fallback");
        if (obj.has("account_auth_pbkdf2_iterations"))
            Constants.ACCOUNT_AUTH_PBKDF2_ITERATIONS = obj.getInt("account_auth_pbkdf2_iterations");
        if (obj.has("world_id"))
            Constants.WORLD = obj.getInt("world_id");
        if (obj.has("members_only"))
            Constants.MEMBERS_ONLY = obj.getBoolean("members_only");
        if (obj.has("tutorial_island_enabled"))
            Constants.TUTORIAL_ISLAND = obj.getBoolean("tutorial_island_enabled");
        if (obj.has("party_room_enabled"))
            Constants.PARTY_ROOM_DISABLED = !obj.getBoolean("party_room_enabled");
        if (obj.has("clues_enabled"))
            Constants.CLUES_ENABLED = obj.getBoolean("clues_enabled");
        if (obj.has("admin_can_trade"))
            Constants.ADMIN_CAN_TRADE = obj.getBoolean("admin_can_trade");
        if (obj.has("admin_can_drop_items"))
            Constants.ADMIN_DROP_ITEMS = obj.getBoolean("admin_can_drop_items");
        if (obj.has("admin_can_sell"))
            Constants.ADMIN_CAN_SELL_ITEMS = obj.getBoolean("admin_can_sell");
        if (obj.has("respawn_x"))
            Constants.RESPAWN_X = obj.getInt("respawn_x");
        if (obj.has("respawn_y"))
            Constants.RESPAWN_Y = obj.getInt("respawn_y");
        if (obj.has("save_timer"))
            Constants.SAVE_TIMER = obj.getInt("save_timer");
        if (obj.has("timeout"))
            Constants.TIMEOUT = obj.getInt("timeout");
        if (obj.has("item_requirements"))
            Constants.ITEM_REQUIREMENTS = obj.getBoolean("item_requirements");
        if (obj.has("variable_xp_rate"))
            Constants.VARIABLE_XP_RATE = obj.getBoolean("variable_xp_rate");
        if (obj.has("xp_rate"))
            Constants.XP_RATE = obj.getDouble("xp_rate");
        if (obj.has("max_players"))
            Constants.MAX_PLAYERS = obj.getInt("max_players");
        if (obj.has("variable_xp_rates")) {
            JSONArray rates = obj.optJSONArray("variable_xp_rates");
            for (int i = 0; i < rates.length(); ++i) {
                Constants.VARIABLE_XP_RATES[i] = rates.optInt(i);
            }
        }
        if (obj.has("website_integration"))
            Constants.WEBSITE_INTEGRATION = obj.getBoolean("website_integration");
        
        if (obj.has("cycle_logging")) 
            Constants.CYCLE_LOGGING = obj.getBoolean("cycle_logging");
        if (obj.has("cycle_logging_tick")) 
            Constants.CYCLE_LOGGING_TICK = obj.getInt("cycle_logging_tick");
        if (obj.has("performance_logging"))
            Constants.PERFORMANCE_LOGGING = obj.getBoolean("performance_logging");
        validateNetworkSettings();
    }

    private static void initialize() {
        try {
            writeDefaultSecretsFile(new File("data/secrets.json"));
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    static void writeDefaultSecretsFileForTest(File secretsFile) throws IOException {
        writeDefaultSecretsFile(secretsFile);
    }

    static void prepareExistingSecretsFileForTest(File secretsFile) throws IOException {
        prepareExistingSecretsFile(secretsFile);
    }

    private static void writeDefaultSecretsFile(File secretsFile) throws IOException {
        JSONObject main = new JSONObject();
        main
                .put("bot-token", "")
                .put("agent-discord-bots", new JSONArray())
                .put("websitepass", "")
                .put("erssecret", "");
        preparePrivateSecretsFile(secretsFile);
        Files.write(secretsFile.toPath(), main.toString().getBytes(StandardCharsets.UTF_8),
                StandardOpenOption.TRUNCATE_EXISTING);
        restrictFile(secretsFile);
    }

    private static void preparePrivateSecretsFile(File file) throws IOException {
        File parent = file.getParentFile();
        if (parent != null) {
            Files.createDirectories(parent.toPath());
        }
        Path path = file.toPath();
        if (!Files.exists(path)) {
            try {
                Files.createFile(path, PosixFilePermissions.asFileAttribute(PRIVATE_FILE_PERMISSIONS));
            } catch (UnsupportedOperationException e) {
                Files.createFile(path);
            }
        }
        restrictFile(file);
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

    private static void prepareExistingSecretsFile(File file) throws IOException {
        Path path = file.toPath();
        if (Files.isSymbolicLink(path)) {
            throw new IOException("Refusing to load symlinked secrets file: " + file.getPath());
        }
        restrictFile(file);
    }

    public static void loadSecrets() throws IOException {
        File secretsFile = new File("data/secrets.json");
        if (!secretsFile.exists()) {
            initialize();
            System.out.println("Please open \"data/secrets.json\" file and enter your discord token bot there!");
            System.out.println("Please open \"data/secrets.json\" file and enter your Website Password there!");

        } else {
            prepareExistingSecretsFile(secretsFile);
            String out;
            try (BufferedReader br = new BufferedReader(new FileReader(secretsFile))) {
                out = br.lines().collect(Collectors.joining("\n"));
            }
            JSONObject obj = new JSONObject(out);

            /*
             * Sets External Services Vars
             */
            if (obj.has("bot-token"))
                JavaCord.token = obj.getString("bot-token");
            if (obj.has("agent-discord-bots"))
                DiscordAgentTransport.INSTANCE.configure(obj.optJSONArray("agent-discord-bots"));
            if (obj.has("websitepass")) {
                PlayersOnlineWebsite.password = obj.getString("websitepass");
                RegisteredAccsWebsite.password = obj.getString("websitepass");
            }
            if (obj.has("erssecret"))
                GameEngine.ersSecret = obj.getString("erssecret");

        }
    }

    private static void validateNetworkSettings() throws IOException {
        validateConfiguredPorts();
        validateBindHostSet("game_bind_hosts", effectiveHosts(Constants.GAME_BIND_HOSTS, Constants.GAME_BIND_HOST));
        if (Constants.FILE_SERVER) {
            validateBindHostSet("http_bind_hosts", effectiveHosts(Constants.HTTP_BIND_HOSTS, Constants.HTTP_BIND_HOST));
            validateBindHostSet("jaggrab_bind_hosts", effectiveHosts(Constants.JAGGRAB_BIND_HOSTS, Constants.JAGGRAB_BIND_HOST));
        }
        if (!Constants.EXTERNAL_PLAYERS_ENABLED) {
            return;
        }
        if (!Constants.ACCOUNT_AUTH_ENABLED) {
            throw new IOException("external_players_enabled requires account_auth_enabled=true so external logins use PBKDF2 account records instead of legacy character-password auth.");
        }
        if (Constants.ACCOUNT_AUTH_AUTO_CREATE) {
            throw new IOException("external_players_enabled requires account_auth_auto_create=false. Create external account records intentionally with scripts/create-account.py.");
        }
        if (Constants.ACCOUNT_AUTH_LEGACY_FALLBACK) {
            throw new IOException("external_players_enabled requires account_auth_legacy_fallback=false so missing, invalid, or wrong PBKDF2 account records fail closed.");
        }
        if (Constants.ACCOUNT_AUTH_PBKDF2_ITERATIONS < MIN_EXTERNAL_ACCOUNT_AUTH_PBKDF2_ITERATIONS) {
            throw new IOException("external_players_enabled requires account_auth_pbkdf2_iterations >= "
                    + MIN_EXTERNAL_ACCOUNT_AUTH_PBKDF2_ITERATIONS + ".");
        }
        requireSingleLineValue("external_transport_mode", Constants.EXTERNAL_TRANSPORT_MODE);
        requireSingleLineValue("public_game_host", Constants.PUBLIC_GAME_HOST);
        String mode = Constants.EXTERNAL_TRANSPORT_MODE == null ? "" : Constants.EXTERNAL_TRANSPORT_MODE.trim().toLowerCase();
        boolean secureTransportMode = "tailscale".equals(mode) || "wireguard".equals(mode) || "vpn".equals(mode)
                || "client_tls_tunnel".equals(mode);
        boolean directTcpMode = "direct_tcp".equals(mode);
        if (!(secureTransportMode || directTcpMode)) {
            throw new IOException("external_transport_mode must be one of direct_tcp, tailscale, wireguard, vpn, or client_tls_tunnel for external players.");
        }
        if (directTcpMode) {
            if (Constants.REQUIRE_SECURE_EXTERNAL_TRANSPORT) {
                throw new IOException("external_transport_mode=direct_tcp requires require_secure_external_transport=false because the legacy Java client connects over plaintext TCP.");
            }
            if (!Constants.DIRECT_TCP_EXTERNAL_TRANSPORT_CONFIRMED) {
                throw new IOException("external_transport_mode=direct_tcp requires direct_tcp_external_transport_confirmed=true to acknowledge plaintext public game/cache sockets.");
            }
        } else {
            if (!Constants.REQUIRE_SECURE_EXTERNAL_TRANSPORT) {
                throw new IOException("external_players_enabled requires require_secure_external_transport=true unless external_transport_mode=direct_tcp.");
            }
            if (!Constants.SECURE_EXTERNAL_TRANSPORT_CONFIRMED) {
                throw new IOException("external_players_enabled requires secure_external_transport_confirmed=true for Tailscale, WireGuard, VPN, or client_tls_tunnel modes.");
            }
        }
        if (isLoopbackOrWildcardHost(Constants.PUBLIC_GAME_HOST)) {
            throw new IOException("external_players_enabled requires public_game_host to be a reachable external host name or address, not localhost, loopback, or wildcard.");
        }
        boolean clientTlsTunnel = "client_tls_tunnel".equals(mode);
        if (!clientTlsTunnel && allLoopbackHosts(effectiveHosts(Constants.GAME_BIND_HOSTS, Constants.GAME_BIND_HOST))) {
            throw new IOException("external_players_enabled requires at least one non-loopback game bind host so external clients can connect over the selected transport.");
        }
        if (!clientTlsTunnel && Constants.FILE_SERVER
                && allLoopbackHosts(effectiveHosts(Constants.HTTP_BIND_HOSTS, Constants.HTTP_BIND_HOST))) {
            throw new IOException("external_players_enabled with file_server=true requires at least one non-loopback HTTP cache bind host.");
        }
        if (!clientTlsTunnel && Constants.FILE_SERVER
                && allLoopbackHosts(effectiveHosts(Constants.JAGGRAB_BIND_HOSTS, Constants.JAGGRAB_BIND_HOST))) {
            throw new IOException("external_players_enabled with file_server=true requires at least one non-loopback JAGGRAB cache bind host.");
        }
        if (anyWildcardHost(effectiveHosts(Constants.GAME_BIND_HOSTS, Constants.GAME_BIND_HOST))
                || anyWildcardHost(effectiveHosts(Constants.HTTP_BIND_HOSTS, Constants.HTTP_BIND_HOST))
                || anyWildcardHost(effectiveHosts(Constants.JAGGRAB_BIND_HOSTS, Constants.JAGGRAB_BIND_HOST))) {
            if (!Constants.WILDCARD_BIND_CONFIRMED) {
                throw new IOException("external_players_enabled with wildcard bind hosts requires wildcard_bind_confirmed=true and a verified firewall boundary.");
            }
        }
    }

    private static void validateConfiguredPorts() throws IOException {
        int gamePort = effectiveGamePort();
        validatePort("game_port", gamePort);
        validatePort("http_port", Constants.HTTP_PORT);
        validatePort("jaggrab_port", Constants.JAGGRAB_PORT);
        validatePort("agent_bridge_port", Constants.AGENT_BRIDGE_PORT);
        validateAgentBridgeBind();
        if (Constants.FILE_SERVER && (gamePort == Constants.HTTP_PORT || gamePort == Constants.JAGGRAB_PORT
                || Constants.HTTP_PORT == Constants.JAGGRAB_PORT)) {
            throw new IOException("game_port, http_port, and jaggrab_port must be distinct when file_server=true.");
        }
        if (Constants.AGENT_BRIDGE_PORT == gamePort
                && anyLoopbackHost(effectiveHosts(Constants.GAME_BIND_HOSTS, Constants.GAME_BIND_HOST))) {
            throw new IOException("agent_bridge_port must not overlap game_port on a loopback game bind host.");
        }
        if (Constants.FILE_SERVER && Constants.AGENT_BRIDGE_PORT == Constants.HTTP_PORT
                && anyLoopbackHost(effectiveHosts(Constants.HTTP_BIND_HOSTS, Constants.HTTP_BIND_HOST))) {
            throw new IOException("agent_bridge_port must not overlap http_port on a loopback HTTP cache bind host.");
        }
        if (Constants.FILE_SERVER && Constants.AGENT_BRIDGE_PORT == Constants.JAGGRAB_PORT
                && anyLoopbackHost(effectiveHosts(Constants.JAGGRAB_BIND_HOSTS, Constants.JAGGRAB_BIND_HOST))) {
            throw new IOException("agent_bridge_port must not overlap jaggrab_port on a loopback JAGGRAB cache bind host.");
        }
    }

    private static int effectiveGamePort() {
        return Constants.GAME_PORT > 0 ? Constants.GAME_PORT
                : (Constants.WORLD == 1 ? 43594 : 43596 + Constants.WORLD);
    }

    private static void validatePort(String name, int port) throws IOException {
        if (port < 1 || port > 65535) {
            throw new IOException(name + " must be between 1 and 65535.");
        }
    }

    private static void validateAgentBridgeBind() throws IOException {
        requireSingleLineValue("agent_bridge_bind_host", Constants.AGENT_BRIDGE_BIND_HOST);
        if (!isLoopbackHost(Constants.AGENT_BRIDGE_BIND_HOST)) {
            throw new IOException("agent_bridge_bind_host must be localhost or another loopback address. Do not expose the agent bridge externally.");
        }
    }

    private static void validateBindHostSet(String name, String[] hosts) throws IOException {
        if (hosts == null) {
            return;
        }
        boolean hasWildcard = false;
        ArrayList<String> uniqueHosts = new ArrayList<String>();
        for (String host : hosts) {
            requireSingleLineValue(name, host);
            String clean = host == null ? "" : host.trim().toLowerCase();
            if (clean.isEmpty()) {
                continue;
            }
            if (!uniqueHosts.contains(clean)) {
                uniqueHosts.add(clean);
            }
            if (isWildcardHost(clean)) {
                hasWildcard = true;
            }
        }
        if (hasWildcard && uniqueHosts.size() > 1) {
            throw new IOException(name + " must not mix wildcard bind hosts with specific hosts. Bind wildcard alone or list explicit interface hosts.");
        }
    }

    private static String[] readStringList(JSONObject obj, String key) throws IOException {
        List<String> values = new ArrayList<String>();
        Object raw = obj.opt(key);
        if (raw instanceof JSONArray) {
            JSONArray array = (JSONArray) raw;
            for (int i = 0; i < array.length(); i++) {
                Object value = array.opt(i);
                if (!(value instanceof String)) {
                    throw new IOException(key + "[" + i + "] must be a string.");
                }
                addNonBlank(values, (String) value, key + "[" + i + "]");
            }
        } else if (raw instanceof String) {
            String[] parts = ((String) raw).split(",");
            for (String part : parts) {
                addNonBlank(values, part, key);
            }
        } else {
            throw new IOException(key + " must be a string or array of strings.");
        }
        return values.toArray(new String[values.size()]);
    }

    private static String readSingleLineString(JSONObject obj, String key) throws IOException {
        String value = obj.getString(key);
        requireSingleLineValue(key, value);
        return value;
    }

    private static void addNonBlank(List<String> values, String value, String label) throws IOException {
        requireSingleLineValue(label, value);
        String clean = value == null ? "" : value.trim();
        if (!clean.isEmpty()) {
            values.add(clean);
        }
    }

    private static void requireSingleLineValue(String name, String value) throws IOException {
        if (value == null) {
            return;
        }
        for (int i = 0; i < value.length(); i++) {
            if (value.charAt(i) < 32) {
                throw new IOException(name + " must be a single-line value without control characters.");
            }
        }
    }

    private static String[] effectiveHosts(String[] hosts, String fallback) {
        if (hosts != null && hosts.length > 0) {
            return hosts;
        }
        return new String[] {fallback};
    }

    private static boolean allLoopbackHosts(String[] hosts) {
        if (hosts == null || hosts.length == 0) {
            return true;
        }
        for (String host : hosts) {
            if (!isLoopbackHost(host)) {
                return false;
            }
        }
        return true;
    }

    private static boolean anyLoopbackHost(String[] hosts) {
        if (hosts == null || hosts.length == 0) {
            return false;
        }
        for (String host : hosts) {
            if (isLoopbackHost(host)) {
                return true;
            }
        }
        return false;
    }

    private static boolean isLoopbackHost(String host) {
        String clean = host == null ? "" : host.trim().toLowerCase();
        return clean.length() == 0 || "localhost".equals(clean) || clean.startsWith("127.")
                || "::1".equals(clean) || "0:0:0:0:0:0:0:1".equals(clean);
    }

    private static boolean isLoopbackOrWildcardHost(String host) {
        String clean = host == null ? "" : host.trim().toLowerCase();
        return isLoopbackHost(clean) || isWildcardHost(clean);
    }

    private static boolean anyWildcardHost(String[] hosts) {
        if (hosts == null) {
            return false;
        }
        for (String host : hosts) {
            if (isWildcardHost(host)) {
                return true;
            }
        }
        return false;
    }

    private static boolean isWildcardHost(String host) {
        String clean = host == null ? "" : host.trim().toLowerCase();
        return "*".equals(clean) || "0.0.0.0".equals(clean) || "::".equals(clean);
    }
}
