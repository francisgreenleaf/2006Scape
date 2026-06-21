#!/usr/bin/env python3
"""Render operator-side server deployment templates for 2006Scape."""

import argparse
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INSTALL_ROOT = "/opt/2006scape"
DEFAULT_CONFIG_PATH = "/etc/2006scape/ServerConfig.json"
DEFAULT_ENV_PATH = "/etc/2006scape/server.env"
DEFAULT_RUN_DIR = "/var/lib/2006scape/run"
INTERFACE_NAME_RE = re.compile(r"^[A-Za-z0-9_.:@+-]{1,64}$")
SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")
DEPLOYMENT_PATH_RE = re.compile(r"^/[A-Za-z0-9._@:+,=/-]+$")


def load_config(path):
    try:
        with Path(path).open("r", encoding="utf-8") as source:
            data = json.load(source)
    except OSError as exc:
        raise SystemExit("could not read config {}: {}".format(path, exc))
    except json.JSONDecodeError as exc:
        raise SystemExit("invalid JSON in config {}: {}".format(path, exc))
    if not isinstance(data, dict):
        raise SystemExit("config must be a JSON object: {}".format(path))
    return data


def port(config, key, fallback):
    try:
        value = int(config.get(key, fallback))
    except (TypeError, ValueError):
        raise SystemExit("{} must be an integer port".format(key))
    if value < 1 or value > 65535:
        raise SystemExit("{} must be between 1 and 65535".format(key))
    return value


def bool_value(config, key, fallback=False):
    value = config.get(key, fallback)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def mode(config):
    return str(config.get("external_transport_mode", "") or "").strip().lower()


def shq(value):
    return shlex.quote(str(value))


def shell_command(*parts):
    return " ".join(shq(part) for part in parts)


def simple_service_name(value, label):
    clean = str(value or "").strip()
    if not SERVICE_NAME_RE.fullmatch(clean):
        raise SystemExit("{} must be a simple service user/group name, got {!r}".format(label, value))
    if clean == "root":
        raise SystemExit("{} must not be root".format(label))
    return clean


def deployment_path(value, label, allow_root=False):
    clean = str(value or "").strip()
    if clean != str(value or ""):
        raise SystemExit("{} must not contain leading or trailing whitespace, got {!r}".format(label, value))
    if not DEPLOYMENT_PATH_RE.fullmatch(clean):
        raise SystemExit(
            "{} must be an absolute path with simple characters and no whitespace/control chars, got {!r}".format(
                label,
                value,
            )
        )
    if clean == "/" and not allow_root:
        raise SystemExit("{} must not be the filesystem root".format(label))
    return clean


def single_line_value(value, label, allow_empty=False):
    clean = str(value or "")
    if not clean and not allow_empty:
        raise SystemExit("{} must not be empty".format(label))
    if any(ord(ch) < 32 for ch in clean):
        raise SystemExit("{} must be a single-line value without control characters".format(label))
    return clean


def interface_name(value, label):
    clean = str(value or "").strip()
    if not INTERFACE_NAME_RE.fullmatch(clean):
        raise SystemExit("{} must be a simple interface name, got {!r}".format(label, value))
    return clean


def service_text(args):
    install_root = args.install_root.rstrip("/")
    return """[Unit]
Description=2006Scape Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={service_user}
Group={service_group}
WorkingDirectory={install_root}
EnvironmentFile={env_path}
ExecStart={install_root}/scripts/start-server.sh
Restart=on-failure
RestartSec=5
UMask=0077
LimitNOFILE=4096
AmbientCapabilities=
CapabilityBoundingSet=
NoNewPrivileges=true
PrivateDevices=true
PrivateTmp=true
ProtectClock=true
ProtectControlGroups=true
ProtectHome=true
ProtectHostname=true
ProtectKernelModules=true
ProtectKernelTunables=true
ProtectSystem=full
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
RestrictSUIDSGID=true
SystemCallArchitectures=native

[Install]
WantedBy=multi-user.target
""".format(
        env_path=args.env_path,
        install_root=install_root,
        service_group=args.service_group,
        service_user=args.service_user,
    )


