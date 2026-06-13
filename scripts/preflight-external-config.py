#!/usr/bin/env python3
"""Validate a 2006Scape config before using it for external players."""

import argparse
import ipaddress
import json
from pathlib import Path


ALLOWED_SECURE_MODES = {
    "tailscale",
    "wireguard",
    "vpn",
    "client_tls_tunnel",
}
ALLOWED_DIRECT_MODES = {
    "direct_tcp",
}

LOOPBACK_HOSTS = {"", "localhost", "127.0.0.1", "::1"}
WILDCARD_HOSTS = {"*", "0.0.0.0", "::"}
TAILSCALE_CGNAT = ipaddress.ip_network("100.64.0.0/10")
MIN_EXTERNAL_PBKDF2_ITERATIONS = 120000


def fail(message):
    raise SystemExit("preflight failed: {}".format(message))


def warn(warnings, message):
    warnings.append(message)


def require_single_line_string(value, label, allow_empty=True):
    if value is None:
        value = ""
    if not isinstance(value, str):
        fail("{} must be a string".format(label))
    if not allow_empty and not value.strip():
        fail("{} must not be empty".format(label))
    if any(ord(ch) < 32 for ch in value):
        fail("{} must be a single-line value without control characters".format(label))
    return value


def load_config(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        fail("could not read {}: {}".format(path, exc))
    except json.JSONDecodeError as exc:
        fail("invalid JSON in {}: {}".format(path, exc))


def normalized_host(config, key, fallback=""):
    return require_single_line_string(config.get(key, fallback), key).strip().lower()


def normalized_hosts(config, plural_key, singular_key, fallback=""):
    raw = config.get(plural_key)
    values = []
    if isinstance(raw, list):
        for index, value in enumerate(raw):
            if not isinstance(value, str):
                fail("{}[{}] must be a string".format(plural_key, index))
            values.append(value)
    elif isinstance(raw, str):
        values = raw.split(",")
    elif raw is not None:
        fail("{} must be a string or array of strings".format(plural_key))
    if not values:
        singular = config.get(singular_key, fallback)
        if not isinstance(singular, str):
            fail("{} must be a string".format(singular_key))
        values = [singular]
    hosts = []
    for index, value in enumerate(values):
        host = require_single_line_string(value, "{}[{}]".format(plural_key, index)).strip().lower()
        if host:
            hosts.append(host)
    return hosts or [str(fallback or "").strip().lower()]


def require_port(config, key, fallback=None):
    value = config.get(key, fallback)
    try:
        port = int(value)
    except (TypeError, ValueError):
        fail("{} must be an integer port".format(key))
    if port < 1 or port > 65535:
        fail("{} must be between 1 and 65535".format(key))
    return port


def is_private_host(host):
    if host in WILDCARD_HOSTS:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        # DNS names are accepted; firewall/VPN proof happens outside this static check.
        return not is_loopback_host(host)
    return address.is_private or address.is_loopback or address.is_link_local or address in TAILSCALE_CGNAT


def is_loopback_host(host):
    clean = str(host or "").strip().lower()
    if clean in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(clean).is_loopback
    except ValueError:
        return False


def reject_mixed_wildcard_hosts(label, hosts):
    unique_hosts = []
    has_wildcard = False
    for host in hosts:
        if host and host not in unique_hosts:
            unique_hosts.append(host)
        if host in WILDCARD_HOSTS:
            has_wildcard = True
    if has_wildcard and len(unique_hosts) > 1:
        fail("{} must not mix wildcard bind hosts with specific hosts; bind wildcard alone or list explicit interface hosts".format(label))


def main():
    parser = argparse.ArgumentParser(description="Preflight a 2006Scape external-player server config.")
    parser.add_argument("config", type=Path)
    parser.add_argument("--allow-wildcard-bind", action="store_true",
            help="Allow 0.0.0.0/* binds; only use with a verified host firewall or private network.")
    args = parser.parse_args()

    config = load_config(args.config)
    warnings = []

    external = bool(config.get("external_players_enabled", False))
    if not external:
        print("ok: external_players_enabled is false; local/dev config only")
        return 0

    mode = require_single_line_string(config.get("external_transport_mode", ""), "external_transport_mode").strip().lower()
    if mode not in (ALLOWED_SECURE_MODES | ALLOWED_DIRECT_MODES):
        fail("external_transport_mode must be one of {}".format(
            ", ".join(sorted(ALLOWED_SECURE_MODES | ALLOWED_DIRECT_MODES))
        ))
    direct_tcp = mode == "direct_tcp"
    if direct_tcp:
        if bool(config.get("require_secure_external_transport", True)):
            fail("direct_tcp requires require_secure_external_transport=false because the Java client connects over plaintext TCP")
        if not bool(config.get("direct_tcp_external_transport_confirmed", False)):
            fail("direct_tcp_external_transport_confirmed must be true for direct_tcp external players")
        warn(warnings, "direct_tcp exposes plaintext game/cache sockets; keep PBKDF2 account auth, firewall rules, and bridge loopback-only")
    else:
        if not bool(config.get("require_secure_external_transport", True)):
            fail("require_secure_external_transport must be true for encrypted external transport modes")
        if not bool(config.get("secure_external_transport_confirmed", False)):
            fail("secure_external_transport_confirmed must be true for encrypted external transport modes")

    game_hosts = normalized_hosts(config, "game_bind_hosts", "game_bind_host", "127.0.0.1")
    http_hosts = normalized_hosts(config, "http_bind_hosts", "http_bind_host", game_hosts[0])
    jaggrab_hosts = normalized_hosts(config, "jaggrab_bind_hosts", "jaggrab_bind_host", game_hosts[0])
    public_host = normalized_host(config, "public_game_host", "")
    client_connect_host = normalized_host(config, "client_connect_host", "")
    client_tls_tunnel_server_accept_host = normalized_host(
        config,
        "client_tls_tunnel_server_accept_host",
        public_host,
    )
    wildcard_bind_confirmed = bool(config.get("wildcard_bind_confirmed", False))
    client_tls_tunnel = mode == "client_tls_tunnel"

    reject_mixed_wildcard_hosts("game_bind_hosts", game_hosts)
    if not client_tls_tunnel and all(is_loopback_host(host) for host in game_hosts):
        fail("all game bind hosts are loopback; external clients cannot connect")
    if is_loopback_host(public_host) or public_host in WILDCARD_HOSTS:
        fail("public_game_host must not be localhost, loopback, or wildcard for external clients")
    if client_tls_tunnel and client_connect_host in WILDCARD_HOSTS:
        fail("client_connect_host must not be a wildcard host")
    if client_tls_tunnel and client_connect_host and not is_loopback_host(client_connect_host):
        fail("client_tls_tunnel client_connect_host must be localhost or another loopback address; the Java client connects to a local plaintext tunnel endpoint")
    if client_tls_tunnel and not client_connect_host:
        warn(warnings, "client_tls_tunnel packages default client_connect_host to 127.0.0.1; configure local TLS tunnel launch instructions for players")
    if client_tls_tunnel:
        if client_tls_tunnel_server_accept_host in WILDCARD_HOSTS:
            fail("client_tls_tunnel_server_accept_host must not be wildcard; it would collide with the loopback Java listener on the same ports")
        if is_loopback_host(client_tls_tunnel_server_accept_host):
            fail("client_tls_tunnel_server_accept_host must not be loopback; external TLS clients need a specific public interface host")
    for game_host in game_hosts:
        if game_host in WILDCARD_HOSTS:
            if not wildcard_bind_confirmed:
                fail("wildcard game bind host requires wildcard_bind_confirmed=true in the config")
            if not args.allow_wildcard_bind:
                fail("wildcard game bind host requires --allow-wildcard-bind and a verified firewall boundary")
        if game_host not in LOOPBACK_HOSTS and not is_private_host(game_host):
            if direct_tcp:
                warn(warnings, "game bind host {} is public; direct_tcp should expose only required game/cache ports and never the agent bridge".format(game_host))
            else:
                warn(warnings, "game bind host {} does not look private; expose it only behind the selected encrypted transport".format(game_host))

    file_server_enabled = bool(config.get("file_server", True))
    for key, hosts in (("http_bind_hosts", http_hosts), ("jaggrab_bind_hosts", jaggrab_hosts)):
        if file_server_enabled:
            reject_mixed_wildcard_hosts(key, hosts)
        if not client_tls_tunnel and file_server_enabled and all(is_loopback_host(host) for host in hosts):
            fail("{} are loopback only while file_server=true; external clients need cache services over the selected external transport".format(key))
        for host in hosts:
            if host in WILDCARD_HOSTS:
                if not wildcard_bind_confirmed:
                    fail("{} wildcard bind requires wildcard_bind_confirmed=true in the config".format(key))
                if not args.allow_wildcard_bind:
                    fail("{} wildcard bind requires --allow-wildcard-bind and a verified firewall boundary".format(key))

    game_port = require_port(config, "game_port", 43594)
    http_port = require_port(config, "http_port", 8080)
    jaggrab_port = require_port(config, "jaggrab_port", 43595)
    if file_server_enabled and len({game_port, http_port, jaggrab_port}) != 3:
        fail("game_port, http_port, and jaggrab_port must be distinct when file_server=true")
    bridge_host = normalized_host(config, "agent_bridge_bind_host", "127.0.0.1")
    bridge_port = require_port(config, "agent_bridge_port", 43610)
    if not is_loopback_host(bridge_host):
        fail("agent_bridge_bind_host must be localhost or another loopback address; never expose AgentBridgeServer")
    if bridge_port == game_port and any(is_loopback_host(host) for host in game_hosts):
        fail("agent_bridge_port must not overlap game_port on a loopback game bind host")
    if file_server_enabled and bridge_port == http_port and any(is_loopback_host(host) for host in http_hosts):
        fail("agent_bridge_port must not overlap http_port on a loopback HTTP cache bind host")
    if file_server_enabled and bridge_port == jaggrab_port and any(is_loopback_host(host) for host in jaggrab_hosts):
        fail("agent_bridge_port must not overlap jaggrab_port on a loopback JAGGRAB cache bind host")

    if not bool(config.get("account_auth_enabled", False)):
        fail("account_auth_enabled should be true for external players")
    if bool(config.get("account_auth_auto_create", False)):
        fail("account_auth_auto_create should be false for external players")
    if bool(config.get("account_auth_legacy_fallback", False)):
        fail("account_auth_legacy_fallback should be false for external players")
    try:
        iterations = int(config.get("account_auth_pbkdf2_iterations", MIN_EXTERNAL_PBKDF2_ITERATIONS))
    except (TypeError, ValueError):
        fail("account_auth_pbkdf2_iterations must be an integer")
    if iterations < MIN_EXTERNAL_PBKDF2_ITERATIONS:
        fail("account_auth_pbkdf2_iterations must be at least {}".format(MIN_EXTERNAL_PBKDF2_ITERATIONS))

    if bool(config.get("agent_chat_discord_enabled", False)):
        warn(warnings, "Discord transport needs ignored data/secrets.json agent-discord-bots; do not commit tokens")

    print("ok: external-player config passed preflight: {}".format(args.config))
    for message in warnings:
        print("warning: {}".format(message))
    print("reminder: never expose AgentBridgeServer {}:{}".format(bridge_host or "127.0.0.1", bridge_port))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
