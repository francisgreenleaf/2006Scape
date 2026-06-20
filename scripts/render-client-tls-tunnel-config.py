#!/usr/bin/env python3
"""Render client_tls_tunnel stunnel templates from a 2006Scape server config."""

import argparse
import ipaddress
import json
import os
import stat
from pathlib import Path


PLACEHOLDER_NETWORK_VALUES = {
    "example-tailnet-host",
    "example-vpn-host",
    "example-server",
    "server.example.com",
    "100.64.0.10",
    "REPLACE_WITH_TAILSCALE_IP",
    "REPLACE_WITH_WIREGUARD_IP",
    "REPLACE_WITH_PUBLIC_GAME_HOST",
}
TLS_MIN_VERSION = "TLSv1.2"
WILDCARD_HOSTS = {"*", "0.0.0.0", "::"}
LOOPBACK_HOSTS = {"", "localhost", "127.0.0.1", "::1", "0:0:0:0:0:0:0:1"}


def fail(message):
    raise SystemExit("client TLS tunnel config failed: {}".format(message))


def load_config(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        fail("could not read {}: {}".format(path, exc))
    except json.JSONDecodeError as exc:
        fail("invalid JSON in {}: {}".format(path, exc))


def string_value(data, key, fallback=""):
    value = data.get(key, fallback)
    return "" if value is None else str(value).strip()


def require_single_line(value, label):
    if any(ord(ch) < 32 for ch in str(value or "")):
        fail("{} must be a single-line value without control characters".format(label))
    return value


def bool_value(data, key, fallback):
    value = data.get(key, fallback)
    return bool(value)


def int_value(data, key, fallback):
    try:
        value = int(data.get(key, fallback))
    except (TypeError, ValueError):
        fail("{} must be an integer".format(key))
    if value < 1 or value > 65535:
        fail("{} must be between 1 and 65535".format(key))
    return value


def is_placeholder(value):
    clean = str(value or "").strip()
    upper = clean.upper()
    return (
        clean.lower() in {item.lower() for item in PLACEHOLDER_NETWORK_VALUES}
        or upper.startswith("REPLACE_")
        or "PLACEHOLDER" in upper
    )


def is_loopback_host(value):
    clean = str(value or "").strip().lower()
    if clean in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(clean).is_loopback
    except ValueError:
        return False


def is_forbidden_accept_host(value):
    clean = str(value or "").strip().lower()
    return clean in WILDCARD_HOSTS or is_loopback_host(clean)


def require_client_tls_config(config, allow_placeholders):
    require_single_line(config.get("external_transport_mode", ""), "external_transport_mode")
    mode = string_value(config, "external_transport_mode").lower()
    if mode != "client_tls_tunnel":
        fail("external_transport_mode must be client_tls_tunnel")
    require_single_line(config.get("public_game_host", ""), "public_game_host")
    public_host = string_value(config, "public_game_host")
    if not public_host:
        fail("public_game_host is required")
    if is_forbidden_accept_host(public_host):
        fail("public_game_host must not be localhost, loopback, or wildcard for client_tls_tunnel")
    if is_placeholder(public_host) and not allow_placeholders:
        fail("public_game_host still contains a placeholder network value: {}".format(public_host))
    require_single_line(config.get("client_connect_host", "127.0.0.1"), "client_connect_host")
    client_host = string_value(config, "client_connect_host", "127.0.0.1") or "127.0.0.1"
    if not is_loopback_host(client_host):
        fail(
            "client_connect_host must be localhost or another loopback address; "
            "the Java client connects to a local plaintext tunnel endpoint"
        )
    require_single_line(
        config.get("client_tls_tunnel_server_accept_host", public_host),
        "client_tls_tunnel_server_accept_host",
    )
    server_accept_host = string_value(
        config,
        "client_tls_tunnel_server_accept_host",
        public_host,
    ) or public_host
    if is_placeholder(server_accept_host) and not allow_placeholders:
        fail("client_tls_tunnel_server_accept_host still contains a placeholder network value: {}".format(server_accept_host))
    if is_forbidden_accept_host(server_accept_host):
        fail(
            "client_tls_tunnel_server_accept_host must be a specific public interface host, "
            "not loopback or wildcard; wildcard would collide with the loopback Java listener"
        )
    return public_host, client_host, server_accept_host


def tunnel_ports(config):
    ports = [("game", "2006scape-game", int_value(config, "game_port", 43594))]
    if bool_value(config, "file_server", True):
        ports.append(("http cache", "2006scape-http-cache", int_value(config, "http_port", 8080)))
        ports.append(("jaggrab cache", "2006scape-jaggrab-cache", int_value(config, "jaggrab_port", 43595)))
    return ports


def render_client_stunnel(config, public_host, client_host, cert_host):
    lines = [
        "; agent-scape player-side stunnel config.",
        "; Start this before launching the Java client.",
        "foreground = yes",
        "client = yes",
        "verifyChain = yes",
        "sslVersionMin = {}".format(TLS_MIN_VERSION),
        "checkHost = {}".format(cert_host),
        "; If stunnel cannot find your OS trust store, set CAfile or CApath here.",
        "",
    ]
    for label, service, port in tunnel_ports(config):
        lines.extend([
            "[{}]".format(service),
            "; Local plaintext {} endpoint used by the Java client.".format(label),
            "accept = {}:{}".format(client_host, port),
            "; Remote TLS endpoint on the server/VPS.",
            "connect = {}:{}".format(public_host, port),
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def render_server_stunnel(config, server_accept_host, cert_host):
    cert_base = "/etc/letsencrypt/live/{}".format(cert_host)
    lines = [
        "; 2006Scape server-side stunnel config.",
        "; Terminate TLS publicly and forward plaintext to loopback 2006Scape listeners.",
        "foreground = yes",
        "client = no",
        "sslVersionMin = {}".format(TLS_MIN_VERSION),
        "cert = {}/fullchain.pem".format(cert_base),
        "key = {}/privkey.pem".format(cert_base),
        "",
    ]
    for label, service, port in tunnel_ports(config):
        lines.extend([
            "[{}]".format(service),
            "; Public TLS {} endpoint.".format(label),
            "accept = {}:{}".format(server_accept_host, port),
            "; Local 2006Scape listener. Keep the game/cache services bound to loopback in this mode.",
            "connect = 127.0.0.1:{}".format(port),
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def render_readme(config, public_host, client_host, server_accept_host, cert_host, client_only):
    file_server = bool_value(config, "file_server", True)
    cache_line = "Game, HTTP cache, and JAGGRAB cache tunnels are included." if file_server else "Only the game tunnel is included because file_server=false."
    server_note = (
        "The operator-side template is not included in this player package; generate it with "
        "`scripts/render-client-tls-tunnel-config.py --config SERVER_CONFIG --output-dir OUTPUT_DIR`."
        if client_only
        else "This folder includes both player-side and operator-side stunnel templates."
    )
    return """agent-scape client TLS Tunnel

This package targets external_transport_mode=client_tls_tunnel.
The Java client still speaks plaintext to {client_host}; stunnel carries that traffic
over TLS 1.2 or newer to {public_host}. {cache_line}

Player setup:
1. Install stunnel. See INSTALL-STUNNEL.txt in this folder for OS-specific hints.
2. Normally use the packaged agent-scape launcher; it starts this stunnel config
   automatically when stunnel is installed.
3. If you need to start the tunnel manually, run this from this folder:
     stunnel stunnel-client.conf
4. Leave stunnel running, then launch the agent-scape client.

Expected endpoints:
- local client endpoint: {client_host}
- remote TLS endpoint: {public_host}
- server-side tunnel accept host: {server_accept_host}
- certificate host checked by stunnel: {cert_host}

{server_note}

Deployment proof:
Run scripts/verify-external-deployment.py with --live after the remote server and
server-side tunnel are intentionally running. In client_tls_tunnel mode the verifier
requires TLS handshakes on the public game/cache ports, not plain TCP.
""".format(
        cache_line=cache_line,
        cert_host=cert_host,
        client_host=client_host,
        public_host=public_host,
        server_accept_host=server_accept_host,
        server_note=server_note,
    )


def render_install_help():
    return """Installing stunnel for agent-scape client_tls_tunnel

This package does not bundle stunnel binaries. Install stunnel through a trusted
OS package manager or installer, then use the packaged agent-scape launchers.

macOS with Homebrew:
  brew install stunnel

Debian or Ubuntu:
  sudo apt-get update
  sudo apt-get install stunnel4

Fedora or RHEL-family Linux:
  sudo dnf install stunnel

Windows:
  Install stunnel from a trusted Windows package source or installer, then make
  sure stunnel.exe is on PATH before running run-windows.bat.

After installation:
  - macOS/Linux: run ./check-setup-macos-linux.sh or ./run-macos-linux.sh.
  - Windows: run run-windows.bat. The Windows setup checker expects the local
    tunnel endpoint to be reachable first.
  - Manual fallback from this folder: stunnel stunnel-client.conf
"""


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if os.name == "posix":
        path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o111)


def main():
    parser = argparse.ArgumentParser(description="Render stunnel templates for client_tls_tunnel deployments.")
    parser.add_argument("--config", required=True, type=Path,
            help="Server config with external_transport_mode=client_tls_tunnel.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--client-only", action="store_true",
            help="Write only files useful to a downloadable player client package.")
    parser.add_argument("--tls-cert-host", default="",
            help="Certificate hostname to verify. Defaults to public_game_host.")
    parser.add_argument("--allow-placeholder-network-config", action="store_true",
            help="Allow placeholder host values for source/sample validation only.")
    args = parser.parse_args()

    config = load_config(args.config)
    public_host, client_host, server_accept_host = require_client_tls_config(
        config,
        args.allow_placeholder_network_config,
    )
    cert_host = args.tls_cert_host.strip() or public_host
    require_single_line(cert_host, "--tls-cert-host")
    if is_placeholder(cert_host) and not args.allow_placeholder_network_config:
        fail("--tls-cert-host still contains a placeholder network value: {}".format(cert_host))
    if is_forbidden_accept_host(cert_host):
        fail("--tls-cert-host must be a specific non-loopback, non-wildcard certificate host")

    write_text(
        args.output_dir / "README.txt",
        render_readme(config, public_host, client_host, server_accept_host, cert_host, args.client_only),
    )
    write_text(
        args.output_dir / "stunnel-client.conf",
        render_client_stunnel(config, public_host, client_host, cert_host),
    )
    write_text(args.output_dir / "INSTALL-STUNNEL.txt", render_install_help())
    if not args.client_only:
        write_text(
            args.output_dir / "stunnel-server.conf",
            render_server_stunnel(config, server_accept_host, cert_host),
        )
    print("ok: rendered client TLS tunnel templates in {}".format(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