def env_text(args):
    return """# 2006Scape server environment.
# Install this as {env_path} with owner root:root and mode 0644.
JAVA_BIN={java_bin}
SERVER_CONFIG={config_path}
SERVER_RUN_DIR={run_dir}
SERVER_JAVA_OPTS={java_opts}
""".format(
        config_path=args.config_path,
        env_path=args.env_path,
        java_bin=args.java_bin,
        java_opts=args.java_opts,
        run_dir=args.run_dir,
    )


def firewall_ports(config):
    values = [("game", port(config, "game_port", 43594))]
    if bool_value(config, "file_server", True):
        values.append(("http-cache", port(config, "http_port", 8080)))
        values.append(("jaggrab-cache", port(config, "jaggrab_port", 43595)))
    return values


def validate_args(config, args):
    args.install_root = deployment_path(args.install_root, "--install-root").rstrip("/")
    args.config_path = deployment_path(args.config_path, "--config-path")
    args.env_path = deployment_path(args.env_path, "--env-path")
    args.run_dir = deployment_path(args.run_dir, "--run-dir")
    args.java_bin = deployment_path(args.java_bin, "--java-bin")
    args.service_user = simple_service_name(args.service_user, "--service-user")
    args.service_group = simple_service_name(args.service_group, "--service-group")
    args.java_opts = single_line_value(args.java_opts, "--java-opts", allow_empty=True)

    transport = mode(config)
    if transport == "tailscale":
        args.tailscale_interface = interface_name(args.tailscale_interface, "--tailscale-interface")
    elif transport in {"wireguard", "vpn"}:
        args.vpn_interface = interface_name(args.vpn_interface, "--vpn-interface")


def preflight_config(config_path, args):
    argv = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "preflight-external-config.py"),
        str(config_path),
    ]
    if args.allow_wildcard_bind:
        argv.append("--allow-wildcard-bind")
    completed = subprocess.run(
        argv,
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        output = (completed.stdout or "").strip()
        raise SystemExit("server deployment config preflight failed:\n{}".format(output))


def firewall_text(config, args):
    transport = mode(config)
    ports = firewall_ports(config)
    if transport == "tailscale":
        interface = interface_name(args.tailscale_interface, "--tailscale-interface")
        allow_lines = [
            shell_command(
                "sudo", "ufw", "allow", "in", "on", interface, "to", "any", "port",
                str(port_value), "proto", "tcp", "comment", "2006Scape {} over Tailscale".format(label),
            )
            for label, port_value in ports
        ]
        note = "Tailscale mode: expose game/cache only on the Tailscale interface."
    elif transport in {"wireguard", "vpn"}:
        interface = interface_name(args.vpn_interface, "--vpn-interface")
        allow_lines = [
            shell_command(
                "sudo", "ufw", "allow", "in", "on", interface, "to", "any", "port",
                str(port_value), "proto", "tcp", "comment", "2006Scape {} over VPN".format(label),
            )
            for label, port_value in ports
        ]
        note = "VPN mode: replace the interface if your WireGuard/VPN interface is not {}.".format(interface)
    elif transport == "client_tls_tunnel":
        allow_lines = [
            shell_command(
                "sudo", "ufw", "allow", "{}/tcp".format(port_value), "comment",
                "2006Scape TLS tunnel {}".format(label),
            )
            for label, port_value in ports
        ]
        note = "client_tls_tunnel mode: these public ports are for the TLS tunnel endpoint, not direct plaintext game listeners."
    elif transport == "direct_tcp":
        allow_lines = [
            shell_command(
                "sudo", "ufw", "allow", "{}/tcp".format(port_value), "comment",
                "2006Scape direct TCP {}".format(label),
            )
            for label, port_value in ports
        ]
        note = "direct_tcp mode: exposes plaintext game/cache listeners directly; keep account auth enabled and never expose the agent bridge."
    else:
        allow_lines = [
            '# unsupported or unspecified external_transport_mode={!r}; review firewall manually'.format(transport)
        ]
        note = "Transport mode is not recognized by this template."
    bridge_port = port(config, "agent_bridge_port", 43610)
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Generated UFW example for 2006Scape.",
        "# {}".format(note),
        "# Default is dry-run. Set APPLY=1 to execute the commands.",
        "",
        "run() {",
        "    if [[ \"${APPLY:-0}\" == \"1\" ]]; then",
        "        \"$@\"",
        "    else",
        "        printf 'DRY-RUN: %q ' \"$@\"",
        "        printf '\\n'",
        "    fi",
        "}",
        "",
        "run sudo ufw default deny incoming",
        "run sudo ufw default allow outgoing",
    ]
    for command in allow_lines:
        lines.append("run {}".format(command))
    lines.extend([
        "run {}".format(shell_command(
            "sudo", "ufw", "deny", "{}/tcp".format(bridge_port), "comment",
            "Do not expose 2006Scape AgentBridgeServer",
        )),
        "run sudo ufw status verbose",
        "",
    ])
    return "\n".join(lines)


