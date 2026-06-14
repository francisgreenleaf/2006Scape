#!/usr/bin/env python3
"""Summarize an existing external-deployment readiness JSON report."""

import argparse
import json
import shlex
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_READINESS_JSON = ROOT_DIR / "dist" / "deployment-readiness-report.json"
PREPARED_READINESS_JSON = "deployment-readiness-report.json"

FULL_PROOF_STATUSES = {
    "LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_PROOF_RECORDED_DISCORD_NOT_REQUESTED",
    "FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED",
}
FULL_DISCORD_PROOF_STATUS = "FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED"


def fail(message, code=1):
    print("error: {}".format(message), file=sys.stderr)
    raise SystemExit(code)


def resolve_readiness_json(args):
    if args.readiness_json:
        return Path(args.readiness_json)
    if args.prepared_dir:
        return Path(args.prepared_dir) / PREPARED_READINESS_JSON
    return DEFAULT_READINESS_JSON


def load_report(path):
    if path.is_symlink():
        fail("readiness JSON must not be a symlink: {}".format(path))
    if not path.is_file():
        fail("readiness JSON is missing: {}".format(path))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("readiness JSON is invalid: {}: {}".format(path, exc))
    if not isinstance(data, dict):
        fail("readiness JSON must contain an object: {}".format(path))
    return data


def externally_ready(data, require_discord=False):
    if data.get("status") != "PASS":
        return False
    proof_status = data.get("deploymentProofStatus")
    if require_discord:
        return proof_status == FULL_DISCORD_PROOF_STATUS
    return proof_status in FULL_PROOF_STATUSES


def shell_join(argv):
    return " ".join(shlex.quote(str(part)) for part in argv if str(part))


def report_input(data, name, default):
    inputs = data.get("inputs", {})
    if not isinstance(inputs, dict):
        return default
    value = inputs.get(name)
    if isinstance(value, str) and value.strip():
        return value
    return default


def coverage_status(data, requirement):
    coverage = data.get("proofCoverage", [])
    if not isinstance(coverage, list):
        return ""
    for item in coverage:
        if isinstance(item, dict) and item.get("requirement") == requirement:
            return str(item.get("status") or "")
    return ""


def command_entry(label, why, command):
    return {
        "label": label,
        "why": why,
        "command": command,
    }


def readiness_base_args(data, readiness_json_path):
    config = report_input(data, "config", "2006Scape Server/ServerConfig.json")
    client_dist = report_input(data, "clientDist", "dist/2006scape-client")
    archive = report_input(data, "archive", "")
    server_dir = report_input(data, "serverDeploymentDir", "")
    tls_dir = report_input(data, "clientTlsTunnelDir", "")
    accounts_dir = report_input(data, "accountsDir", "")
    secrets = report_input(data, "secrets", "")
    argv = [
        "scripts/deployment-readiness-report.py",
        "--config", config,
        "--client-dist", client_dist,
    ]
    if archive:
        argv.extend(["--archive", archive])
    if server_dir:
        argv.extend(["--server-deployment-dir", server_dir])
    if tls_dir:
        argv.extend(["--client-tls-tunnel-dir", tls_dir])
    if accounts_dir:
        argv.extend(["--accounts-dir", accounts_dir])
    if secrets:
        argv.extend(["--secrets", secrets])
    argv.extend(["--json-output", str(readiness_json_path)])
    return argv


def manifest_path_for(readiness_json_path):
    path = Path(readiness_json_path)
    if path.name == PREPARED_READINESS_JSON:
        return str(path.parent / "deployment-proof-manifest.json")
    return "dist/external-deployment/deployment-proof-manifest.json"


def proof_note_path_for(readiness_json_path, filename):
    return str(Path(manifest_path_for(readiness_json_path)).parent / filename)


def copy_manifest_template_command(template, manifest):
    commands = []
    manifest_parent = Path(manifest).parent
    if str(manifest_parent) not in ("", "."):
        commands.append(shell_join(["mkdir", "-p", str(manifest_parent)]))
    commands.append("{} || {}".format(
        shell_join(["test", "-f", manifest]),
        shell_join(["cp", template, manifest]),
    ))
    return "\n".join(commands)


