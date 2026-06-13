#!/usr/bin/env python3
"""Write a redacted deployment-readiness report for external-player builds."""

import argparse
import datetime as _datetime
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.deployment_proof_manifest import apply_proof_manifest


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT_DIR / "2006Scape Server" / "ServerConfig.json"
DEFAULT_CLIENT_DIST = ROOT_DIR / "dist" / "2006scape-client"
DEFAULT_ACCOUNTS_DIR = ROOT_DIR / "2006Scape Server" / "data" / "accounts"
DEFAULT_SECRETS = ROOT_DIR / "2006Scape Server" / "data" / "secrets.json"
DEFAULT_AGENT_CHAT_LOG_ROOT = ROOT_DIR / "2006Scape Server" / "data" / "logs" / "agent-chat"
DEFAULT_OUTPUT = ROOT_DIR / "dist" / "deployment-readiness-report.md"
SENSITIVE_ENV_RE = re.compile(r"(?i)(password|token|secret|authorization|api[_-]?key)")
SENSITIVE_KEY_RE = re.compile(
    r"(?i)(\"(?:passwordHash|passwordSalt|password|token|secret|authorization|apiKey)\"\s*:\s*\")[^\"]+(\")"
)
SENSITIVE_ASSIGN_RE = re.compile(
    r"(?i)\b(password|token|secret|authorization|api[_-]?key)(\s*[=:]\s*)([^\s,;]+)"
)
DESKTOP_PROOF_REQUIREMENTS = [
    (
        "same-host/local Java client",
        re.compile(r"(?i)\b(same[- ]host|local|127\.0\.0\.1|localhost)\b"),
    ),
    (
        "external Java client",
        re.compile(r"(?i)\b(external|remote|public|direct[_-]?tcp|vpn|tailscale|wireguard|tunnel)\b"),
    ),
    (
        "external transport path",
        re.compile(r"(?i)\b(direct[_-]?tcp|public tcp|tailscale|wireguard|vpn|client[_-]?tls[_-]?tunnel|stunnel|tunnel)\b"),
    ),
    (
        "concurrent online observation",
        re.compile(r"(?i)\b(both|concurrent|simultaneous|same time|online together|remained online)\b"),
    ),
]
RUNTIME_DATA_BACKUP_PROOF_REQUIREMENTS = [
    (
        "character saves",
        re.compile(r"(?i)\b(data/characters|characters)\b"),
    ),
    (
        "PBKDF2 account records",
        re.compile(r"(?i)\b(data/accounts|accounts)\b"),
    ),
    (
        "Discord secrets",
        re.compile(r"(?i)\b(data/secrets\.json|secrets\.json|discord secrets)\b"),
    ),
    (
        "backup or archive artifact",
        re.compile(r"(?i)\b(backup|backed up|archive|tar|tgz|/var/backups/2006scape)\b"),
    ),
    (
        "date or timestamp",
        re.compile(r"(?i)\b(20\d\d-\d\d-\d\d|20\d{6}T\d{6}Z|date|timestamp|backed up at)\b"),
    ),
    (
        "no runtime start/stop/restart",
        re.compile(r"(?i)\b(not started, stopped, or restarted|without starting, stopping, or restarting|does not start, stop, or restart)\b"),
    ),
    (
        "readiness argument",
        re.compile(r"--runtime-data-backup-proof-file\b"),
    ),
]
RUNTIME_DATA_ARCHIVE_LINE_RE = re.compile(r"(?im)^-\s*archive:\s*(.+?)\s*$")
RUNTIME_DATA_ARCHIVE_SHA_RE = re.compile(r"(?im)^-\s*backup archive sha256:\s*([0-9a-f]{64})\s*$")
DESKTOP_EVIDENCE_LINE_RE = re.compile(r"(?im)^-\s*evidence:\s*(.+?)\s*$")
RUNTIME_DATA_ARCHIVE_REQUIRED_ENTRIES = {
    "characters",
    "accounts",
    "secrets.json",
}
PROOF_PLACEHOLDER_RE = re.compile(
    r"(?i)(REPLACE_|TODO|TBD|YYYY-MM-DD|YYYYMMDD|HHMMSS|PATH_TO_|FILL_ME|"
    r"LOCAL_USERNAME|EXTERNAL_USERNAME|BACKUP_ARCHIVE|SCREENSHOT_PATH|LOG_PATH)"
)


def utc_now():
    return _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0)


def iso_z(value):
    return value.isoformat().replace("+00:00", "Z")


def redact_text(text):
    redacted = SENSITIVE_KEY_RE.sub(r"\1[redacted]\2", text)
    redacted = SENSITIVE_ASSIGN_RE.sub(r"\1\2[redacted]", redacted)
    return redacted


def display_path(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT_DIR))
    except (OSError, ValueError):
        return str(path)


def format_command(argv):
    safe_parts = []
    for value in argv:
        if SENSITIVE_ENV_RE.search(str(value)) and "=" in str(value):
            key = str(value).split("=", 1)[0]
            safe_parts.append("{}=[redacted]".format(key))
        else:
            safe_parts.append(str(value))
    return " ".join(safe_parts)


def clip_output(text, limit):
    if len(text) <= limit:
        return text
    keep = max(0, limit - 96)
    return text[:keep] + "\n[output clipped: {} chars total]\n".format(len(text))


