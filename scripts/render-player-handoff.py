#!/usr/bin/env python3
"""Render a public-safe player handoff note from prepared deployment artifacts."""

import argparse
import hashlib
import os
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PREPARED_DIR = ROOT_DIR / "dist" / "external-deployment"
USERNAME_RE = re.compile(r"[a-z0-9 .]{1,12}", re.IGNORECASE)
SECRET_WORDS = ("password", "token", "secret", "nonce", "api key", "bot token")


def fail(message):
    raise SystemExit(message)


def reject_symlink(path, label):
    if path.is_symlink():
        fail("{} must not be a symlink: {}".format(label, path))


def require_file(path, label):
    reject_symlink(path, label)
    if not path.is_file():
        fail("{} is missing: {}".format(label, path))
    return path


def optional_file(path, label):
    reject_symlink(path, label)
    if not path.exists():
        return None
    if not path.is_file():
        fail("{} must be a regular file: {}".format(label, path))
    return path


def safe_output_path(path):
    reject_symlink(path, "output path")
    parent = path.parent
    while True:
        if parent.is_symlink():
            fail("refusing to write through symlinked parent directory: {}".format(parent))
        if parent.exists():
            if not parent.is_dir():
                fail("output parent must be a directory: {}".format(parent))
            return
        if parent == parent.parent:
            fail("output parent does not exist: {}".format(path.parent))
        parent = parent.parent


def normalize_player_name(value, label):
    clean = (value or "").strip()
    if not USERNAME_RE.fullmatch(clean):
        fail("{} must be 1-12 characters: letters, numbers, spaces, or dots".format(label))
    return clean


def parse_key_value_file(path):
    values = {}
    if not path:
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def transport_steps(transport):
    mode = (transport or "").strip().lower()
    if mode == "tailscale":
        return [
            "1. Install Tailscale and sign in with the account invited by the operator.",
            "2. Confirm Tailscale is connected before running the setup checker.",
            "3. If setup cannot reach the server, check Tailscale status before retrying login.",
        ]
    if mode in ("wireguard", "vpn"):
        return [
            "1. Install or import the private network profile supplied by the operator.",
            "2. Connect that private network before running the setup checker.",
            "3. If setup cannot reach the server, confirm the VPN is connected first.",
        ]
    if mode == "client_tls_tunnel":
        return [
            "1. Install stunnel if the launcher cannot find it automatically.",
            "2. Keep the bundled `client-tls-tunnel/` folder beside the launcher.",
            "3. Run the setup checker; on macOS/Linux it can start the bundled tunnel for diagnostics.",
        ]
    if mode == "direct_tcp":
        return [
            "1. No VPN or client-side tunnel is expected for this package.",
            "2. This mode uses plaintext game/cache TCP to the public host.",
            "3. Use only a password unique to this 2006Scape server.",
        ]
    return [
        "1. Connect the transport specified by the operator before launching.",
        "2. Run the setup checker before logging in.",
    ]


def agent_gateway_note(agent_gateway):
    value = (agent_gateway or "").strip()
    if value.startswith("https://"):
        return "`/agent ...` uses the configured HTTPS gateway: `{}`.".format(value)
    return (
        "`/agent ...` is not available for remote play unless the operator supplies "
        "an HTTPS `/agent` gateway. Never expose raw TCP `43610`."
    )


