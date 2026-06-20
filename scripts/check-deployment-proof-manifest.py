#!/usr/bin/env python3
"""Check deployment proof-manifest completeness without running deployment checks."""

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR / "lib") not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR / "lib"))

from deployment_proof_manifest import PASSWORD_ENV_FIELDS, read_manifest_values  # noqa: E402


BASE_FULL_PROOF_FIELDS = (
    "live",
    "live_login_username",
    "live_login_password_env",
    "live_local_login_username",
    "live_local_login_password_env",
    "live_reject_login_username",
    "live_reject_login_password_env",
    "live_reject_login_expected_statuses",
    "desktop_client_proof_file",
    "runtime_data_backup_proof_file",
    "agent_chat_delivery_log_text",
    "agent_chat_delivery_log_to_name",
)

DISCORD_FULL_PROOF_FIELDS = (
    "live_discord",
    "agent_chat_log_text",
    "agent_chat_log_from_type",
    "agent_chat_log_from_bot",
    "discord_channel_message_text",
    "discord_channel_message_agent",
)

FILE_FIELDS = (
    "desktop_client_proof_file",
    "runtime_data_backup_proof_file",
)
ENCRYPTED_EXTERNAL_TRANSPORTS = ("tailscale", "wireguard", "vpn", "client_tls_tunnel")

READINESS_REPORT_SCRIPT = SCRIPT_DIR / "deployment-readiness-report.py"
READINESS_REPORT_MODULE = None


