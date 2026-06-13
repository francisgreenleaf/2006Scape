package com.rs2;

import static org.junit.Assert.assertEquals;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;

import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public class ConfigLoaderNetworkTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    private boolean previousExternalPlayers;
    private boolean previousRequireSecureTransport;
    private boolean previousSecureTransportConfirmed;
    private boolean previousDirectTcpTransportConfirmed;
    private boolean previousWildcardBindConfirmed;
    private String previousTransportMode;
    private String previousGameBindHost;
    private String previousHttpBindHost;
    private String previousJaggrabBindHost;
    private String[] previousGameBindHosts;
    private String[] previousHttpBindHosts;
    private String[] previousJaggrabBindHosts;
    private String previousPublicGameHost;
    private boolean previousFileServer;
    private int previousGamePort;
    private int previousHttpPort;
    private int previousJaggrabPort;
    private int previousWorld;
    private boolean previousAccountAuthEnabled;
    private boolean previousAccountAuthAutoCreate;
    private boolean previousAccountAuthLegacyFallback;
    private int previousAccountAuthIterations;
    private boolean previousAgentChatLogEnabled;
    private String previousAgentBridgeBindHost;
    private int previousAgentBridgePort;

    @Before
    public void setUp() {
        previousExternalPlayers = Constants.EXTERNAL_PLAYERS_ENABLED;
        previousRequireSecureTransport = Constants.REQUIRE_SECURE_EXTERNAL_TRANSPORT;
        previousSecureTransportConfirmed = Constants.SECURE_EXTERNAL_TRANSPORT_CONFIRMED;
        previousDirectTcpTransportConfirmed = Constants.DIRECT_TCP_EXTERNAL_TRANSPORT_CONFIRMED;
        previousWildcardBindConfirmed = Constants.WILDCARD_BIND_CONFIRMED;
        previousTransportMode = Constants.EXTERNAL_TRANSPORT_MODE;
        previousGameBindHost = Constants.GAME_BIND_HOST;
        previousHttpBindHost = Constants.HTTP_BIND_HOST;
        previousJaggrabBindHost = Constants.JAGGRAB_BIND_HOST;
        previousGameBindHosts = Constants.GAME_BIND_HOSTS;
        previousHttpBindHosts = Constants.HTTP_BIND_HOSTS;
        previousJaggrabBindHosts = Constants.JAGGRAB_BIND_HOSTS;
        previousPublicGameHost = Constants.PUBLIC_GAME_HOST;
        previousFileServer = Constants.FILE_SERVER;
        previousGamePort = Constants.GAME_PORT;
        previousHttpPort = Constants.HTTP_PORT;
        previousJaggrabPort = Constants.JAGGRAB_PORT;
        previousWorld = Constants.WORLD;
        previousAccountAuthEnabled = Constants.ACCOUNT_AUTH_ENABLED;
        previousAccountAuthAutoCreate = Constants.ACCOUNT_AUTH_AUTO_CREATE;
        previousAccountAuthLegacyFallback = Constants.ACCOUNT_AUTH_LEGACY_FALLBACK;
        previousAccountAuthIterations = Constants.ACCOUNT_AUTH_PBKDF2_ITERATIONS;
        previousAgentChatLogEnabled = Constants.AGENT_CHAT_LOG_ENABLED;
        previousAgentBridgeBindHost = Constants.AGENT_BRIDGE_BIND_HOST;
        previousAgentBridgePort = Constants.AGENT_BRIDGE_PORT;
        Constants.FILE_SERVER = true;
        Constants.GAME_PORT = -1;
        Constants.HTTP_PORT = 8080;
        Constants.JAGGRAB_PORT = 43595;
        Constants.AGENT_BRIDGE_BIND_HOST = "127.0.0.1";
        Constants.AGENT_BRIDGE_PORT = 43610;
        Constants.WORLD = 1;
    }

    @After
    public void tearDown() {
        Constants.EXTERNAL_PLAYERS_ENABLED = previousExternalPlayers;
        Constants.REQUIRE_SECURE_EXTERNAL_TRANSPORT = previousRequireSecureTransport;
        Constants.SECURE_EXTERNAL_TRANSPORT_CONFIRMED = previousSecureTransportConfirmed;
        Constants.DIRECT_TCP_EXTERNAL_TRANSPORT_CONFIRMED = previousDirectTcpTransportConfirmed;
        Constants.WILDCARD_BIND_CONFIRMED = previousWildcardBindConfirmed;
        Constants.EXTERNAL_TRANSPORT_MODE = previousTransportMode;
        Constants.GAME_BIND_HOST = previousGameBindHost;
        Constants.HTTP_BIND_HOST = previousHttpBindHost;
        Constants.JAGGRAB_BIND_HOST = previousJaggrabBindHost;
        Constants.GAME_BIND_HOSTS = previousGameBindHosts;
        Constants.HTTP_BIND_HOSTS = previousHttpBindHosts;
        Constants.JAGGRAB_BIND_HOSTS = previousJaggrabBindHosts;
        Constants.PUBLIC_GAME_HOST = previousPublicGameHost;
        Constants.FILE_SERVER = previousFileServer;
        Constants.GAME_PORT = previousGamePort;
        Constants.HTTP_PORT = previousHttpPort;
        Constants.JAGGRAB_PORT = previousJaggrabPort;
        Constants.WORLD = previousWorld;
        Constants.ACCOUNT_AUTH_ENABLED = previousAccountAuthEnabled;
        Constants.ACCOUNT_AUTH_AUTO_CREATE = previousAccountAuthAutoCreate;
        Constants.ACCOUNT_AUTH_LEGACY_FALLBACK = previousAccountAuthLegacyFallback;
        Constants.ACCOUNT_AUTH_PBKDF2_ITERATIONS = previousAccountAuthIterations;
        Constants.AGENT_CHAT_LOG_ENABLED = previousAgentChatLogEnabled;
        Constants.AGENT_BRIDGE_BIND_HOST = previousAgentBridgeBindHost;
        Constants.AGENT_BRIDGE_PORT = previousAgentBridgePort;
    }

    @Test(expected = IOException.class)
    public void externalModeRequiresSecureTransportConfirmation() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":false,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings()));
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsDisabledSecureTransportRequirement() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":false,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings()));
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsUnknownSecureTransportMode() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"plain_public_tcp\","
                        + externalAccountAuthSettings()));
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsControlCharacterTransportMode() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\\nplain_public_tcp\","
                        + externalAccountAuthSettings()
                        + ","
                        + externalServiceBindSettings("100.64.0.10")));
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsPrivateNetworkAsUnencryptedTransportMode() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"private_network\","
                        + externalAccountAuthSettings()
                        + ","
                        + externalServiceBindSettings("10.0.0.5")));
    }

    @Test(expected = IOException.class)
    public void directTcpModeRequiresPlaintextAcknowledgement() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":false,"
                        + "\"secure_external_transport_confirmed\":false,"
                        + "\"external_transport_mode\":\"direct_tcp\","
                        + externalAccountAuthSettings("server.example.com")
                        + ","
                        + externalServiceBindSettings("10.0.0.5")));
    }

    @Test(expected = IOException.class)
    public void directTcpModeRejectsSecureTransportRequirement() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"direct_tcp_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"direct_tcp\","
                        + externalAccountAuthSettings("server.example.com")
                        + ","
                        + externalServiceBindSettings("10.0.0.5")));
    }

    @Test
    public void directTcpModeAcceptsExplicitPlaintextExternalConfig() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":false,"
                        + "\"secure_external_transport_confirmed\":false,"
                        + "\"direct_tcp_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"direct_tcp\","
                        + externalAccountAuthSettings("server.example.com")
                        + ","
                        + externalServiceBindSettings("10.0.0.5")));

        assertEquals("direct_tcp", Constants.EXTERNAL_TRANSPORT_MODE);
        assertEquals(false, Constants.REQUIRE_SECURE_EXTERNAL_TRANSPORT);
        assertEquals(true, Constants.DIRECT_TCP_EXTERNAL_TRANSPORT_CONFIRMED);
    }

    @Test
    public void confirmedExternalModeAcceptsKnownSecureTransportMode() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"wireguard\","
                        + externalAccountAuthSettings()
                        + ","
                        + externalServiceBindSettings("10.0.0.5")));

        assertEquals("wireguard", Constants.EXTERNAL_TRANSPORT_MODE);
    }

    @Test
    public void localModeDoesNotRequireSecureTransportConfirmation() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":false,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":false,"
                        + "\"external_transport_mode\":\"local\""));

        assertEquals("local", Constants.EXTERNAL_TRANSPORT_MODE);
    }

    @Test(expected = IOException.class)
    public void localModeRejectsInvalidConfiguredPort() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":false,"
                        + "\"game_port\":70000"));
    }

    @Test(expected = IOException.class)
    public void fileServerModeRejectsOverlappingServicePorts() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":false,"
                        + "\"file_server\":true,"
                        + "\"game_port\":43594,"
                        + "\"http_port\":43594,"
                        + "\"jaggrab_port\":43595"));
    }

    @Test
    public void fileServerDisabledAllowsOverlappingCachePorts() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":false,"
                        + "\"file_server\":false,"
                        + "\"game_port\":43594,"
                        + "\"http_port\":43594,"
                        + "\"jaggrab_port\":43594"));

        assertEquals(false, Constants.FILE_SERVER);
        assertEquals(43594, Constants.GAME_PORT);
        assertEquals(43594, Constants.HTTP_PORT);
        assertEquals(43594, Constants.JAGGRAB_PORT);
    }

    @Test(expected = IOException.class)
    public void agentBridgeRejectsNonLoopbackBindHost() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":false,"
                        + "\"agent_bridge_bind_host\":\"10.0.0.5\""));
    }

    @Test(expected = IOException.class)
    public void agentBridgeRejectsControlCharacterBindHost() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":false,"
                        + "\"agent_bridge_bind_host\":\"127.0.0.1\\n0.0.0.0\""));
    }

    @Test(expected = IOException.class)
    public void agentBridgeRejectsInvalidPort() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":false,"
                        + "\"agent_bridge_port\":70000"));
    }

    @Test(expected = IOException.class)
    public void agentBridgeRejectsLoopbackGamePortOverlap() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":false,"
                        + "\"game_bind_host\":\"127.0.0.1\","
                        + "\"game_port\":43594,"
                        + "\"agent_bridge_port\":43594"));
    }

    @Test
    public void agentBridgeAcceptsAlternateLoopbackPort() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":false,"
                        + "\"agent_bridge_bind_host\":\"127.0.0.1\","
                        + "\"agent_bridge_port\":44610"));

        assertEquals("127.0.0.1", Constants.AGENT_BRIDGE_BIND_HOST);
        assertEquals(44610, Constants.AGENT_BRIDGE_PORT);
    }

    @Test(expected = IOException.class)
    public void externalModeRequiresAccountAuth() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + "\"account_auth_enabled\":false,"
                        + "\"account_auth_auto_create\":false,"
                        + "\"account_auth_legacy_fallback\":false"));
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsAccountAutoCreate() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + "\"account_auth_enabled\":true,"
                        + "\"account_auth_auto_create\":true,"
                        + "\"account_auth_legacy_fallback\":false"));
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsLegacyAuthFallback() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + "\"account_auth_enabled\":true,"
                        + "\"account_auth_auto_create\":false,"
                        + "\"account_auth_legacy_fallback\":true"));
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsWeakPbkdf2Iterations() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + "\"account_auth_enabled\":true,"
                        + "\"account_auth_auto_create\":false,"
                        + "\"account_auth_legacy_fallback\":false,"
                        + "\"account_auth_pbkdf2_iterations\":10000"));
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsLoopbackPublicHost() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings("localhost")
                        + ","
                        + "\"game_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"]"));
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsLoopbackOnlyGameBindHosts() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings()
                        + ","
                        + "\"game_bind_hosts\":[\"127.0.0.1\",\"localhost\"]"));
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsControlCharacterPublicHost() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings("example-tailnet-host\\nserver.port=1")
                        + ","
                        + externalServiceBindSettings("100.64.0.10")));
    }

    @Test
    public void clientTlsTunnelAllowsLoopbackOnlyGameAndCacheBindHosts() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"client_tls_tunnel\","
                        + externalAccountAuthSettings("tls.example.com")
                        + ","
                        + "\"game_bind_hosts\":[\"127.0.0.1\"],"
                        + "\"http_bind_hosts\":[\"127.0.0.1\"],"
                        + "\"jaggrab_bind_hosts\":[\"127.0.0.1\"]"));

        assertEquals("client_tls_tunnel", Constants.EXTERNAL_TRANSPORT_MODE);
        assertEquals("127.0.0.1", Constants.GAME_BIND_HOSTS[0]);
        assertEquals("127.0.0.1", Constants.HTTP_BIND_HOSTS[0]);
        assertEquals("127.0.0.1", Constants.JAGGRAB_BIND_HOSTS[0]);
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsWildcardBindWithoutExplicitConfirmation() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings()
                        + ","
                        + "\"game_bind_hosts\":[\"0.0.0.0\"]"));
    }

    @Test
    public void externalModeAllowsWildcardBindWithExplicitConfirmation() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + "\"wildcard_bind_confirmed\":true,"
                        + externalAccountAuthSettings()
                        + ","
                        + "\"game_bind_hosts\":[\"0.0.0.0\"],"
                        + "\"http_bind_hosts\":[\"0.0.0.0\"],"
                        + "\"jaggrab_bind_hosts\":[\"0.0.0.0\"]"));

        assertEquals(true, Constants.WILDCARD_BIND_CONFIRMED);
        assertEquals("0.0.0.0", Constants.GAME_BIND_HOSTS[0]);
    }

    @Test(expected = IOException.class)
    public void bindHostArraysRejectWildcardMixedWithSpecificHost() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + "\"wildcard_bind_confirmed\":true,"
                        + externalAccountAuthSettings()
                        + ","
                        + "\"game_bind_hosts\":[\"0.0.0.0\",\"127.0.0.1\"],"
                        + "\"http_bind_hosts\":[\"0.0.0.0\"],"
                        + "\"jaggrab_bind_hosts\":[\"0.0.0.0\"]"));
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsLoopbackOnlyHttpCacheBindHostsWhenFileServerEnabled() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings()
                        + ","
                        + "\"game_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"],"
                        + "\"http_bind_hosts\":[\"127.0.0.1\"],"
                        + "\"jaggrab_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"]"));
    }

    @Test(expected = IOException.class)
    public void externalModeRejectsLoopbackOnlyJaggrabCacheBindHostsWhenFileServerEnabled() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings()
                        + ","
                        + "\"game_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"],"
                        + "\"http_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"],"
                        + "\"jaggrab_bind_hosts\":[\"127.0.0.1\"]"));
    }

    @Test
    public void externalModeAllowsLoopbackOnlyCacheBindHostsWhenFileServerDisabled() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"file_server\":false,"
                        + "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings()
                        + ","
                        + "\"game_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"]"));

        assertEquals(false, Constants.FILE_SERVER);
    }

    @Test
    public void trackedLocalSampleKeepsLoopbackAndLegacyAuthDefaults() throws Exception {
        ConfigLoader.loadSettings(sampleConfig("ServerConfig.Sample.json"));

        assertEquals("127.0.0.1", Constants.GAME_BIND_HOST);
        assertEquals("127.0.0.1", Constants.HTTP_BIND_HOST);
        assertEquals("127.0.0.1", Constants.JAGGRAB_BIND_HOST);
        assertEquals("localhost", Constants.PUBLIC_GAME_HOST);
        assertEquals(false, Constants.EXTERNAL_PLAYERS_ENABLED);
        assertEquals(false, Constants.WILDCARD_BIND_CONFIRMED);
        assertEquals(false, Constants.ACCOUNT_AUTH_ENABLED);
        assertEquals(true, Constants.ACCOUNT_AUTH_LEGACY_FALLBACK);
        assertEquals(false, Constants.AGENT_CHAT_LOG_ENABLED);
    }

    @Test
    public void trackedExternalSampleEnablesDirectTcpAndAccountAuth() throws Exception {
        ConfigLoader.loadSettings(sampleConfig("ServerConfig.External.Sample.json"));

        assertEquals(true, Constants.EXTERNAL_PLAYERS_ENABLED);
        assertEquals(false, Constants.REQUIRE_SECURE_EXTERNAL_TRANSPORT);
        assertEquals(false, Constants.SECURE_EXTERNAL_TRANSPORT_CONFIRMED);
        assertEquals(true, Constants.DIRECT_TCP_EXTERNAL_TRANSPORT_CONFIRMED);
        assertEquals(false, Constants.WILDCARD_BIND_CONFIRMED);
        assertEquals("direct_tcp", Constants.EXTERNAL_TRANSPORT_MODE);
        assertEquals("server.example.com", Constants.PUBLIC_GAME_HOST);
        assertEquals(true, Constants.ACCOUNT_AUTH_ENABLED);
        assertEquals(false, Constants.ACCOUNT_AUTH_LEGACY_FALLBACK);
        assertEquals(120000, Constants.ACCOUNT_AUTH_PBKDF2_ITERATIONS);
        assertEquals(true, Constants.AGENT_CHAT_LOG_ENABLED);
    }

    @Test
    public void bindHostArraysSupportLocalAndPrivateExternalInterfaces() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings()
                        + ","
                        + "\"game_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"],"
                        + "\"http_bind_hosts\":\"127.0.0.1,100.64.0.10\","
                        + "\"jaggrab_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"]"));

        assertEquals(2, Constants.GAME_BIND_HOSTS.length);
        assertEquals("127.0.0.1", Constants.GAME_BIND_HOSTS[0]);
        assertEquals("100.64.0.10", Constants.GAME_BIND_HOSTS[1]);
        assertEquals(2, Constants.HTTP_BIND_HOSTS.length);
        assertEquals("100.64.0.10", Constants.HTTP_BIND_HOSTS[1]);
        assertEquals(2, Constants.JAGGRAB_BIND_HOSTS.length);
    }

    @Test(expected = IOException.class)
    public void bindHostArraysRejectNonStringValues() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings()
                        + ","
                        + "\"game_bind_hosts\":[\"127.0.0.1\",100],"
                        + "\"http_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"],"
                        + "\"jaggrab_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"]"));
    }

    @Test(expected = IOException.class)
    public void bindHostArraysRejectControlCharacterValues() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings()
                        + ","
                        + "\"game_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\\n0.0.0.0\"],"
                        + "\"http_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"],"
                        + "\"jaggrab_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"]"));
    }

    @Test(expected = IOException.class)
    public void bindHostArraysRejectObjectValues() throws Exception {
        ConfigLoader.loadSettings(config(
                "\"external_players_enabled\":true,"
                        + "\"require_secure_external_transport\":true,"
                        + "\"secure_external_transport_confirmed\":true,"
                        + "\"external_transport_mode\":\"tailscale\","
                        + externalAccountAuthSettings()
                        + ","
                        + "\"game_bind_hosts\":{\"host\":\"100.64.0.10\"},"
                        + "\"http_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"],"
                        + "\"jaggrab_bind_hosts\":[\"127.0.0.1\",\"100.64.0.10\"]"));
    }

    @Test
    public void singularBindHostClearsPreviousPluralBindHosts() throws Exception {
        Constants.GAME_BIND_HOSTS = new String[] {"127.0.0.1", "100.64.0.10"};
        Constants.HTTP_BIND_HOSTS = new String[] {"127.0.0.1", "100.64.0.10"};
        Constants.JAGGRAB_BIND_HOSTS = new String[] {"127.0.0.1", "100.64.0.10"};

        ConfigLoader.loadSettings(config(
                "\"game_bind_host\":\"127.0.0.1\","
                        + "\"http_bind_host\":\"127.0.0.1\","
                        + "\"jaggrab_bind_host\":\"127.0.0.1\""));

        assertEquals(0, Constants.GAME_BIND_HOSTS.length);
        assertEquals(0, Constants.HTTP_BIND_HOSTS.length);
        assertEquals(0, Constants.JAGGRAB_BIND_HOSTS.length);
    }

    private String config(String body) throws IOException {
        File file = temporaryFolder.newFile("ServerConfig.json");
        try (FileWriter writer = new FileWriter(file)) {
            writer.write("{");
            writer.write(body);
            writer.write("}");
        }
        return file.getAbsolutePath();
    }

    private String sampleConfig(String name) {
        return new File(System.getProperty("user.dir"), name).getAbsolutePath();
    }

    private static String externalAccountAuthSettings() {
        return externalAccountAuthSettings("example-tailnet-host");
    }

    private static String externalAccountAuthSettings(String publicGameHost) {
        return "\"account_auth_enabled\":true,"
                + "\"account_auth_auto_create\":false,"
                + "\"account_auth_legacy_fallback\":false,"
                + "\"account_auth_pbkdf2_iterations\":120000,"
                + "\"public_game_host\":\"" + publicGameHost + "\"";
    }

    private static String externalServiceBindSettings(String externalHost) {
        return "\"game_bind_hosts\":[\"127.0.0.1\",\"" + externalHost + "\"],"
                + "\"http_bind_hosts\":[\"127.0.0.1\",\"" + externalHost + "\"],"
                + "\"jaggrab_bind_hosts\":[\"127.0.0.1\",\"" + externalHost + "\"]";
    }
}