def render_note(args):
    prepared_dir = Path(args.prepared_dir)
    client_dist = Path(args.client_dist) if args.client_dist else prepared_dir / "2006scape-client"
    client_archive = Path(args.client_archive) if args.client_archive else prepared_dir / "2006scape-client.zip"
    server_deployment = Path(args.server_deployment_dir) if args.server_deployment_dir else prepared_dir / "server-deployment"

    manifest = require_file(client_dist / "MANIFEST.txt", "client MANIFEST.txt")
    checksums = require_file(client_dist / "SHA256SUMS", "client SHA256SUMS")
    client_readme = require_file(client_dist / "README.txt", "client README.txt")
    client_props = require_file(client_dist / "client.properties", "client.properties")
    handoff_template = require_file(server_deployment / "player-handoff-template.md", "player handoff template")
    archive_path = optional_file(client_archive, "client archive")

    username = normalize_player_name(args.username, "username")
    character = normalize_player_name(args.character or args.username, "character")

    manifest_values = parse_key_value_file(manifest)
    prop_values = parse_key_value_file(client_props)
    transport = manifest_values.get("expected_external_transport") or prop_values.get("secure.transport") or "unspecified"
    public_host = manifest_values.get("public_game_host") or prop_values.get("server.host") or "operator-provided host"
    game_port = manifest_values.get("game_port") or prop_values.get("server.port") or "43594"
    http_port = manifest_values.get("http_port") or prop_values.get("http.port") or "8080"
    jaggrab_port = manifest_values.get("jaggrab_port") or prop_values.get("jaggrab.port") or "43595"
    agent_gateway = args.agent_gateway_url or manifest_values.get("agent_bridge_url") or prop_values.get("agent.bridge.url") or ""

    archive_label = archive_path.name if archive_path else "2006scape-client.zip"
    archive_sha = sha256_file(archive_path) if archive_path else ""

    lines = [
        "# 2006Scape Player Handoff",
        "",
        "This note is safe to send to the player. Send the account password separately through a private channel.",
        "Do not paste passwords, account JSON files, bridge tokens, claim nonces, API keys, or Discord bot tokens into this note.",
        "",
        "## Download",
        "",
        "- client archive: `{}`".format(archive_label),
    ]
    if archive_sha:
        lines.append("- client archive SHA-256: `{}`".format(archive_sha))
    lines.extend([
        "- manifest: `2006scape-client/MANIFEST.txt`",
        "- checksums: `2006scape-client/SHA256SUMS`",
        "",
        "After unzipping, the player can verify package files by opening `SHA256SUMS` or running checksum verification from the extracted client folder.",
        "",
        "## Account",
        "",
        "- username: `{}`".format(username),
        "- character: `{}`".format(character),
        "- password: sent separately through a private channel",
        "",
        "Use a password unique to this 2006Scape server. Do not reuse a RuneScape.com password or any password from another service.",
        "",
        "## Connection",
        "",
        "- public game host: `{}`".format(public_host),
        "- external transport: `{}`".format(transport),
        "- game port: `{}`".format(game_port),
        "- HTTP cache port: `{}`".format(http_port),
        "- JAGGRAB/cache port: `{}`".format(jaggrab_port),
        "- agent bridge URL in package: `{}`".format(agent_gateway or "not configured"),
        "",
        "## Before Logging In",
        "",
    ])
    lines.extend(transport_steps(transport))
    lines.extend([
        "",
        "## Start The Client",
        "",
        "1. Run the setup checker before logging in:",
        "   - macOS: double-click `Check-Setup.command`.",
        "   - Linux: run `./check-setup-macos-linux.sh`.",
        "   - Windows: double-click `check-setup-windows.bat`.",
        "2. If setup passes, start the game:",
        "   - macOS: double-click `Run-2006Scape.command`.",
        "   - Linux: run `./run-macos-linux.sh`.",
        "   - Windows: double-click `run-windows.bat`.",
        "3. Log in with the username above and the privately supplied password.",
        "",
        "## Agent Mode",
        "",
        agent_gateway_note(agent_gateway),
        "",
        "## Do Not Send",
        "",
        "- `2006Scape Server/data/accounts/*.json` account records.",
        "- `2006Scape Server/data/secrets.json`.",
        "- Runtime backup archives containing character saves, account records, or secrets.",
        "- Bridge session files, bridge tokens, `/agent` claim nonces, API keys, or Discord bot tokens.",
        "",
        "<!-- Source artifacts used: {}, {}, {}, {}, {} -->".format(
            manifest.name,
            checksums.name,
            client_readme.name,
            client_props.name,
            handoff_template.name,
        ),
        "",
    ])
    text = "\n".join(lines)
    lowered = text.lower()
    for word in SECRET_WORDS:
        if word == "password":
            continue
        if "{}=".format(word) in lowered:
            fail("rendered handoff appears to contain a secret-like assignment: {}".format(word))
    return text


def main():
    parser = argparse.ArgumentParser(
        description="Render a public-safe per-player handoff note from prepared 2006Scape deployment artifacts."
    )
    parser.add_argument("--prepared-dir", default=str(DEFAULT_PREPARED_DIR),
            help="Directory created by prepare-external-deployment.py. Defaults to dist/external-deployment.")
    parser.add_argument("--client-dist", default="",
            help="Packaged client directory. Defaults to PREPARED_DIR/2006scape-client.")
    parser.add_argument("--client-archive", default="",
            help="Client zip path. Defaults to PREPARED_DIR/2006scape-client.zip.")
    parser.add_argument("--server-deployment-dir", default="",
            help="Rendered server-deployment directory. Defaults to PREPARED_DIR/server-deployment.")
    parser.add_argument("--username", required=True,
            help="Player account username to show in the handoff note. The password is never accepted.")
    parser.add_argument("--character", default="",
            help="Allowed/logged-in character name. Defaults to --username.")
    parser.add_argument("--agent-gateway-url", default="",
            help="Optional HTTPS /agent gateway URL to show instead of the packaged agent.bridge.url.")
    parser.add_argument("--output", default="",
            help="Write the note to this path instead of stdout.")
    args = parser.parse_args()

    text = render_note(args)
    if args.output:
        output = Path(args.output)
        safe_output_path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        if os.name == "posix":
            output.chmod(0o600)
        print("ok: wrote player handoff note {}".format(output))
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
