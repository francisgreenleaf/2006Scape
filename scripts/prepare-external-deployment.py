#!/usr/bin/env python3
"""Prepare external-player client artifacts and deployment evidence."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.deployment_proof_manifest import FIELD_TYPES, apply_proof_manifest


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT_DIR / "2006Scape Server" / "ServerConfig.json"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "dist" / "external-deployment"
DEFAULT_ACCOUNTS_DIR = ROOT_DIR / "2006Scape Server" / "data" / "accounts"
DEFAULT_SECRETS = ROOT_DIR / "2006Scape Server" / "data" / "secrets.json"


def run(argv, env=None):
    subprocess.check_call(argv, cwd=str(ROOT_DIR), env=env)


def run_precheck(argv):
    exit_code = subprocess.call(argv, cwd=str(ROOT_DIR))
    if exit_code != 0:
        raise SystemExit(exit_code)


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


def build_report_args(args, client_dist, archive, report_path, server_deployment_dir,
        client_tls_tunnel_dir=None):
    argv = [
        "scripts/deployment-readiness-report.py",
        "--config",
        args.config,
        "--client-dist",
        str(client_dist),
        "--archive",
        str(archive),
        "--accounts-dir",
        args.accounts_dir,
        "--secrets",
        args.secrets,
        "--output",
        str(report_path),
        "--server-deployment-dir",
        str(server_deployment_dir),
    ]
    if client_tls_tunnel_dir is not None:
        argv.extend(["--client-tls-tunnel-dir", str(client_tls_tunnel_dir)])
    if args.json_output:
        argv.extend(["--json-output", args.json_output])
    if args.allow_empty_accounts:
        argv.append("--allow-empty-accounts")
    if args.allow_wildcard_bind:
        argv.append("--allow-wildcard-bind")
    if args.allow_placeholder_network_config:
        argv.append("--allow-placeholder-network-config")
    if args.allow_placeholder_discord_secrets:
        argv.append("--allow-placeholder-discord-secrets")
    if args.require_full_proof:
        argv.append("--require-full-proof")
    if args.live:
        argv.append("--live")
    if args.timeout:
        argv.extend(["--timeout", str(args.timeout)])
    if args.tls_sni_host:
        argv.extend(["--tls-sni-host", args.tls_sni_host])
    if args.allow_untrusted_client_tls:
        argv.append("--allow-untrusted-client-tls")
    if args.live_login_username:
        argv.extend(["--live-login-username", args.live_login_username])
    if args.live_login_password_env:
        argv.extend(["--live-login-password-env", args.live_login_password_env])
    if args.live_login_hold_seconds:
        argv.extend(["--live-login-hold-seconds", str(args.live_login_hold_seconds)])
    if args.live_local_login_username:
        argv.extend(["--live-local-login-username", args.live_local_login_username])
    if args.live_local_login_password_env:
        argv.extend(["--live-local-login-password-env", args.live_local_login_password_env])
    if args.live_local_login_username or args.live_local_host != "127.0.0.1":
        argv.extend(["--live-local-host", args.live_local_host])
    if args.live_local_port:
        argv.extend(["--live-local-port", str(args.live_local_port)])
    if args.live_reject_login_username:
        argv.extend(["--live-reject-login-username", args.live_reject_login_username])
    if args.live_reject_login_password_env:
        argv.extend(["--live-reject-login-password-env", args.live_reject_login_password_env])
    if args.live_reject_login_expected_statuses:
        argv.extend(["--live-reject-login-expected-statuses", args.live_reject_login_expected_statuses])
    if args.live_discord:
        argv.append("--live-discord")
    if args.agent_chat_log_root:
        argv.extend(["--agent-chat-log-root", args.agent_chat_log_root])
    if args.agent_chat_log_text:
        argv.extend(["--agent-chat-log-text", args.agent_chat_log_text])
    if args.agent_chat_log_from_type:
        argv.extend(["--agent-chat-log-from-type", args.agent_chat_log_from_type])
    if args.agent_chat_log_from_name:
        argv.extend(["--agent-chat-log-from-name", args.agent_chat_log_from_name])
    if args.agent_chat_log_from_profile:
        argv.extend(["--agent-chat-log-from-profile", args.agent_chat_log_from_profile])
    if args.agent_chat_log_from_bot:
        argv.extend(["--agent-chat-log-from-bot", args.agent_chat_log_from_bot])
    if args.agent_chat_log_discord_message_id:
        argv.extend(["--agent-chat-log-discord-message-id", args.agent_chat_log_discord_message_id])
    if args.agent_chat_log_to_type:
        argv.extend(["--agent-chat-log-to-type", args.agent_chat_log_to_type])
    if args.agent_chat_log_to_name:
        argv.extend(["--agent-chat-log-to-name", args.agent_chat_log_to_name])
    if args.agent_chat_log_channel:
        argv.extend(["--agent-chat-log-channel", args.agent_chat_log_channel])
    if args.agent_chat_log_since_seconds:
        argv.extend(["--agent-chat-log-since-seconds", str(args.agent_chat_log_since_seconds)])
    if args.agent_chat_log_since_id:
        argv.extend(["--agent-chat-log-since-id", str(args.agent_chat_log_since_id)])
    if args.agent_chat_blocked_log_root:
        argv.extend(["--agent-chat-blocked-log-root", args.agent_chat_blocked_log_root])
    if args.agent_chat_blocked_log_text:
        argv.extend(["--agent-chat-blocked-log-text", args.agent_chat_blocked_log_text])
    if args.agent_chat_blocked_log_channel:
        argv.extend(["--agent-chat-blocked-log-channel", args.agent_chat_blocked_log_channel])
    if args.agent_chat_blocked_log_since_seconds:
        argv.extend(["--agent-chat-blocked-log-since-seconds", str(args.agent_chat_blocked_log_since_seconds)])
    if args.agent_chat_blocked_log_since_id:
        argv.extend(["--agent-chat-blocked-log-since-id", str(args.agent_chat_blocked_log_since_id)])
    if args.agent_chat_delivery_log_root:
        argv.extend(["--agent-chat-delivery-log-root", args.agent_chat_delivery_log_root])
    if args.agent_chat_delivery_log_text:
        argv.extend(["--agent-chat-delivery-log-text", args.agent_chat_delivery_log_text])
    if args.agent_chat_delivery_log_to_name:
        argv.extend(["--agent-chat-delivery-log-to-name", args.agent_chat_delivery_log_to_name])
    if args.agent_chat_delivery_log_channel:
        argv.extend(["--agent-chat-delivery-log-channel", args.agent_chat_delivery_log_channel])
    if args.agent_chat_delivery_log_since_seconds:
        argv.extend(["--agent-chat-delivery-log-since-seconds", str(args.agent_chat_delivery_log_since_seconds)])
    if args.agent_chat_delivery_log_since_id:
        argv.extend(["--agent-chat-delivery-log-since-id", str(args.agent_chat_delivery_log_since_id)])
    if args.desktop_client_proof_file:
        argv.extend(["--desktop-client-proof-file", args.desktop_client_proof_file])
    if args.runtime_data_backup_proof_file:
        argv.extend(["--runtime-data-backup-proof-file", args.runtime_data_backup_proof_file])
    if args.discord_channel_message_text:
        argv.extend(["--discord-channel-message-text", args.discord_channel_message_text])
    for agent in args.discord_channel_message_agent:
        argv.extend(["--discord-channel-message-agent", agent])
    if args.discord_channel_message_limit:
        argv.extend(["--discord-channel-message-limit", str(args.discord_channel_message_limit)])
    if args.discord_channel_message_after_id:
        argv.extend(["--discord-channel-message-after-id", args.discord_channel_message_after_id])
    if args.discord_channel_message_allow_human_author:
        argv.append("--discord-channel-message-allow-human-author")
    if args.discord_channel_message_require_all:
        argv.append("--discord-channel-message-require-all")
    if args.command_timeout:
        argv.extend(["--command-timeout", str(args.command_timeout)])
    return argv


def validate_chat_proof_args(parser, args):
    if args.agent_chat_log_text:
        if args.agent_chat_log_from_type.strip().lower() != "discord":
            parser.error(
                "--agent-chat-log-text is recorded as Discord-to-server proof; "
                "pass --agent-chat-log-from-type discord"
            )
        if args.agent_chat_log_from_bot != "false":
            parser.error(
                "--agent-chat-log-text Discord proof requires "
                "--agent-chat-log-from-bot false"
            )
    if args.agent_chat_blocked_log_text and args.agent_chat_blocked_log_text == args.agent_chat_log_text:
        parser.error("--agent-chat-blocked-log-text must use a different marker than --agent-chat-log-text")
    if args.agent_chat_delivery_log_text and not args.agent_chat_delivery_log_to_name:
        parser.error("--agent-chat-delivery-log-text requires --agent-chat-delivery-log-to-name")
    if args.agent_chat_delivery_log_to_name and not args.agent_chat_delivery_log_text:
        parser.error("--agent-chat-delivery-log-to-name requires --agent-chat-delivery-log-text")
    if args.discord_channel_message_text and args.discord_channel_message_allow_human_author:
        parser.error(
            "--discord-channel-message-allow-human-author weakens server-to-Discord "
            "proof; omit it so the verifier requires the configured bot author"
        )


def validate_require_full_proof_args(parser, args):
    if not args.require_full_proof:
        return
    blocked = []
    if args.allow_empty_accounts:
        blocked.append("--allow-empty-accounts")
    if args.allow_placeholder_network_config:
        blocked.append("--allow-placeholder-network-config")
    if args.allow_placeholder_discord_secrets:
        blocked.append("--allow-placeholder-discord-secrets")
    if args.allow_untrusted_client_tls:
        blocked.append("--allow-untrusted-client-tls")
    if blocked:
        parser.error(
            "--require-full-proof cannot be combined with source/test-only flags: {}".format(
                ", ".join(blocked)
            )
        )


def validate_encrypted_external_args(parser, args, config):
    if not args.require_encrypted_external:
        return
    mode = str(config.get("external_transport_mode", "") or "").strip().lower()
    allowed = ("tailscale", "wireguard", "vpn", "client_tls_tunnel")
    if mode not in allowed:
        parser.error(
            "--require-encrypted-external requires external_transport_mode to be one of {}; "
            "direct_tcp is plaintext and should only be used for explicit no-install smoke tests".format(
                ", ".join(allowed)
            )
        )
    if config.get("require_secure_external_transport") is not True:
        parser.error("--require-encrypted-external requires require_secure_external_transport=true")
    if config.get("secure_external_transport_confirmed") is not True:
        parser.error("--require-encrypted-external requires secure_external_transport_confirmed=true")


def merged_proof_manifest_values(args):
    values = {}
    for field in sorted(FIELD_TYPES):
        if not hasattr(args, field):
            continue
        value = getattr(args, field)
        if value is None:
            continue
        if isinstance(value, bool):
            if value:
                values[field] = value
            continue
        if isinstance(value, str):
            if value.strip():
                values[field] = value
            continue
        if isinstance(value, list):
            if value:
                values[field] = value
            continue
        if isinstance(value, (int, float)):
            if value:
                values[field] = value
            continue
        values[field] = value
    return values


def proof_manifest_precheck_args(args, manifest_path):
    argv = [
        "scripts/check-deployment-proof-manifest.py",
        str(manifest_path),
        "--config",
        args.config,
        "--require-full-proof",
        "--check-files",
        "--check-env",
    ]
    if args.secrets:
        argv.extend(["--secrets", args.secrets])
    if args.live_discord or args.agent_chat_log_text or args.discord_channel_message_text:
        argv.append("--discord-required")
    if args.agent_chat_blocked_log_text:
        argv.append("--blocked-routing-required")
    return argv


def run_final_proof_manifest_precheck(args):
    if not args.require_full_proof:
        return
    values = merged_proof_manifest_values(args)
    with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix="2006scape-merged-proof-manifest-",
            suffix=".json",
            delete=False,
    ) as tmp:
        json.dump(values, tmp, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    try:
        run_precheck(proof_manifest_precheck_args(args, tmp_path))
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description="Prepare external 2006Scape deployment artifacts.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
            help="External-player server config to package against.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
            help="Directory for client package, zip, readiness report, and optional operator tunnel templates.")
    parser.add_argument("--accounts-dir", default=str(DEFAULT_ACCOUNTS_DIR))
    parser.add_argument("--secrets", default=str(DEFAULT_SECRETS))
    parser.add_argument("--proof-manifest", default="",
            help=("Optional JSON file containing live/manual proof arguments for the generated readiness report. "
                  "CLI flags override manifest fields. Store password env var names, not passwords."))
    parser.add_argument("--json-output", default="",
            help="Optional machine-readable JSON readiness report path passed through to deployment-readiness-report.py.")
    parser.add_argument("--skip-build", action="store_true",
            help="Pass SKIP_BUILD=1 to package-client.sh. Use only when the client jar is already current.")
    parser.add_argument("--allow-empty-accounts", action="store_true")
    parser.add_argument("--allow-wildcard-bind", action="store_true")
    parser.add_argument("--allow-placeholder-network-config", action="store_true",
            help="Allow tracked sample hosts. Source validation only; do not use for real deployments.")
    parser.add_argument("--allow-placeholder-discord-secrets", action="store_true",
            help="Allow tracked sample Discord secrets. Source validation only; do not use for real deployments.")
    parser.add_argument("--require-full-proof", action="store_true",
            help=("Fail unless the generated readiness report records all required live/manual proof categories. "
                  "Use only for final deployment gates after the remote runtime and evidence exist."))
    parser.add_argument("--require-encrypted-external", action="store_true",
            help=("Refuse to prepare/package a downloadable external client unless the config uses an encrypted/private "
                  "transport: tailscale, wireguard, vpn, or client_tls_tunnel. direct_tcp is plaintext."))
    parser.add_argument("--live", action="store_true",
            help="Record live reachability checks in the readiness report after the remote server is intentionally running.")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--tls-sni-host", default="")
    parser.add_argument("--allow-untrusted-client-tls", action="store_true")
    parser.add_argument("--live-login-username", default="")
    parser.add_argument("--live-login-password-env", default="")
    parser.add_argument("--live-login-hold-seconds", type=float, default=0.0)
    parser.add_argument("--live-local-login-username", default="")
    parser.add_argument("--live-local-login-password-env", default="")
    parser.add_argument("--live-local-host", default="127.0.0.1")
    parser.add_argument("--live-local-port", type=int, default=0)
    parser.add_argument("--live-reject-login-username", default="")
    parser.add_argument("--live-reject-login-password-env", default="")
    parser.add_argument("--live-reject-login-expected-statuses", default="")
    parser.add_argument("--live-discord", action="store_true")
    parser.add_argument("--agent-chat-log-root", default=str(ROOT_DIR / "2006Scape Server" / "data" / "logs" / "agent-chat"))
    parser.add_argument("--agent-chat-log-text", default="")
    parser.add_argument("--agent-chat-log-from-type", default="")
    parser.add_argument("--agent-chat-log-from-name", default="")
    parser.add_argument("--agent-chat-log-from-profile", default="")
    parser.add_argument("--agent-chat-log-from-bot", choices=("true", "false"), default="")
    parser.add_argument("--agent-chat-log-discord-message-id", default="")
    parser.add_argument("--agent-chat-log-to-type", default="")
    parser.add_argument("--agent-chat-log-to-name", default="")
    parser.add_argument("--agent-chat-log-channel", default="")
    parser.add_argument("--agent-chat-log-since-seconds", type=float, default=0.0)
    parser.add_argument("--agent-chat-log-since-id", type=int, default=0)
    parser.add_argument("--agent-chat-blocked-log-root", default="")
    parser.add_argument("--agent-chat-blocked-log-text", default="")
    parser.add_argument("--agent-chat-blocked-log-channel", default="")
    parser.add_argument("--agent-chat-blocked-log-since-seconds", type=float, default=0.0)
    parser.add_argument("--agent-chat-blocked-log-since-id", type=int, default=0)
    parser.add_argument("--agent-chat-delivery-log-root", default="")
    parser.add_argument("--agent-chat-delivery-log-text", default="")
    parser.add_argument("--agent-chat-delivery-log-to-name", default="")
    parser.add_argument("--agent-chat-delivery-log-channel", default="agent")
    parser.add_argument("--agent-chat-delivery-log-since-seconds", type=float, default=0.0)
    parser.add_argument("--agent-chat-delivery-log-since-id", type=int, default=0)
    parser.add_argument("--desktop-client-proof-file", default="",
            help=("Optional operator-written evidence file for same-host plus external desktop client "
                  "coexistence; must mention local client, external client, external transport, and concurrency."))
    parser.add_argument("--runtime-data-backup-proof-file", default="",
            help=("Optional operator-written evidence file for runtime-data backup before remote replacement/restart; "
                  "must be a real non-symlink file and mention character saves, account records, Discord secrets, "
                  "backup artifact, date/timestamp, and backup archive sha256."))
    parser.add_argument("--discord-channel-message-text", default="")
    parser.add_argument("--discord-channel-message-agent", action="append", default=[])
    parser.add_argument("--discord-channel-message-limit", type=int, default=50)
    parser.add_argument("--discord-channel-message-after-id", default="")
    parser.add_argument("--discord-channel-message-allow-human-author", action="store_true")
    parser.add_argument("--discord-channel-message-require-all", action="store_true")
    parser.add_argument("--command-timeout", type=float, default=120.0)
    parser.add_argument("--server-install-root", default="/opt/2006scape")
    parser.add_argument("--server-service-user", default="2006scape")
    parser.add_argument("--server-service-group", default="2006scape")
    parser.add_argument("--server-config-path", default="/etc/2006scape/ServerConfig.json")
    parser.add_argument("--server-env-path", default="/etc/2006scape/server.env")
    parser.add_argument("--server-run-dir", default="/var/lib/2006scape/run")
    parser.add_argument("--server-java-bin", default="/usr/bin/java")
    args = parser.parse_args()
    apply_proof_manifest(parser, args, sys.argv[1:])
    validate_chat_proof_args(parser, args)
    validate_require_full_proof_args(parser, args)

    config = load_config(args.config)
    validate_encrypted_external_args(parser, args, config)
    run_final_proof_manifest_precheck(args)
    output_dir = Path(args.output_dir)
    client_dist = output_dir / "2006scape-client"
    archive = output_dir / "2006scape-client.zip"
    report_path = output_dir / "deployment-readiness-report.md"
    tunnel_operator_dir = output_dir / "client-tls-tunnel-operator"
    server_deployment_dir = output_dir / "server-deployment"
    output_dir.mkdir(parents=True, exist_ok=True)

    package_env = dict(os.environ)
    package_env["CLIENT_SERVER_CONFIG"] = args.config
    package_env["CLIENT_DIST_DIR"] = str(client_dist)
    package_env["CLIENT_ARCHIVE_PATH"] = str(archive)
    if args.skip_build:
        package_env["SKIP_BUILD"] = "1"
    if args.allow_wildcard_bind:
        package_env["CLIENT_ALLOW_WILDCARD_BIND"] = "1"
    if args.allow_placeholder_network_config:
        package_env["CLIENT_ALLOW_PLACEHOLDER_NETWORK_CONFIG"] = "1"
    if args.require_encrypted_external:
        package_env["CLIENT_REQUIRE_ENCRYPTED_EXTERNAL"] = "1"

    run(["scripts/package-client.sh"], env=package_env)

    rendered_tunnel = False
    mode = str(config.get("external_transport_mode", "") or "").strip().lower()
    if mode == "client_tls_tunnel":
        tunnel_args = [
            "scripts/render-client-tls-tunnel-config.py",
            "--config",
            args.config,
            "--output-dir",
            str(tunnel_operator_dir),
        ]
        if args.tls_sni_host:
            tunnel_args.extend(["--tls-cert-host", args.tls_sni_host])
        if args.allow_placeholder_network_config:
            tunnel_args.append("--allow-placeholder-network-config")
        run(tunnel_args)
        rendered_tunnel = True

    server_deployment_args = [
        "scripts/render-server-deployment-files.py",
        "--config",
        args.config,
        "--output-dir",
        str(server_deployment_dir),
        "--install-root",
        args.server_install_root,
        "--service-user",
        args.server_service_user,
        "--service-group",
        args.server_service_group,
        "--config-path",
        args.server_config_path,
        "--env-path",
        args.server_env_path,
        "--run-dir",
        args.server_run_dir,
        "--java-bin",
        args.server_java_bin,
    ]
    if args.allow_wildcard_bind:
        server_deployment_args.append("--allow-wildcard-bind")
    run(server_deployment_args)
    run(build_report_args(
        args,
        client_dist,
        archive,
        report_path,
        server_deployment_dir,
        tunnel_operator_dir if rendered_tunnel else None,
    ))

    print("prepared external deployment artifacts:")
    print("client_dist: {}".format(client_dist))
    print("archive: {}".format(archive))
    print("readiness_report: {}".format(report_path))
    if args.json_output:
        print("readiness_json: {}".format(args.json_output))
    if rendered_tunnel:
        print("client_tls_tunnel_operator: {}".format(tunnel_operator_dir))
    else:
        print("client_tls_tunnel_operator: skipped; external_transport_mode={}".format(mode or "unspecified"))
    print("encrypted_external_required: {}".format("yes" if args.require_encrypted_external else "no"))
    print("server_deployment: {}".format(server_deployment_dir))
    print("runtime: not started, stopped, or restarted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