def load_readiness_report_module():
    global READINESS_REPORT_MODULE
    if READINESS_REPORT_MODULE is not None:
        return READINESS_REPORT_MODULE
    spec = importlib.util.spec_from_file_location("deployment_readiness_report", READINESS_REPORT_SCRIPT)
    if spec is None or spec.loader is None:
        raise ValueError("could not load readiness proof validators from {}".format(READINESS_REPORT_SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    READINESS_REPORT_MODULE = module
    return module


def load_json_file(path, label):
    if not path:
        return {}
    candidate = Path(path)
    if candidate.is_symlink():
        raise ValueError("{} must not be a symlink: {}".format(label, candidate))
    if not candidate.is_file():
        raise ValueError("{} is missing or not a file: {}".format(label, candidate))
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("{} is not valid JSON: {}: {}".format(label, candidate, exc))
    if not isinstance(data, dict):
        raise ValueError("{} must be a JSON object: {}".format(label, candidate))
    return data


def discord_enabled_in_config(config_path):
    if not config_path:
        return False
    config = load_json_file(config_path, "config")
    return config.get("agent_chat_discord_enabled") is True


def discord_routing_filters_configured(secrets_path):
    if not secrets_path:
        return False
    secrets = load_json_file(secrets_path, "secrets")
    bots = secrets.get("agent-discord-bots", [])
    if not isinstance(bots, list):
        return False
    for bot in bots:
        if not isinstance(bot, dict):
            continue
        if "allowedAgents" in bot or "allowed_agents" in bot:
            return True
        if "allowedPlayers" in bot or "allowed_players" in bot:
            return True
        for key in ("allowBroadcast", "allow_broadcast"):
            if key in bot and bot.get(key) is False:
                return True
    return False


def value_present(values, field):
    if field not in values:
        return False
    value = values[field]
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return True


def encrypted_external_config_errors(config_path):
    if not config_path:
        return ["require_encrypted_external needs --config so transport settings can be checked"]
    config = load_json_file(config_path, "config")
    mode = str(config.get("external_transport_mode", "") or "").strip().lower()
    errors = []
    if mode not in ENCRYPTED_EXTERNAL_TRANSPORTS:
        errors.append(
            "require_encrypted_external requires external_transport_mode to be one of {}; "
            "direct_tcp is plaintext".format(", ".join(ENCRYPTED_EXTERNAL_TRANSPORTS))
        )
    if config.get("require_secure_external_transport") is not True:
        errors.append("require_encrypted_external requires require_secure_external_transport=true")
    if config.get("secure_external_transport_confirmed") is not True:
        errors.append("require_encrypted_external requires secure_external_transport_confirmed=true")
    return errors


def evaluate_manifest(values, args):
    errors = []
    warnings = []
    proof_file_checks = []

    manifest_requests_full = values.get("require_full_proof") is True
    manifest_requests_encrypted = values.get("require_encrypted_external") is True
    require_full = args.require_full_proof or manifest_requests_full
    require_encrypted = args.require_encrypted_external or manifest_requests_encrypted
    discord_required = bool(
        args.discord_required
        or values.get("live_discord") is True
        or values.get("agent_chat_log_text")
        or values.get("discord_channel_message_text")
        or discord_enabled_in_config(args.config)
    )
    blocked_required = bool(
        args.blocked_routing_required
        or values.get("agent_chat_blocked_log_text")
        or (discord_required and discord_routing_filters_configured(args.secrets))
    )

    if require_full:
        if args.require_full_proof and not manifest_requests_full:
            errors.append("final proof manifest must set require_full_proof=true")
        if not manifest_requests_encrypted:
            errors.append("final proof manifest must set require_encrypted_external=true")
        for field in BASE_FULL_PROOF_FIELDS:
            if not value_present(values, field):
                errors.append("missing required full-proof field: {}".format(field))
        if values.get("live") is not True:
            errors.append("full proof requires live=true")

    if require_encrypted:
        if args.require_encrypted_external and not manifest_requests_encrypted:
            errors.append("encrypted proof manifest must set require_encrypted_external=true")
        errors.extend(encrypted_external_config_errors(args.config))

    if require_full and discord_required:
        for field in DISCORD_FULL_PROOF_FIELDS:
            if not value_present(values, field):
                errors.append("missing required Discord proof field: {}".format(field))
        if values.get("live_discord") is not True:
            errors.append("Discord proof requires live_discord=true")
        if str(values.get("agent_chat_log_from_type", "")).strip().lower() != "discord":
            errors.append("Discord-to-server proof requires agent_chat_log_from_type=discord")
        if str(values.get("agent_chat_log_from_bot", "")).strip().lower() != "false":
            errors.append("Discord-to-server proof requires agent_chat_log_from_bot=false")

    if require_full and blocked_required and not value_present(values, "agent_chat_blocked_log_text"):
        errors.append("missing required blocked-routing proof field: agent_chat_blocked_log_text")

    if args.check_env:
        for field in sorted(PASSWORD_ENV_FIELDS):
            env_name = values.get(field)
            if env_name and env_name not in os.environ:
                errors.append("environment variable named by {} is not set: {}".format(field, env_name))

    if args.check_files:
        readiness = load_readiness_report_module()
        for field in FILE_FIELDS:
            proof_path = values.get(field)
            if not proof_path:
                continue
            if field == "desktop_client_proof_file":
                result = readiness.run_desktop_client_proof_file_check(proof_path)
            elif field == "runtime_data_backup_proof_file":
                result = readiness.run_runtime_data_backup_proof_file_check(proof_path)
            else:
                raise ValueError("unsupported proof-file field: {}".format(field))
            proof_file_checks.append({
                "field": field,
                "path": proof_path,
                "status": result["status"],
                "output": result["output"],
            })
            if result["exitCode"] != 0:
                errors.append("{} failed proof-file validation: {}".format(field, result["output"]))

    if discord_required and not args.config and values.get("live_discord") is not True:
        warnings.append("Discord proof was inferred from manifest fields; pass --config to infer deployment requirements from config.")

    return {
        "status": "PASS" if not errors else "FAIL",
        "requireFullProof": require_full,
        "requireEncryptedExternal": require_encrypted,
        "manifestRequestsFullProof": manifest_requests_full,
        "manifestRequestsEncryptedExternal": manifest_requests_encrypted,
        "discordRequired": discord_required,
        "blockedRoutingRequired": blocked_required,
        "fieldCount": len(values),
        "errors": errors,
        "proofFileChecks": proof_file_checks,
        "warnings": warnings,
    }


def print_human(manifest_path, result):
    print("manifest: {}".format(manifest_path))
    print("status: {}".format(result["status"]))
    print("requireFullProof: {}".format("yes" if result["requireFullProof"] else "no"))
    print("requireEncryptedExternal: {}".format("yes" if result["requireEncryptedExternal"] else "no"))
    print("discordRequired: {}".format("yes" if result["discordRequired"] else "no"))
    print("blockedRoutingRequired: {}".format("yes" if result["blockedRoutingRequired"] else "no"))
    print("fields: {}".format(result["fieldCount"]))
    for check in result.get("proofFileChecks", []):
        print("proofFileCheck: {field} {status} {path}".format(**check))
    for warning in result["warnings"]:
        print("warning: {}".format(warning))
    for error in result["errors"]:
        print("error: {}".format(error))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate a deployment proof manifest before running readiness/prep commands."
    )
    parser.add_argument("manifest", help="Path to a copied and filled deployment-proof-manifest JSON file.")
    parser.add_argument("--config", default="", help="Optional ServerConfig JSON used to infer Discord proof requirements.")
    parser.add_argument("--secrets", default="", help="Optional secrets JSON used to infer blocked Discord routing proof.")
    parser.add_argument("--require-full-proof", action="store_true",
            help="Require the manifest to contain the full live/manual proof field set.")
    parser.add_argument("--require-encrypted-external", action="store_true",
            help="Require the manifest and config to prove an encrypted/private external transport.")
    parser.add_argument("--discord-required", action="store_true",
            help="Require Discord bot/channel, Discord-to-server, and server-to-Discord proof fields.")
    parser.add_argument("--blocked-routing-required", action="store_true",
            help="Require blocked Discord routing absence proof.")
    parser.add_argument("--check-env", action="store_true",
            help="Verify password environment-variable names in the manifest are currently set.")
    parser.add_argument("--check-files", action="store_true",
            help=("Validate referenced manual proof files with readiness-report proof checks, including "
                  "desktop evidence and runtime backup archive checksum/details."))
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    try:
        values = read_manifest_values(args.manifest, allow_placeholders=False)
        result = evaluate_manifest(values, args)
    except ValueError as exc:
        result = {
            "status": "FAIL",
            "requireFullProof": args.require_full_proof,
            "requireEncryptedExternal": args.require_encrypted_external,
            "manifestRequestsFullProof": False,
            "manifestRequestsEncryptedExternal": False,
            "discordRequired": args.discord_required,
            "blockedRoutingRequired": args.blocked_routing_required,
            "fieldCount": 0,
            "errors": [str(exc)],
            "proofFileChecks": [],
            "warnings": [],
        }

    if args.json:
        payload = dict(result)
        payload["manifest"] = args.manifest
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_human(args.manifest, result)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