def command_with_manifest(template, manifest, argv):
    return "{}\n{}".format(
        copy_manifest_template_command(template, manifest),
        shell_join(argv),
    )


def build_next_commands(data, readiness_json_path, require_discord=False):
    if externally_ready(data, require_discord):
        return []

    config = report_input(data, "config", "2006Scape Server/ServerConfig.json")
    server_dir = report_input(data, "serverDeploymentDir", "dist/server-deployment")
    secrets = report_input(data, "secrets", "2006Scape Server/data/secrets.json")
    base = readiness_base_args(data, readiness_json_path)
    manifest = manifest_path_for(readiness_json_path)
    template = "{}/proof-templates/deployment-proof-manifest.json".format(server_dir.rstrip("/"))
    commands = []

    live_status = coverage_status(data, "Public reachability and bridge non-exposure")
    external_login_status = coverage_status(data, "External PBKDF2 game-protocol login")
    concurrent_status = coverage_status(data, "Concurrent external plus same-host local protocol login")
    rejection_status = coverage_status(data, "Fail-closed login cases")
    if live_status != "REQUESTED":
        commands.append(command_entry(
            "Preview public network path",
            "Checks public game/cache reachability plus agent-bridge non-exposure without logging in.",
            shell_join(["scripts/probe-deployment-network.py", "--config", config]),
        ))
    if (live_status != "REQUESTED"
            or external_login_status != "REQUESTED"
            or concurrent_status != "REQUESTED"
            or rejection_status != "REQUESTED"):
        live_args = list(base)
        live_args.extend([
            "--live",
            "--live-login-username", "EXTERNAL_TEST",
            "--live-login-password-env", "EXTERNAL_PASSWORD",
            "--live-local-login-username", "LOCAL_TEST",
            "--live-local-login-password-env", "LOCAL_PASSWORD",
            "--live-reject-login-username", "REJECT_TEST",
            "--live-reject-login-password-env", "REJECT_PASSWORD",
            "--live-reject-login-expected-statuses", "3,4",
            "--update-proof-manifest", manifest,
        ])
        commands.append(command_entry(
            "Record live network/auth proof",
            "Run after the remote server is intentionally running; password values stay in environment variables.",
            "{}\nEXTERNAL_PASSWORD='...' LOCAL_PASSWORD='...' REJECT_PASSWORD='...' {}".format(
                copy_manifest_template_command(template, manifest),
                shell_join(live_args),
            ),
        ))

    if coverage_status(data, "Runtime data backup before remote replacement/restart") != "MANUAL_PROOF_RECORDED":
        commands.append(command_entry(
            "Back up deployed runtime data",
            "Run on the deployed host before replacing files or restarting into new bits; updates the copied proof manifest when present.",
            "{}\n{}".format(
                copy_manifest_template_command(template, manifest),
                shell_join([
                    "scripts/backup-runtime-data.py",
                    "--data-dir", "2006Scape Server/data",
                    "--proof-file", proof_note_path_for(readiness_json_path, "runtime-data-backup-proof.md"),
                    "--proof-manifest", manifest,
                ]),
            ),
        ))

    if coverage_status(data, "Desktop client coexistence") != "MANUAL_PROOF_RECORDED":
        commands.append(command_entry(
            "Write desktop-client coexistence proof",
            "Run after one same-host Java client and one external Java client are online together.",
            command_with_manifest(template, manifest, [
                "scripts/write-desktop-client-proof.py",
                "--config", config,
                "--same-host-client", "LOCAL_PLAYER",
                "--external-client", "EXTERNAL_PLAYER",
                "--transport", "TRANSPORT",
                "--public-host", "PUBLIC_HOST",
                "--evidence", "PATH_TO_SCREENSHOT_OR_LOG",
                "--output", proof_note_path_for(readiness_json_path, "desktop-client-proof.md"),
                "--proof-manifest", manifest,
            ]),
        ))

    if coverage_status(data, "Agent-to-player chat delivery") != "DELIVERY_LOG_PROOF_REQUESTED":
        commands.append(command_entry(
            "Verify direct agent/player chat delivery",
            "Run after sending one unique structured marker to an online player; updates the copied proof manifest.",
            command_with_manifest(template, manifest, [
                "scripts/verify-agent-chat-log.py",
                "--event", "agent_chat_player_delivery",
                "--text-contains", "CHAT_MARKER",
                "--to-type", "player",
                "--to-name", "PLAYER",
                "--delivered-to", "PLAYER",
                "--no-undelivered",
                "--channel", "agent",
                "--proof-manifest", manifest,
            ]),
        ))

    discord_statuses = [
        coverage_status(data, "Discord bot auth and channel reachability"),
        coverage_status(data, "Discord-to-server chat ingestion"),
        coverage_status(data, "Blocked Discord routing filters"),
        coverage_status(data, "Server-to-Discord chat mirroring"),
    ]
    discord_needed = require_discord or any(status.startswith("MISSING_REQUIRED") for status in discord_statuses)
    if discord_needed and coverage_status(data, "Discord bot auth and channel reachability") != "REQUESTED":
        commands.append(command_entry(
            "Verify Discord bot/channel reachability",
            "Run with the real ignored secrets file; this does not post messages by default.",
            shell_join(["scripts/probe-discord-agent-bots.py", "--secrets", secrets]),
        ))
    if discord_needed and coverage_status(data, "Discord-to-server chat ingestion") != "LOG_PROOF_REQUESTED":
        commands.append(command_entry(
            "Verify Discord-to-server chat ingestion",
            "Run after a real human/non-bot Discord message with a unique marker; updates the copied proof manifest.",
            command_with_manifest(template, manifest, [
                "scripts/verify-agent-chat-log.py",
                "--text-contains", "DISCORD_TO_SERVER_MARKER",
                "--from-type", "discord",
                "--from-bot", "false",
                "--channel", "agent",
                "--proof-manifest", manifest,
            ]),
        ))
    if discord_needed and coverage_status(data, "Blocked Discord routing filters") == "MISSING_REQUIRED_FOR_CONFIGURED_FILTERS":
        commands.append(command_entry(
            "Verify blocked Discord routing absence",
            "Run after sending a blocked human/non-bot Discord marker; updates the copied proof manifest.",
            command_with_manifest(template, manifest, [
                "scripts/verify-agent-chat-log.py",
                "--text-contains", "BLOCKED_MARKER",
                "--from-type", "discord",
                "--from-bot", "false",
                "--channel", "agent",
                "--expect-absent",
                "--proof-manifest", manifest,
            ]),
        ))
    if discord_needed and coverage_status(data, "Server-to-Discord chat mirroring") != "DISCORD_MESSAGE_PROOF_REQUESTED":
        commands.append(command_entry(
            "Verify server-to-Discord mirroring",
            "Run after sending one in-game or agent marker that should mirror to Discord; updates the copied proof manifest.",
            command_with_manifest(template, manifest, [
                "scripts/verify-discord-channel-message.py",
                "--text-contains", "SERVER_TO_DISCORD_MARKER",
                "--agent", "PROFILE",
                "--proof-manifest", manifest,
            ]),
        ))

    final_args = list(base)
    final_args.extend(["--proof-manifest", manifest, "--require-full-proof"])
    manifest_check_args = [
        "scripts/check-deployment-proof-manifest.py",
        manifest,
        "--config",
        config,
        "--require-full-proof",
        "--check-files",
    ]
    if secrets:
        manifest_check_args.extend(["--secrets", secrets])
    commands.append(command_entry(
        "Check final proof manifest and rerun final readiness",
        "Use after filling proof paths, usernames, markers, and password environment-variable names.",
        "{}\n{}\n{}".format(
            copy_manifest_template_command(template, manifest),
            shell_join(manifest_check_args),
            shell_join(final_args),
        ),
    ))
    return commands