def run_command(label, argv, timeout):
    started = utc_now()
    try:
        completed = subprocess.run(
            argv,
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = completed.stdout or ""
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", "replace")
        output += "\ncommand timed out after {} seconds\n".format(timeout)
        exit_code = 124
    finished = utc_now()
    return {
        "label": label,
        "argv": argv,
        "exitCode": exit_code,
        "status": "PASS" if exit_code == 0 else "FAIL",
        "started": started,
        "finished": finished,
        "output": redact_text(clip_output(output.strip(), 12000)),
    }


def run_manual_proof_file_check(label, path, requirements, detail_label):
    started = utc_now()
    argv = ["manual-proof-file", path]
    output = ""
    exit_code = 0
    proof_path = Path(path)
    try:
        if not path:
            raise ValueError("proof file path is empty")
        if proof_path.is_symlink():
            raise ValueError("proof file must not be a symlink: {}".format(proof_path))
        if not proof_path.exists():
            raise ValueError("proof file does not exist: {}".format(proof_path))
        if not proof_path.is_file():
            raise ValueError("proof path is not a file: {}".format(proof_path))
        text = proof_path.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("proof file is empty: {}".format(proof_path))
        placeholder = PROOF_PLACEHOLDER_RE.search(text)
        if placeholder:
            raise ValueError(
                "proof file still contains placeholder text {!r}: {}".format(
                    placeholder.group(0),
                    proof_path,
                )
            )
        missing = [name for name, pattern in requirements if not pattern.search(text)]
        if missing:
            raise ValueError(
                "proof file is missing required {} detail(s): {}".format(
                    detail_label,
                    ", ".join(missing)
                )
            )
        output = "manual proof file accepted: {}\nrequired details: {}\n\n{}".format(
            display_path(proof_path),
            ", ".join(name for name, _pattern in requirements),
            clip_output(text.strip(), 4000),
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        output = str(exc)
        exit_code = 1
    finished = utc_now()
    return {
        "label": label,
        "argv": argv,
        "exitCode": exit_code,
        "status": "PASS" if exit_code == 0 else "FAIL",
        "started": started,
        "finished": finished,
        "output": redact_text(output.strip()),
    }


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_proof_value(value):
    clean = str(value or "").strip()
    if (clean.startswith("`") and clean.endswith("`")) or (
            clean.startswith('"') and clean.endswith('"')) or (
            clean.startswith("'") and clean.endswith("'")):
        clean = clean[1:-1].strip()
    return clean


def resolve_proof_archive_path(raw_value, proof_path):
    return resolve_proof_relative_path(raw_value, proof_path)


def resolve_proof_relative_path(raw_value, proof_path):
    candidate_path = Path(clean_proof_value(raw_value))
    if candidate_path.is_absolute():
        return candidate_path
    candidates = [
        proof_path.parent / candidate_path,
        ROOT_DIR / candidate_path,
        candidate_path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def verify_non_symlink_file(path, label, require_non_empty=False):
    if path.is_symlink():
        raise ValueError("{} must not be a symlink: {}".format(label, path))
    if not path.is_file():
        raise ValueError("{} is missing or not a file: {}".format(label, path))
    if require_non_empty and path.stat().st_size <= 0:
        raise ValueError("{} must not be empty: {}".format(label, path))
    return "{} verified: {}".format(label, display_path(path))


def verify_owner_only_file(path, label):
    if os.name != "posix":
        return ""
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError("{} permissions must be owner-only, got {:03o}: {}".format(label, mode, path))
    if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        raise ValueError("{} must not be executable, got {:03o}: {}".format(label, mode, path))
    return "{0} permissions owner-only {1:03o}".format(label, mode)


def verify_runtime_archive_contents(archive_path):
    try:
        with tarfile.open(str(archive_path), "r:*") as archive:
            names = set(archive.getnames())
    except (OSError, tarfile.TarError) as exc:
        raise ValueError("runtime data backup archive is not a readable tar archive: {}: {}".format(
            archive_path,
            exc,
        ))
    unsafe = [name for name in names if name.startswith("/") or ".." in Path(name).parts]
    if unsafe:
        raise ValueError("runtime data backup archive contains unsafe path names: {}".format(
            ", ".join(sorted(unsafe)[:5])
        ))
    missing = sorted(RUNTIME_DATA_ARCHIVE_REQUIRED_ENTRIES - names)
    if missing:
        raise ValueError("runtime data backup archive is missing required entries: {}".format(
            ", ".join(missing)
        ))
    return "archive entries present: {}".format(", ".join(sorted(RUNTIME_DATA_ARCHIVE_REQUIRED_ENTRIES)))


def run_runtime_data_backup_proof_file_check(path):
    base = run_manual_proof_file_check(
        "runtime data backup proof",
        path,
        RUNTIME_DATA_BACKUP_PROOF_REQUIREMENTS,
        "runtime data backup proof",
    )
    if base["exitCode"] != 0:
        return base

    proof_path = Path(path)
    try:
        text = proof_path.read_text(encoding="utf-8")
        archive_match = RUNTIME_DATA_ARCHIVE_LINE_RE.search(text)
        if not archive_match:
            raise ValueError("runtime data backup proof is missing an archive line: {}".format(proof_path))
        sha_match = RUNTIME_DATA_ARCHIVE_SHA_RE.search(text)
        if not sha_match:
            raise ValueError("runtime data backup proof is missing backup archive sha256: {}".format(proof_path))
        expected_digest = sha_match.group(1).lower()
        proof_permission_line = verify_owner_only_file(proof_path, "runtime data backup proof")
        archive_path = resolve_proof_archive_path(archive_match.group(1), proof_path)
        if archive_path.is_symlink():
            raise ValueError("runtime data backup archive must not be a symlink: {}".format(archive_path))
        if not archive_path.is_file():
            raise ValueError("runtime data backup archive is missing: {}".format(archive_path))
        permission_line = verify_owner_only_file(archive_path, "runtime data backup archive")
        actual_digest = sha256_file(archive_path)
        if actual_digest != expected_digest:
            raise ValueError("backup archive sha256 mismatch: expected {}, got {}".format(
                expected_digest,
                actual_digest,
            ))
        archive_line = verify_runtime_archive_contents(archive_path)
        extra = [
            "archive verified: {}".format(display_path(archive_path)),
            "backup archive sha256 verified: {}".format(actual_digest),
            archive_line,
        ]
        if proof_permission_line:
            extra.append(proof_permission_line)
        if permission_line:
            extra.append(permission_line)
        base["output"] = "{}\n{}".format(base["output"], redact_text("\n".join(extra))).strip()
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        base["exitCode"] = 1
        base["status"] = "FAIL"
        base["output"] = redact_text(str(exc))
    return base


def run_desktop_client_proof_file_check(path):
    base = run_manual_proof_file_check(
        "desktop client coexistence proof",
        path,
        DESKTOP_PROOF_REQUIREMENTS,
        "desktop proof",
    )
    if base["exitCode"] != 0:
        return base

    proof_path = Path(path)
    try:
        text = proof_path.read_text(encoding="utf-8")
        evidence_match = DESKTOP_EVIDENCE_LINE_RE.search(text)
        if not evidence_match:
            raise ValueError("desktop client proof is missing an evidence line: {}".format(proof_path))
        evidence_path = resolve_proof_relative_path(evidence_match.group(1), proof_path)
        evidence_line = verify_non_symlink_file(evidence_path, "desktop client proof evidence", True)
        base["output"] = "{}\n{}".format(base["output"], redact_text(evidence_line)).strip()
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        base["exitCode"] = 1
        base["status"] = "FAIL"
        base["output"] = redact_text(str(exc))
    return base


def discord_proof_requested(args):
    return bool(args.live_discord or args.agent_chat_log_text
            or args.agent_chat_blocked_log_text or args.discord_channel_message_text)


def discord_enabled_in_config(args):
    try:
        config_path = Path(args.config)
    except (AttributeError, TypeError):
        return False
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError):
        return False
    return config.get("agent_chat_discord_enabled") is True


def discord_proof_required(args):
    return discord_enabled_in_config(args) or discord_proof_requested(args)


def discord_routing_filters_configured(args):
    try:
        with Path(args.secrets).open("r", encoding="utf-8") as handle:
            secrets = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError):
        return False
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


def blocked_routing_proof_required(args):
    return discord_proof_required(args) and discord_routing_filters_configured(args)


def missing_proof_codes(args):
    missing = []
    if not args.live:
        missing.append("PUBLIC_REACHABILITY_AND_BRIDGE_NON_EXPOSURE")
    if not (args.live and args.live_login_username):
        missing.append("EXTERNAL_LOGIN_PROOF")
    if not (args.live and args.live_login_username and args.live_local_login_username):
        missing.append("CONCURRENT_LOCAL_LOGIN_PROOF")
    if not (args.live and args.live_reject_login_username and args.live_reject_login_expected_statuses):
        missing.append("FAIL_CLOSED_REJECTION_PROOF")
    if not args.desktop_client_proof_file:
        missing.append("DESKTOP_CLIENT_PROOF")
    if not args.runtime_data_backup_proof_file:
        missing.append("RUNTIME_DATA_BACKUP_PROOF")
    if not args.agent_chat_delivery_log_text:
        missing.append("AGENT_PLAYER_CHAT_DELIVERY_PROOF")
    if discord_proof_required(args):
        if not args.live_discord:
            missing.append("DISCORD_BOT_CHANNEL_PROOF")
        if not args.agent_chat_log_text:
            missing.append("DISCORD_TO_SERVER_CHAT_PROOF")
        if blocked_routing_proof_required(args) and not args.agent_chat_blocked_log_text:
            missing.append("BLOCKED_DISCORD_ROUTING_PROOF")
        if not args.discord_channel_message_text:
            missing.append("SERVER_TO_DISCORD_CHAT_PROOF")
    return missing


def deployment_proof_status(args, all_passed):
    if not all_passed:
        return "CHECKS_FAILED"
    if not args.live:
        return "STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF"
    missing = missing_proof_codes(args)
    if missing:
        return "LIVE_PROOF_PARTIAL_NEEDS_{}".format("_AND_".join(missing))
    if discord_proof_required(args):
        return "FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED"
    return "LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_PROOF_RECORDED_DISCORD_NOT_REQUESTED"


FULL_PROOF_STATUSES = (
    "FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED",
    "LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_PROOF_RECORDED_DISCORD_NOT_REQUESTED",
)


def remaining_live_proof_items(args):
    items = []
    if not args.live:
        items.append("The rebuilt server is intentionally restarted on the target host and public reachability plus bridge non-exposure are checked with `--live`.")
    if not args.runtime_data_backup_proof_file:
        items.append("`data/characters`, `data/accounts`, and `data/secrets.json` are backed up before replacing runtime files or restarting into new deployment bits.")
    if not args.desktop_client_proof_file:
        items.append("One local same-host Java client and one external Java client can remain online together over the selected external transport.")
    if not (args.live and args.live_login_username):
        items.append("A throwaway PBKDF2 account can log in over the deployed external network path.")
    if not (args.live and args.live_login_username and args.live_local_login_username):
        items.append("A same-host local PBKDF2 login can remain open concurrently with the external login.")
    if not (args.live and args.live_reject_login_username and args.live_reject_login_expected_statuses):
        items.append("At least one wrong-password, missing-account, disabled-account, or weak/tampered-account case fails closed over the deployed live path with pinned rejection status codes such as `--live-reject-login-expected-statuses 3,4`.")
    if not args.agent_chat_delivery_log_text:
        items.append("A structured agent/player chat message reaches a player chatbox and is verified through the AgentChatService delivery audit event.")
    if discord_proof_required(args):
        if not args.live_discord:
            items.append("Discord bot auth and channel reachability are proven with real ignored secrets.")
        if not args.agent_chat_log_text:
            items.append("A real human/non-bot Discord message is ingested into AgentChatService and verified in the chat log.")
        if blocked_routing_proof_required(args) and not args.agent_chat_blocked_log_text:
            items.append("If Discord routing filters are configured, a blocked human/non-bot Discord marker is proven absent from the AgentChatService log.")
        if not args.discord_channel_message_text:
            items.append("A real in-game or agent chat message is mirrored into Discord and verified in the channel.")
    else:
        items.append("If Discord is enabled for this deployment, bot auth/channel reachability and one in-game/agent/Discord round trip are proven with real ignored secrets.")
    return items


def proof_row(label, status, evidence):
    return "| {} | {} | {} |".format(label, status, evidence)


def proof_item(label, status, evidence):
    return {
        "requirement": label,
        "status": status,
        "evidence": evidence,
    }


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


def live_arg_status(args, requested):
    if requested and not args.live:
        return "INVALID_WITHOUT_LIVE"
    return "REQUESTED" if requested else "MISSING"


def proof_coverage_items(args):
    discord_enabled = discord_enabled_in_config(args)
    blocked_routing_status = "ABSENCE_PROOF_REQUESTED" if args.agent_chat_blocked_log_text else (
        "MISSING_REQUIRED_FOR_CONFIGURED_FILTERS" if blocked_routing_proof_required(args) else "CONDITIONAL"
    )
    return [
        proof_item(
            "Static config/package/server-template verification",
            "REQUESTED",
            "preflight, account audit, and deployment verifier commands",
        ),
        proof_item(
            "Public reachability and bridge non-exposure",
            "REQUESTED" if args.live else "MISSING",
            "`--live`" if args.live else "rerun with `--live` after the target runtime is intentionally running",
        ),
        proof_item(
            "External PBKDF2 game-protocol login",
            live_arg_status(args, bool(args.live_login_username)),
            "`--live-login-username` with `--live`" if args.live_login_username and args.live
            else "`--live-login-username` requires `--live`" if args.live_login_username
            else "rerun with `--live --live-login-username` and `--live-login-password-env`",
        ),
        proof_item(
            "Concurrent external plus same-host local protocol login",
            "REQUESTED" if args.live and args.live_login_username and args.live_local_login_username
            else "INVALID_WITHOUT_LIVE" if args.live_local_login_username and not args.live
            else "INVALID_WITHOUT_EXTERNAL_LOGIN" if args.live_local_login_username and not args.live_login_username
            else "MISSING",
            "`--live-local-login-username` with `--live-login-username`" if args.live and args.live_login_username and args.live_local_login_username
            else "`--live-local-login-username` requires `--live`" if args.live_local_login_username and not args.live
            else "`--live-local-login-username` requires `--live-login-username`" if args.live_local_login_username
            else "rerun with `--live --live-login-username`, `--live-local-login-username`, and password env flags",
        ),
        proof_item(
            "Discord bot auth and channel reachability",
            "REQUESTED" if args.live_discord else (
                "MISSING_REQUIRED_WHEN_ENABLED" if discord_enabled else "CONDITIONAL"
            ),
            "`--live-discord`" if args.live_discord else "required when `agent_chat_discord_enabled=true` with real ignored secrets",
        ),
        proof_item(
            "Desktop client coexistence",
            "MANUAL_PROOF_RECORDED" if args.desktop_client_proof_file else "MANUAL",
            "`--desktop-client-proof-file`" if args.desktop_client_proof_file else "connect one same-host Java client and one external Java client concurrently over the selected transport",
        ),
        proof_item(
            "Runtime data backup before remote replacement/restart",
            "MANUAL_PROOF_RECORDED" if args.runtime_data_backup_proof_file else "MANUAL",
            "`--runtime-data-backup-proof-file`" if args.runtime_data_backup_proof_file else "back up `data/characters`, `data/accounts`, and `data/secrets.json` before replacing runtime files or restarting into new deployment bits",
        ),
        proof_item(
            "Fail-closed login cases",
            "REQUESTED" if args.live and args.live_reject_login_username and args.live_reject_login_expected_statuses
            else "PINNED_STATUS_MISSING" if args.live and args.live_reject_login_username
            else live_arg_status(args, bool(args.live_reject_login_username)),
            "`--live-reject-login-username` with `--live-reject-login-expected-statuses`" if args.live and args.live_reject_login_username and args.live_reject_login_expected_statuses
            else "`--live-reject-login-expected-statuses 3,4` is required for final readiness" if args.live and args.live_reject_login_username
            else "`--live-reject-login-username` requires `--live`" if args.live_reject_login_username
            else "rerun with `--live --live-reject-login-username`, `--live-reject-login-password-env`, and `--live-reject-login-expected-statuses 3,4`; use `scripts/probe-game-login.py --expect-failure --expect-statuses 3,4` for focused rejection-class probes",
        ),
        proof_item(
            "Discord-to-server chat ingestion",
            "LOG_PROOF_REQUESTED" if args.agent_chat_log_text else (
                "MISSING_REQUIRED_WHEN_ENABLED" if discord_enabled else "MANUAL_WHEN_DISCORD_ENABLED"
            ),
            "`--agent-chat-log-text` with `--agent-chat-log-from-type discord --agent-chat-log-from-bot false`" if args.agent_chat_log_text else "send one real human/non-bot Discord message with a unique marker, then verify the AgentChatService log",
        ),
        proof_item(
            "Agent-to-player chat delivery",
            "DELIVERY_LOG_PROOF_REQUESTED" if args.agent_chat_delivery_log_text else "MISSING",
            "`--agent-chat-delivery-log-text` with `--agent-chat-delivery-log-to-name`" if args.agent_chat_delivery_log_text else "send one structured agent/player chat marker to a player, then verify the `agent_chat_player_delivery` audit event",
        ),
        proof_item(
            "Blocked Discord routing filters",
            blocked_routing_status,
            "`--agent-chat-blocked-log-text` with `--expect-absent`" if args.agent_chat_blocked_log_text else "when Discord allow-lists are configured, send one blocked human/non-bot marker and prove it is absent from AgentChatService logs",
        ),
        proof_item(
            "Server-to-Discord chat mirroring",
            "DISCORD_MESSAGE_PROOF_REQUESTED" if args.discord_channel_message_text else (
                "MISSING_REQUIRED_WHEN_ENABLED" if discord_enabled else "MANUAL_WHEN_DISCORD_ENABLED"
            ),
            "`--discord-channel-message-text` with configured bot-author verification" if args.discord_channel_message_text else "send one real in-game or agent message with a unique marker, then verify it appears in Discord",
        ),
    ]


def proof_coverage_rows(args):
    return [
        proof_row(item["requirement"], item["status"], item["evidence"])
        for item in proof_coverage_items(args)
    ]


def git_revision():
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return (completed.stdout or "").strip() or "unknown"


def report_inputs(args, archive):
    return {
        "config": display_path(args.config),
        "clientDist": display_path(args.client_dist),
        "archive": display_path(archive),
        "serverDeploymentDir": display_path(args.server_deployment_dir) if args.server_deployment_dir else "",
        "clientTlsTunnelDir": display_path(args.client_tls_tunnel_dir) if args.client_tls_tunnel_dir else "",
        "accountsDir": display_path(args.accounts_dir),
        "secrets": display_path(args.secrets),
    }


def serialize_check(check):
    return {
        "label": check["label"],
        "status": check["status"],
        "exitCode": check["exitCode"],
        "command": format_command(check["argv"]),
        "started": iso_z(check["started"]),
        "finished": iso_z(check["finished"]),
        "output": check["output"] or "",
    }


def write_json_report(args, checks, skipped_account_audit, markdown_output_path,
        all_passed, proof_status, generated_at):
    if not args.json_output:
        return None
    archive = Path(args.archive) if args.archive else Path(args.client_dist).with_suffix(".zip")
    output_path = Path(args.json_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "repo": str(ROOT_DIR),
        "gitRevision": git_revision(),
        "status": "PASS" if all_passed else "FAIL",
        "deploymentProofStatus": proof_status,
        "liveChecksRequested": bool(args.live),
        "liveDiscordRequested": bool(args.live_discord),
        "inputs": report_inputs(args, archive),
        "commandSummary": [
            {
                "label": check["label"],
                "status": check["status"],
                "exitCode": check["exitCode"],
            }
            for check in checks
        ],
        "proofCoverage": proof_coverage_items(args),
        "remainingLiveProof": remaining_live_proof_items(args),
        "checks": [serialize_check(check) for check in checks],
        "skippedAccountAudit": bool(skipped_account_audit),
        "markdownReport": str(markdown_output_path),
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def write_report(args, checks, skipped_account_audit):
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = iso_z(utc_now())
    archive = Path(args.archive) if args.archive else Path(args.client_dist).with_suffix(".zip")
    all_passed = all(check["exitCode"] == 0 for check in checks)
    proof_status = deployment_proof_status(args, all_passed)
    revision = git_revision()

    lines = [
        "# 2006Scape Deployment Readiness Report",
        "",
        "- generatedAt: `{}`".format(generated_at),
        "- repo: `{}`".format(ROOT_DIR),
        "- gitRevision: `{}`".format(revision),
        "- status: `{}`".format("PASS" if all_passed else "FAIL"),
        "- deploymentProofStatus: `{}`".format(proof_status),
        "- liveChecksRequested: `{}`".format("yes" if args.live else "no"),
        "- liveDiscordRequested: `{}`".format("yes" if args.live_discord else "no"),
        "",
        "## Inputs",
        "",
        "- config: `{}`".format(display_path(args.config)),
        "- clientDist: `{}`".format(display_path(args.client_dist)),
        "- archive: `{}`".format(display_path(archive)),
        "- serverDeploymentDir: `{}`".format(display_path(args.server_deployment_dir) if args.server_deployment_dir else "(not supplied)"),
        "- clientTlsTunnelDir: `{}`".format(display_path(args.client_tls_tunnel_dir) if args.client_tls_tunnel_dir else "(not supplied)"),
        "- accountsDir: `{}`".format(display_path(args.accounts_dir)),
        "- secrets: `{}`".format(display_path(args.secrets)),
        "",
        "## Command Summary",
        "",
        "| Check | Status | Exit |",
        "| --- | --- | --- |",
    ]
    for check in checks:
        lines.append("| {} | {} | {} |".format(check["label"], check["status"], check["exitCode"]))
    if skipped_account_audit:
        lines.append("| account audit | SKIP | allow-empty-accounts and accounts directory is missing |")

    lines.extend([
        "",
        "## Proof Coverage",
        "",
        "| Requirement | Status | Evidence / Next Step |",
        "| --- | --- | --- |",
    ])
    lines.extend(proof_coverage_rows(args))

    lines.extend([
        "",
        "## Command Output",
        "",
    ])
    for check in checks:
        lines.extend([
            "### {}".format(check["label"]),
            "",
            "- command: `{}`".format(format_command(check["argv"])),
            "- started: `{}`".format(iso_z(check["started"])),
            "- finished: `{}`".format(iso_z(check["finished"])),
            "- status: `{}`".format(check["status"]),
            "",
            "```text",
            check["output"] or "(no output)",
            "```",
            "",
        ])

    remaining_items = remaining_live_proof_items(args)
    lines.extend([
        "## Remaining Live Proof",
        "",
        "This report separates command success from deployment proof. `status: PASS` means the requested checks passed; `deploymentProofStatus` says whether the evidence is still static, partial, or fully recorded for the requested deployment proof set.",
        "",
    ])
    if remaining_items:
        lines.append("Before a real external deployment is called ready, still prove:")
        lines.append("")
        for item in remaining_items:
            lines.append("- {}".format(item))
    else:
        lines.append("No missing proof categories were detected for the requested live/manual proof set.")
    lines.extend([
        "",
        "## Result",
        "",
    ])
    if all_passed:
        if remaining_items:
            lines.append("All requested readiness checks passed, but the remaining proof items above still need evidence before the deployment is called ready.")
        else:
            lines.append("All requested readiness checks passed and the requested live/manual proof categories were recorded.")
    else:
        lines.append("One or more readiness checks failed. Fix the failing command output above before distributing a client or restarting a remote server.")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path, all_passed, proof_status, generated_at


def build_verify_args(args):
    argv = [
        "scripts/verify-external-deployment.py",
        "--config",
        args.config,
        "--client-dist",
        args.client_dist,
        "--accounts-dir",
        args.accounts_dir,
        "--secrets",
        args.secrets,
    ]
    if args.archive:
        argv.extend(["--archive", args.archive])
    if args.server_deployment_dir:
        argv.extend(["--server-deployment-dir", args.server_deployment_dir])
    if args.client_tls_tunnel_dir:
        argv.extend(["--client-tls-tunnel-dir", args.client_tls_tunnel_dir])
    if args.allow_empty_accounts:
        argv.append("--allow-empty-accounts")
    if args.allow_wildcard_bind:
        argv.append("--allow-wildcard-bind")
    if args.allow_placeholder_network_config:
        argv.append("--allow-placeholder-network-config")
    if args.allow_placeholder_discord_secrets:
        argv.append("--allow-placeholder-discord-secrets")
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
    return argv


def build_agent_chat_log_args(args):
    argv = [
        "scripts/verify-agent-chat-log.py",
        "--log-root",
        args.agent_chat_log_root,
        "--text-contains",
        args.agent_chat_log_text,
    ]
    if args.agent_chat_log_from_type:
        argv.extend(["--from-type", args.agent_chat_log_from_type])
    if args.agent_chat_log_from_name:
        argv.extend(["--from-name", args.agent_chat_log_from_name])
    if args.agent_chat_log_from_profile:
        argv.extend(["--from-profile", args.agent_chat_log_from_profile])
    if args.agent_chat_log_from_bot:
        argv.extend(["--from-bot", args.agent_chat_log_from_bot])
    if args.agent_chat_log_discord_message_id:
        argv.extend(["--discord-message-id", args.agent_chat_log_discord_message_id])
    if args.agent_chat_log_to_type:
        argv.extend(["--to-type", args.agent_chat_log_to_type])
    if args.agent_chat_log_to_name:
        argv.extend(["--to-name", args.agent_chat_log_to_name])
    if args.agent_chat_log_channel:
        argv.extend(["--channel", args.agent_chat_log_channel])
    if args.agent_chat_log_since_seconds:
        argv.extend(["--since-seconds", str(args.agent_chat_log_since_seconds)])
    if args.agent_chat_log_since_id:
        argv.extend(["--since-id", str(args.agent_chat_log_since_id)])
    return argv


def build_agent_chat_blocked_log_args(args):
    argv = [
        "scripts/verify-agent-chat-log.py",
        "--log-root",
        args.agent_chat_blocked_log_root or args.agent_chat_log_root,
        "--text-contains",
        args.agent_chat_blocked_log_text,
        "--from-type",
        "discord",
        "--from-bot",
        "false",
        "--expect-absent",
    ]
    if args.agent_chat_blocked_log_channel:
        argv.extend(["--channel", args.agent_chat_blocked_log_channel])
    if args.agent_chat_blocked_log_since_seconds:
        argv.extend(["--since-seconds", str(args.agent_chat_blocked_log_since_seconds)])
    if args.agent_chat_blocked_log_since_id:
        argv.extend(["--since-id", str(args.agent_chat_blocked_log_since_id)])
    return argv


def build_agent_chat_delivery_log_args(args):
    argv = [
        "scripts/verify-agent-chat-log.py",
        "--log-root",
        args.agent_chat_delivery_log_root or args.agent_chat_log_root,
        "--event",
        "agent_chat_player_delivery",
        "--text-contains",
        args.agent_chat_delivery_log_text,
        "--to-type",
        "player",
        "--to-name",
        args.agent_chat_delivery_log_to_name,
        "--delivered-to",
        args.agent_chat_delivery_log_to_name,
        "--no-undelivered",
    ]
    if args.agent_chat_delivery_log_channel:
        argv.extend(["--channel", args.agent_chat_delivery_log_channel])
    if args.agent_chat_delivery_log_since_seconds:
        argv.extend(["--since-seconds", str(args.agent_chat_delivery_log_since_seconds)])
    if args.agent_chat_delivery_log_since_id:
        argv.extend(["--since-id", str(args.agent_chat_delivery_log_since_id)])
    return argv


def build_discord_channel_message_args(args):
    argv = [
        "scripts/verify-discord-channel-message.py",
        "--secrets",
        args.secrets,
        "--text-contains",
        args.discord_channel_message_text,
        "--limit",
        str(args.discord_channel_message_limit),
    ]
    for agent in args.discord_channel_message_agent:
        argv.extend(["--agent", agent])
    if args.discord_channel_message_after_id:
        argv.extend(["--after-id", args.discord_channel_message_after_id])
    if args.discord_channel_message_allow_human_author:
        argv.append("--allow-human-author")
    if args.discord_channel_message_require_all:
        argv.append("--require-all")
    return argv


def main():
    parser = argparse.ArgumentParser(description="Write a redacted external-deployment readiness report.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--client-dist", default=str(DEFAULT_CLIENT_DIST))
    parser.add_argument("--archive", default="")
    parser.add_argument("--server-deployment-dir", default="")
    parser.add_argument("--client-tls-tunnel-dir", default="",
            help="Optional operator-side client_tls_tunnel stunnel template directory.")
    parser.add_argument("--proof-manifest", default="",
            help=("Optional JSON file containing live/manual proof arguments. "
                  "CLI flags override manifest fields. Store password env var names, not passwords."))
    parser.add_argument("--accounts-dir", default=str(DEFAULT_ACCOUNTS_DIR))
    parser.add_argument("--secrets", default=str(DEFAULT_SECRETS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json-output", default="",
            help="Optional machine-readable JSON readiness report path. Markdown output is still written to --output.")
    parser.add_argument("--allow-empty-accounts", action="store_true")
    parser.add_argument("--allow-wildcard-bind", action="store_true")
    parser.add_argument("--allow-placeholder-network-config", action="store_true")
    parser.add_argument("--allow-placeholder-discord-secrets", action="store_true")
    parser.add_argument("--require-full-proof", action="store_true",
            help=("Exit non-zero unless deploymentProofStatus is a full live proof status. "
                  "Use for final deployment gates, not partial evidence reports."))
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--tls-sni-host", default="")
    parser.add_argument("--allow-untrusted-client-tls", action="store_true")
    parser.add_argument("--live-login-username", default="")
    parser.add_argument("--live-login-password-env", default="")
    parser.add_argument("--live-login-hold-seconds", type=float, default=0.0)
    parser.add_argument("--live-local-login-username", default="")
    parser.add_argument("--live-local-login-password-env", default="")
    parser.add_argument("--live-local-host", default="127.0.0.1",
            help="Loopback host for same-host local login proof. Defaults to 127.0.0.1.")
    parser.add_argument("--live-local-port", type=int, default=0)
    parser.add_argument("--live-reject-login-username", default="")
    parser.add_argument("--live-reject-login-password-env", default="")
    parser.add_argument("--live-reject-login-expected-statuses", default="")
    parser.add_argument("--live-discord", action="store_true")
    parser.add_argument("--agent-chat-log-root", default=str(DEFAULT_AGENT_CHAT_LOG_ROOT))
    parser.add_argument("--agent-chat-log-text", default="",
            help="Optional marker text to verify in AgentChatService JSONL logs after a real chat/Discord proof message.")
    parser.add_argument("--agent-chat-log-from-type", default="")
    parser.add_argument("--agent-chat-log-from-name", default="")
    parser.add_argument("--agent-chat-log-from-profile", default="")
    parser.add_argument("--agent-chat-log-from-bot", choices=("true", "false"), default="",
            help="Require logged fromBot metadata for AgentChatService log proof.")
    parser.add_argument("--agent-chat-log-discord-message-id", default="",
            help="Require a specific Discord message id in the AgentChatService log proof.")
    parser.add_argument("--agent-chat-log-to-type", default="")
    parser.add_argument("--agent-chat-log-to-name", default="")
    parser.add_argument("--agent-chat-log-channel", default="")
    parser.add_argument("--agent-chat-log-since-seconds", type=float, default=0.0)
    parser.add_argument("--agent-chat-log-since-id", type=int, default=0)
    parser.add_argument("--agent-chat-blocked-log-root", default="",
            help="Optional AgentChatService log root for blocked Discord routing proof; defaults to --agent-chat-log-root.")
    parser.add_argument("--agent-chat-blocked-log-text", default="",
            help="Marker text that must be absent from AgentChatService logs after a blocked Discord routing test.")
    parser.add_argument("--agent-chat-blocked-log-channel", default="")
    parser.add_argument("--agent-chat-blocked-log-since-seconds", type=float, default=0.0)
    parser.add_argument("--agent-chat-blocked-log-since-id", type=int, default=0)
    parser.add_argument("--agent-chat-delivery-log-root", default="",
            help="Optional AgentChatService log root for direct player delivery proof; defaults to --agent-chat-log-root.")
    parser.add_argument("--agent-chat-delivery-log-text", default="",
            help="Marker text that must appear in an agent_chat_player_delivery audit event.")
    parser.add_argument("--agent-chat-delivery-log-to-name", default="",
            help="Player name that must appear in toName and deliveredTo for direct player delivery proof.")
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
    parser.add_argument("--discord-channel-message-text", default="",
            help="Optional marker text to verify in recent Discord channel messages after server-to-Discord mirroring.")
    parser.add_argument("--discord-channel-message-agent", action="append", default=[],
            help="Only check this configured Discord bot agent/profile. May be passed more than once.")
    parser.add_argument("--discord-channel-message-limit", type=int, default=50)
    parser.add_argument("--discord-channel-message-after-id", default="")
    parser.add_argument("--discord-channel-message-allow-human-author", action="store_true")
    parser.add_argument("--discord-channel-message-require-all", action="store_true")
    parser.add_argument("--command-timeout", type=float, default=120.0)
    args = parser.parse_args()
    apply_proof_manifest(parser, args, sys.argv[1:])
    validate_chat_proof_args(parser, args)
    validate_require_full_proof_args(parser, args)

    checks = []
    preflight = ["scripts/preflight-external-config.py", args.config]
    if args.allow_wildcard_bind:
        preflight.append("--allow-wildcard-bind")
    checks.append(run_command("config preflight", preflight, args.command_timeout))

    skipped_account_audit = False
    accounts_dir = Path(args.accounts_dir)
    if args.allow_empty_accounts and not accounts_dir.exists():
        skipped_account_audit = True
    else:
        checks.append(run_command(
            "account audit",
            ["scripts/account-admin.py", "--accounts-dir", args.accounts_dir,
                "--require-password-policy", "audit"],
            args.command_timeout,
        ))

    if args.agent_chat_log_text:
        checks.append(run_command(
            "agent chat log proof",
            build_agent_chat_log_args(args),
            args.command_timeout,
        ))

    if args.agent_chat_blocked_log_text:
        checks.append(run_command(
            "blocked Discord routing proof",
            build_agent_chat_blocked_log_args(args),
            args.command_timeout,
        ))

    if args.agent_chat_delivery_log_text:
        checks.append(run_command(
            "agent chat player delivery proof",
            build_agent_chat_delivery_log_args(args),
            args.command_timeout,
        ))

    if args.desktop_client_proof_file:
        checks.append(run_desktop_client_proof_file_check(args.desktop_client_proof_file))

    if args.runtime_data_backup_proof_file:
        checks.append(run_runtime_data_backup_proof_file_check(args.runtime_data_backup_proof_file))

    if args.discord_channel_message_text:
        checks.append(run_command(
            "discord channel mirror proof",
            build_discord_channel_message_args(args),
            args.command_timeout,
        ))

    checks.append(run_command("deployment verification", build_verify_args(args), args.command_timeout))
    output_path, all_passed, proof_status, generated_at = write_report(args, checks, skipped_account_audit)
    json_output_path = write_json_report(
        args,
        checks,
        skipped_account_audit,
        output_path,
        all_passed,
        proof_status,
        generated_at,
    )
    print("report: {}".format(output_path))
    if json_output_path is not None:
        print("jsonReport: {}".format(json_output_path))
    if not all_passed:
        return 1
    if args.require_full_proof and proof_status not in FULL_PROOF_STATUSES:
        print(
            "full proof required but deploymentProofStatus is {}".format(proof_status),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