def tailscale_policy_grants_text(config):
    ports = ["tcp:{}".format(port_value) for _, port_value in firewall_ports(config)]
    return json.dumps(
        {
            "groups": {
                "group:2006scape-players": [
                    "player@example.com",
                ],
            },
            "tagOwners": {
                "tag:2006scape-server": [
                    "autogroup:admin",
                ],
            },
            "grants": [
                {
                    "src": [
                        "group:2006scape-players",
                    ],
                    "dst": [
                        "tag:2006scape-server",
                    ],
                    "ip": ports,
                },
            ],
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def readme_text(config, args):
    transport = mode(config) or "unspecified"
    public_host = str(config.get("public_game_host", "") or "").strip() or "(not configured)"
    install_root = args.install_root.rstrip("/")
    config_dir = str(Path(args.config_path).parent)
    server_data_dir = "{}/2006Scape Server/data".format(install_root)
    accounts_dir = "{}/accounts".format(server_data_dir)
    characters_dir = "{}/characters".format(server_data_dir)
    secrets_path = "{}/secrets.json".format(server_data_dir)
    lines = [
        "# 2006Scape Server Deployment Files",
        "",
        "These files are operator templates generated from the selected server config.",
        "They do not start or stop a server by themselves.",
        "",
        "## Files",
        "",
        "- `ServerConfig.json`: copy of the config used for this deployment bundle.",
        "- `2006scape-server.env`: systemd environment file.",
        "- `2006scape-server.service`: systemd unit that runs `scripts/start-server.sh` from the deployed repo.",
        "- `firewall-ufw-example.sh`: dry-run UFW commands for the selected transport.",
        "- `tailscale-policy-grants.example.json`: Tailscale grants example for this deployment's game/cache ports; present only for Tailscale transport.",
        "- `player-handoff-template.md`: public-safe template for telling one player how to download, verify, connect, and log in without exposing secrets.",
        "- `proof-templates/deployment-proof-manifest.json`: fill-in manifest for live/manual readiness proof flags.",
        "- `proof-templates/desktop-client-proof.md`: fill-in note for same-host plus external Java client coexistence evidence.",
        "- `proof-templates/runtime-data-backup-proof.md`: fill-in note for runtime data backup evidence.",
        "",
        "This bundle does not include real `data/secrets.json`, Discord tokens, or account records.",
        "Create or copy those separately with owner-only permissions before live deployment.",
        "",
        "## Deployment Assumptions",
        "",
        "- install root: `{}`".format(args.install_root),
        "- service user/group: `{}:{}`".format(args.service_user, args.service_group),
        "- runtime config path: `{}`".format(args.config_path),
        "- run jar copy directory: `{}`".format(args.run_dir),
        "- public host: `{}`".format(public_host),
        "- external transport: `{}`".format(transport),
        "",
        "## Example Install",
        "",
        "```sh",
        shell_command(
            "sudo", "useradd", "--system", "--home-dir", args.install_root,
            "--shell", "/usr/sbin/nologin", args.service_user,
        ) + " || true",
        shell_command("sudo", "mkdir", "-p", args.install_root, config_dir, args.run_dir),
        shell_command("sudo", "chown", "-R", "{}:{}".format(args.service_user, args.service_group),
                      args.install_root, args.run_dir),
        "# Copy or git-sync this repo to {install_root}, then build/package it there.".format(
            install_root=args.install_root,
        ),
        shell_command("sudo", "install", "-o", "root", "-g", "root", "-m", "0644",
                      "ServerConfig.json", args.config_path),
        shell_command("sudo", "install", "-o", "root", "-g", "root", "-m", "0644",
                      "2006scape-server.env", args.env_path),
        shell_command("sudo", "install", "-o", "root", "-g", "root", "-m", "0644",
                      "2006scape-server.service", "/etc/systemd/system/2006scape-server.service"),
        shell_command("sudo", "systemctl", "daemon-reload"),
        shell_command("sudo", "systemctl", "enable", "--now", "2006scape-server"),
        shell_command("sudo", "systemctl", "status", "2006scape-server"),
        "```",
        "",
        "## Account And Secret Files",
        "",
        "The server reads PBKDF2 account records and Discord secrets from the deployed repo working tree, not from `/etc/2006scape`.",
        "Before a real external deployment, install them under `{}` with owner-only permissions:".format(server_data_dir),
        "",
        "```sh",
        shell_command("sudo", "install", "-d", "-o", args.service_user, "-g", args.service_group,
                      "-m", "0700", accounts_dir),
        "# Create records on the host, or copy pre-created ignored JSON account files here.",
        shell_command(
            "sudo", "-u", args.service_user, "env", "ACCOUNT_PASSWORD=replace-with-12plus",
            "{}/scripts/create-account.py".format(install_root), "username",
            "--password-env", "ACCOUNT_PASSWORD",
        ),
        shell_command(
            "sudo", "-u", args.service_user, "{}/scripts/account-admin.py".format(install_root),
            "--accounts-dir", accounts_dir, "--require-password-policy", "audit",
        ),
        "",
        shell_command("sudo", "install", "-o", args.service_user, "-g", args.service_group,
                      "-m", "0600", "/secure/local/secrets.json", secrets_path),
        shell_command("sudo", "test", "!", "-L", secrets_path),
        shell_command("sudo", "test", "!", "-L", accounts_dir),
        "```",
        "",
        "Do not symlink `data/secrets.json` or `data/accounts`; the runtime and verifier reject symlinked secret/account paths.",
        "`scripts/create-account.py` rejects passwords shorter than 12 characters by default; `--allow-weak-password` is only for local throwaway/source-validation account records.",
        "`scripts/account-admin.py --require-password-policy audit` and deployment verification reject missing or weak-override password policy metadata.",
        "For password rotation, prefer `scripts/create-account.py --overwrite --preserve-metadata` so roles, allowed characters, Discord user id, and disabled state are not dropped.",
        "",
        "## Runtime Data Safety",
        "",
        "Persistent world state lives under the deployed repo's `2006Scape Server/data/` tree.",
        "Do not overwrite `data/characters`, `data/accounts`, or `data/secrets.json` during repo sync, deployment replacement, account rotation, or config changes.",
        "Back up those paths before an intentional remote restart or migration:",
        "",
        "```sh",
        shell_command("sudo", "install", "-d", "-o", "root", "-g", "root", "-m", "0700",
                      "/var/backups/2006scape"),
        shell_command("sudo", "chown", "{}:{}".format(args.service_user, args.service_group),
                      "/var/backups/2006scape"),
        shell_command("sudo", "-u", args.service_user, "{}/scripts/backup-runtime-data.py".format(install_root),
                      "--data-dir", server_data_dir, "--output-dir", "/var/backups/2006scape"),
        shell_command("sudo", "-u", args.service_user, "test", "-d", characters_dir),
        shell_command("sudo", "test", "!", "-L", characters_dir),
        "```",
        "",
        "The helper writes owner-only archive/proof files on POSIX systems and records that it did not start, stop, or restart the runtime. Pass the generated `runtime-data-backup-proof-*.md` file to `scripts/deployment-readiness-report.py --runtime-data-backup-proof-file`, or add `--proof-manifest deployment-proof-manifest.json` when a copied final proof manifest already exists.",
        "Readiness validation rejects symlinked proof notes, verifies owner-only proof/archive modes where supported, and checks the proof's archive path, `backup archive sha256`, and required runtime-data entries, so keep the archive beside the proof or provide an absolute archive path.",
        "",
        "Treat local development character saves as separate data. Copy them to the remote host only when that is intentional.",
        "",
        "## Proof Note Templates",
        "",
        "The files under `proof-templates/` are not evidence until every placeholder is replaced with real deployment details.",
        "`deployment-proof-manifest.json` lets operators keep the final readiness proof flags in one file. Copy `proof-templates/deployment-proof-manifest.json` to `deployment-proof-manifest.json`, edit the copy, and pass the copy with `scripts/deployment-readiness-report.py --proof-manifest deployment-proof-manifest.json`.",
        "Keep only password environment-variable names in the manifest, never password values or Discord tokens.",
        "For final readiness, copy the template before editing it, then run the proof-manifest checker before the heavier readiness/prep command:",
        "",
        "```sh",
        "cp proof-templates/deployment-proof-manifest.json deployment-proof-manifest.json",
        "$EDITOR deployment-proof-manifest.json",
        shell_command("scripts/check-deployment-proof-manifest.py", "deployment-proof-manifest.json",
                      "--config", "ServerConfig.json", "--secrets", secrets_path,
                      "--require-full-proof", "--check-files", "--check-env"),
        "```",
        "",
        "With `--check-files`, the checker validates encrypted/private transport, desktop proof evidence, and runtime-backup archive/checksum details, not just path existence.",
        "Final-gate manifests must keep `require_full_proof:true` and `require_encrypted_external:true` in the copied manifest itself so handoff evidence stays self-describing.",
        "Relative proof-note paths in the manifest are resolved from the manifest file's directory, so keep completed proof notes beside `deployment-proof-manifest.json` or use absolute paths.",
        "Keep `live_reject_login_expected_statuses` in the final manifest, normally `3,4`, so fail-closed login proof pins the accepted rejection status codes instead of treating any rejection-looking response as enough.",
        "After filling them in, pass the completed copies to `scripts/deployment-readiness-report.py` with `--desktop-client-proof-file` and `--runtime-data-backup-proof-file`, or let `scripts/backup-runtime-data.py --proof-manifest deployment-proof-manifest.json` fill the runtime-backup proof field after the backup runs.",
        "Desktop client proof must include an `evidence` path to a real non-symlink screenshot/log file; readiness validation checks that file exists and is not empty.",
        "After observing one same-host Java client and one external Java client online together, prefer `scripts/write-desktop-client-proof.py --same-host-client LOCAL --external-client EXTERNAL --transport TRANSPORT --public-host HOST --evidence PATH` to write the desktop proof note. It validates the existing evidence file and does not start, stop, restart, log in, or probe runtime.",
        "After the final readiness report is written, `scripts/package-deployment-proof.py` can package non-secret handoff evidence from the readiness Markdown/JSON, filled proof manifest, proof notes, and selected client/server metadata while excluding runtime backup archives, character saves, account records, secrets, passwords, bridge tokens, and Discord bot tokens. Its `--require-full-proof` gate also requires the encrypted/private transport proof to pass.",
        "",
        "## Live Chat Proof",
        "",
        "Full readiness needs direct agent/player chat delivery proof even when Discord is disabled.",
        "After the service is intentionally running, send a unique marker to an online player with an agent `agent_chat_send`/`agent_chat_send_XS` call using a `player` target, or from a game client with `::agentchat @player:PLAYER MARKER`.",
        "Verify the delivery-status audit event with `scripts/verify-agent-chat-log.py --event agent_chat_player_delivery --text-contains MARKER --to-type player --to-name PLAYER --delivered-to PLAYER --no-undelivered --channel agent`.",
        "Pass the same marker to readiness with `--agent-chat-delivery-log-text MARKER --agent-chat-delivery-log-to-name PLAYER --agent-chat-delivery-log-channel agent`.",
        "If Discord is enabled, collect Discord-to-server and server-to-Discord proof separately.",
        "",
        "Run `./firewall-ufw-example.sh` first to inspect the generated commands.",
        "Use `APPLY=1 ./firewall-ufw-example.sh` only after the selected transport path and host firewall policy are ready.",
        "",
        "After the service is intentionally running, run the deployment verifier with `--live` from a machine that has the selected transport path.",
    ]
    if transport == "tailscale":
        ports_text = ", ".join("tcp:{}".format(port_value) for _, port_value in firewall_ports(config))
        lines.extend([
            "",
            "## Tailscale Access Policy",
            "",
            "`tailscale-policy-grants.example.json` is a copy/paste starting point for the tailnet policy file.",
            "It grants `group:2006scape-players` access to `tag:2006scape-server` only on this deployment's game/cache ports: {}.".format(ports_text),
            "Replace the placeholder player email, group name, or server tag to match your tailnet before applying it.",
            "Do not add TCP `{}` to that grant; the agent bridge must stay loopback-only and reachable only through the approved HTTPS gateway when remote agent mode is used.".format(port(config, "agent_bridge_port", 43610)),
        ])
    return "\n".join(lines) + "\n"


def player_handoff_template_text(config, args):
    transport = mode(config) or "REPLACE_TRANSPORT"
    public_host = str(config.get("public_game_host", "") or "").strip() or "REPLACE_PUBLIC_HOST"
    game_port = port(config, "game_port", 43594)
    http_port = port(config, "http_port", 8080)
    jaggrab_port = port(config, "jaggrab_port", 43595)
    agent_gateway = str(config.get("agent_bridge_public_url", "") or "").strip() or "REPLACE_AGENT_GATEWAY_OR_NA"
    if transport == "tailscale":
        transport_steps = [
            "1. Install Tailscale from https://tailscale.com/download.",
            "2. Sign in with the account or invite supplied by the operator.",
            "3. Confirm Tailscale is connected before running the setup checker.",
        ]
        security_note = "This package expects the game/cache sockets to be reachable only through Tailscale."
    elif transport in {"wireguard", "vpn"}:
        transport_steps = [
            "1. Install/connect the private network profile supplied by the operator.",
            "2. Confirm the VPN is connected before running the setup checker.",
        ]
        security_note = "This package expects the game/cache sockets to be reachable only through the private network."
    elif transport == "client_tls_tunnel":
        transport_steps = [
            "1. Install stunnel if the launcher cannot start the bundled tunnel automatically.",
            "2. Run the packaged setup checker; on macOS/Linux it can start the bundled stunnel config temporarily for TCP checks.",
            "3. If the checker says the local tunnel endpoint is unreachable, start `client-tls-tunnel/stunnel-client.conf` manually first.",
        ]
        security_note = "This package keeps the Java client on loopback and sends game/cache traffic through a TLS tunnel."
    elif transport == "direct_tcp":
        transport_steps = [
            "1. No VPN or client-side tunnel is required.",
            "2. Run the setup checker before logging in so plain TCP reachability is confirmed without changing server state.",
        ]
        security_note = "This package connects directly over plaintext TCP; use only server-unique passwords."
    else:
        transport_steps = [
            "1. Confirm the transport requirement with the operator before launching the client.",
            "2. Run the setup checker before logging in.",
        ]
        security_note = "Confirm the intended encrypted/private transport before distributing this package."

    lines = [
        "# Player Handoff Template",
        "",
        "Use this as the operator checklist for one player. Replace placeholders, then send only the player-facing section plus that player's credentials through a private channel.",
        "",
        "## Operator Checklist",
        "",
        "- Build the client from the final config: `scripts/prepare-external-deployment.py --config \"2006Scape Server/ServerConfig.json\" --require-encrypted-external` for encrypted/private player packages.",
        "- Share `agent-scape-client.zip`, plus `MANIFEST.txt` and `SHA256SUMS` if the player wants to verify the download.",
        "- Create a PBKDF2 account record with `scripts/create-account.py PLAYER_USERNAME --password-env PLAYER_PASSWORD`.",
        "- Use a 12+ character password by default; short or reused passwords are only acceptable for local throwaway smoke tests.",
        "- If this account should only load one character, preserve that boundary with account metadata such as `--allowed-character CHARACTER_NAME`.",
        "- Run `scripts/account-admin.py --require-password-policy audit` before sending credentials.",
        "- Send username and password privately. Do not put passwords, account JSON files, bridge tokens, Discord tokens, or claim nonces in Git, Discord channels, screenshots, or proof bundles.",
        "- Never expose raw TCP `43610`; remote `/agent` use needs the approved HTTPS `/agent` gateway only.",
        "",
        "## Package Details To Confirm",
        "",
        "- public game host: `{}`".format(public_host),
        "- external transport: `{}`".format(transport),
        "- game port: `{}`".format(game_port),
        "- HTTP cache port: `{}`".format(http_port),
        "- JAGGRAB/cache port: `{}`".format(jaggrab_port),
        "- agent gateway for `/agent`: `{}`".format(agent_gateway),
        "- security note: {}".format(security_note),
        "",
        "## Player-Facing Message",
        "",
        "Download and unzip `agent-scape-client.zip`.",
        "",
        "Before logging in:",
    ]
    lines.extend(transport_steps)
    lines.extend([
        "",
        "Then run the setup checker:",
        "",
        "- macOS: double-click `Check-Setup.command`.",
        "- Linux: run `./check-setup-macos-linux.sh`.",
        "- Windows: double-click `check-setup-windows.bat`.",
        "",
        "If the setup checker passes, start the game:",
        "",
        "- macOS: double-click `run-agent-scape.command`.",
        "- Linux: run `./run-macos-linux.sh`.",
        "- Windows: double-click `run-windows.bat`.",
        "",
        "Login details:",
        "",
        "- username: `PLAYER_USERNAME`",
        "- password: sent privately",
        "- character: `CHARACTER_NAME_OR_ANY_ALLOWED_CHARACTER`",
        "",
        "Use a password unique to this agent-scape server. Do not reuse a RuneScape.com password or any password from another service.",
        "",
        "If `/agent ...` is enabled for this package, it uses the `agent.bridge.url` value in `client.properties`. If that value is not an HTTPS `/agent` gateway supplied by the operator, `/agent` is not available for remote play.",
        "",
        "## Do Not Send To Players",
        "",
        "- Server account-record JSON files.",
        "- Server secrets files.",
        "- Runtime backup archives containing character saves, account records, or secrets.",
        "- Bridge session files, bridge tokens, `/agent` claim nonces, API keys, or Discord bot tokens.",
        "",
    ])
    return "\n".join(lines)


def desktop_client_proof_template_text(config, args):
    public_host = str(config.get("public_game_host", "") or "").strip() or "REPLACE_PUBLIC_HOST"
    transport = mode(config) or "REPLACE_TRANSPORT"
    return """# Desktop Client Coexistence Proof

- date: YYYY-MM-DD
- server config: {config_path}
- public host: {public_host}
- external transport path: {transport}
- same-host/local Java client: LOCAL_USERNAME connected through 127.0.0.1 or localhost
- external Java client: EXTERNAL_USERNAME connected through {transport} to {public_host}
- observed: both desktop clients remained online at the same time
- evidence: SCREENSHOT_PATH_OR_LOG_PATH

Prefer `scripts/write-desktop-client-proof.py` after the real observation; use this template only when the helper cannot be used.
Replace every placeholder before passing this file to `scripts/deployment-readiness-report.py --desktop-client-proof-file`.
""".format(
        config_path=args.config_path,
        public_host=public_host,
        transport=transport,
    )


def runtime_data_backup_proof_template_text(args):
    install_root = args.install_root.rstrip("/")
    server_data_dir = "{}/2006Scape Server/data".format(install_root)
    return """# Runtime Data Backup Proof

- date: YYYY-MM-DD
- characters: backed up {server_data_dir}/characters
- accounts: backed up {server_data_dir}/accounts
- Discord secrets: backed up {server_data_dir}/secrets.json
- archive: BACKUP_ARCHIVE
- backup archive sha256: BACKUP_ARCHIVE_SHA256
- runtime: not started, stopped, or restarted
- readiness argument: --runtime-data-backup-proof-file PROOF_FILE
- command: sudo -u {service_user} {install_root}/scripts/backup-runtime-data.py --data-dir {server_data_dir_q} --archive BACKUP_ARCHIVE --proof-file PROOF_FILE --proof-manifest deployment-proof-manifest.json

Replace every placeholder before passing this file to `scripts/deployment-readiness-report.py --runtime-data-backup-proof-file`.
""".format(
        install_root=install_root,
        server_data_dir=server_data_dir,
        server_data_dir_q=shq(server_data_dir),
        service_user=args.service_user,
    )


def deployment_proof_manifest_template_text(config):
    transport = mode(config) or "direct_tcp"
    return json.dumps(
        {
            "live": True,
            "live_login_username": "EXTERNAL_TEST_USERNAME",
            "live_login_password_env": "EXTERNAL_TEST_PASSWORD",
            "live_local_login_username": "LOCAL_TEST_USERNAME",
            "live_local_login_password_env": "LOCAL_TEST_PASSWORD",
            "live_reject_login_username": "REJECT_TEST_USERNAME",
            "live_reject_login_password_env": "REJECT_TEST_PASSWORD",
            "live_reject_login_expected_statuses": "3,4",
            "desktop_client_proof_file": "PATH_TO_DESKTOP_CLIENT_PROOF.md",
            "runtime_data_backup_proof_file": "PATH_TO_RUNTIME_DATA_BACKUP_PROOF.md",
            "agent_chat_delivery_log_text": "AGENT_TO_PLAYER_MARKER",
            "agent_chat_delivery_log_to_name": "PLAYER_USERNAME",
            "agent_chat_delivery_log_channel": "agent",
            "live_discord": False,
            "agent_chat_log_text": "DISCORD_TO_SERVER_MARKER",
            "agent_chat_log_from_type": "discord",
            "agent_chat_log_from_bot": "false",
            "agent_chat_log_discord_message_id": "DISCORD_MESSAGE_ID",
            "agent_chat_log_channel": "agent",
            "agent_chat_blocked_log_text": "BLOCKED_DISCORD_MARKER",
            "agent_chat_blocked_log_channel": "agent",
            "discord_channel_message_text": "SERVER_TO_DISCORD_MARKER",
            "discord_channel_message_agent": ["AGENT_PROFILE"],
            "require_full_proof": True,
            "require_encrypted_external": True,
            "_notes": "Replace every placeholder and remove unused Discord fields before passing with --proof-manifest. Password fields are environment variable names, not passwords. Keep live_reject_login_expected_statuses, usually 3,4, so final fail-closed auth proof pins the accepted rejection status codes. require_full_proof=true makes readiness/prep treat this as a final gate. require_encrypted_external=true keeps final player packages on Tailscale, WireGuard/VPN, or client_tls_tunnel instead of plaintext direct_tcp. Transport: {}".format(transport),
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def write_text(path, text, mode_bits=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if os.name == "posix":
        path.chmod(mode_bits)


def main():
    parser = argparse.ArgumentParser(description="Render server-side deployment templates.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--install-root", default=DEFAULT_INSTALL_ROOT)
    parser.add_argument("--service-user", default="2006scape")
    parser.add_argument("--service-group", default="2006scape")
    parser.add_argument("--config-path", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--env-path", default=DEFAULT_ENV_PATH)
    parser.add_argument("--run-dir", default=DEFAULT_RUN_DIR)
    parser.add_argument("--java-bin", default="/usr/bin/java")
    parser.add_argument("--java-opts", default="-Xms512m -Xmx1024m -Dsun.zip.disableMemoryMapping=true")
    parser.add_argument("--tailscale-interface", default="tailscale0")
    parser.add_argument("--vpn-interface", default="wg0")
    parser.add_argument("--allow-wildcard-bind", action="store_true",
            help="Allow wildcard bind hosts only when wildcard_bind_confirmed=true and the host firewall/private network is verified.")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT_DIR / config_path
    preflight_config(config_path, args)
    config = load_config(config_path)
    validate_args(config, args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(config_path, output_dir / "ServerConfig.json")
    write_text(output_dir / "2006scape-server.service", service_text(args))
    write_text(output_dir / "2006scape-server.env", env_text(args))
    write_text(output_dir / "firewall-ufw-example.sh", firewall_text(config, args), 0o755)
    tailscale_policy_path = output_dir / "tailscale-policy-grants.example.json"
    if mode(config) == "tailscale":
        write_text(tailscale_policy_path, tailscale_policy_grants_text(config))
    elif tailscale_policy_path.exists():
        tailscale_policy_path.unlink()
    write_text(output_dir / "README.md", readme_text(config, args))
    write_text(output_dir / "player-handoff-template.md", player_handoff_template_text(config, args))
    write_text(output_dir / "proof-templates" / "deployment-proof-manifest.json", deployment_proof_manifest_template_text(config))
    write_text(output_dir / "proof-templates" / "desktop-client-proof.md", desktop_client_proof_template_text(config, args))
    write_text(output_dir / "proof-templates" / "runtime-data-backup-proof.md", runtime_data_backup_proof_template_text(args))
    print("ok: rendered server deployment files in {}".format(output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