def summarize(data, path, require_discord=False, include_next_commands=False):
    coverage = data.get("proofCoverage", [])
    if not isinstance(coverage, list):
        coverage = []
    remaining = data.get("remainingLiveProof", [])
    if not isinstance(remaining, list):
        remaining = []
    summary = {
        "readinessJson": str(path),
        "status": data.get("status"),
        "deploymentProofStatus": data.get("deploymentProofStatus"),
        "externallyReady": externally_ready(data, require_discord),
        "requireDiscord": bool(require_discord),
        "liveChecksRequested": data.get("liveChecksRequested"),
        "liveDiscordRequested": data.get("liveDiscordRequested"),
        "markdownReport": data.get("markdownReport"),
        "remainingLiveProofCount": len(remaining),
        "remainingLiveProof": remaining,
        "proofCoverage": coverage,
    }
    if include_next_commands:
        summary["nextCommands"] = build_next_commands(data, path, require_discord)
    return summary


def print_human(summary, show_covered=False):
    print("readinessJson: {}".format(summary["readinessJson"]))
    print("status: {}".format(summary.get("status")))
    print("deploymentProofStatus: {}".format(summary.get("deploymentProofStatus")))
    print("externallyReady: {}".format("yes" if summary["externallyReady"] else "no"))
    print("liveChecksRequested: {}".format("yes" if summary.get("liveChecksRequested") else "no"))
    print("liveDiscordRequested: {}".format("yes" if summary.get("liveDiscordRequested") else "no"))
    if summary.get("markdownReport"):
        print("markdownReport: {}".format(summary["markdownReport"]))
    remaining = summary.get("remainingLiveProof", [])
    print("remainingLiveProofCount: {}".format(len(remaining)))
    if remaining:
        print("remainingLiveProof:")
        for item in remaining:
            print("- {}".format(item))
    coverage = summary.get("proofCoverage", [])
    if coverage:
        print("proofCoverage:")
        for row in coverage:
            if not isinstance(row, dict):
                continue
            status = row.get("status", "")
            if not show_covered and status in ("RECORDED", "MANUAL_PROOF_RECORDED",
                    "DELIVERY_LOG_PROOF_REQUESTED", "LOG_PROOF_REQUESTED",
                    "ABSENCE_PROOF_REQUESTED"):
                continue
            requirement = row.get("requirement", "unknown")
            detail = row.get("detail", "")
            suffix = " ({})".format(detail) if detail else ""
            print("- {}: {}{}".format(requirement, status, suffix))
    next_commands = summary.get("nextCommands", [])
    if next_commands:
        print("nextCommands:")
        for item in next_commands:
            print("- {}: {}".format(item["label"], item["why"]))
            for line in item["command"].splitlines():
                print("  {}".format(line))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read an existing deployment-readiness-report JSON and summarize whether external readiness is actually proven."
    )
    parser.add_argument("--readiness-json",
            help="Path to deployment-readiness-report JSON. Defaults to dist/deployment-readiness-report.json unless --prepared-dir is supplied.")
    parser.add_argument("--prepared-dir",
            help="Prepared deployment directory containing deployment-readiness-report.json, usually dist/external-deployment.")
    parser.add_argument("--json", action="store_true",
            help="Print a machine-readable summary.")
    parser.add_argument("--show-covered", action="store_true",
            help="Include proof-coverage rows that are already recorded, not only missing/manual/final-gate rows.")
    parser.add_argument("--show-next-commands", action="store_true",
            help="Print read-only command templates for missing live/manual proof categories.")
    parser.add_argument("--require-discord", action="store_true",
            help="Treat Discord round-trip proof as required even when the readiness report says Discord proof was not requested.")
    parser.add_argument("--fail-if-not-ready", action="store_true",
            help="Exit 2 when status/deploymentProofStatus do not prove full external readiness.")
    args = parser.parse_args(argv)

    path = resolve_readiness_json(args)
    data = load_report(path)
    summary = summarize(data, path, args.require_discord, args.show_next_commands)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_human(summary, args.show_covered)
    if args.fail_if_not_ready and not summary["externallyReady"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
