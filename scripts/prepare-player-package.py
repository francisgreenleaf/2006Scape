#!/usr/bin/env python3
"""One-command external player account and package preparation."""

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT_DIR / "2006Scape Server" / "ServerConfig.json"
DEFAULT_PREPARED_DIR = ROOT_DIR / "dist" / "external-deployment"
DEFAULT_ACCOUNTS_DIR = ROOT_DIR / "2006Scape Server" / "data" / "accounts"
SAFE_FILE_RE = re.compile(r"[^a-z0-9._-]+")
SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9_]+")
MR_NAME_WORDS = (
    "Scout",
    "Gem",
    "Flame",
    "Fish",
    "Wood",
    "Athlete",
    "Smith",
    "Mine",
    "Coal",
    "Iron",
    "Copper",
    "Tin",
    "Rune",
    "Oak",
    "Willow",
    "Maple",
    "Yew",
    "Fletch",
    "Cook",
    "Chef",
    "Bank",
    "Quest",
    "Clue",
    "Trail",
    "Stone",
    "Anvil",
    "Arrow",
    "Bronze",
    "Steel",
    "Mith",
    "Range",
    "Prayer",
    "Agile",
    "Swift",
    "Torch",
    "Port",
    "Vale",
    "Cedar",
    "Moss",
    "Forge",
)


def fail(message):
    raise SystemExit(message)


def resolve_under_root(path):
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def safe_file_stem(value):
    clean = SAFE_STEM_RE.sub("_", value.strip()).strip("_").lower()
    return clean or "player"


def safe_account_file_name(username):
    normalized = username.strip().lower().replace(" ", "_")
    return SAFE_FILE_RE.sub("_", normalized) + ".json"


def account_artifacts_exist(prepared_dir, accounts_dir, username):
    stem = safe_file_stem(username)
    candidates = [
        accounts_dir / safe_account_file_name(username),
        prepared_dir / "private" / "player-credentials-{}.env".format(stem),
        prepared_dir / "player-handoff-{}.md".format(stem),
        prepared_dir / "player-kit-{}.zip".format(stem),
    ]
    return any(path.exists() for path in candidates)


def suggest_mr_name(prepared_dir, accounts_dir):
    base_candidates = ["Mr" + word for word in MR_NAME_WORDS if len("Mr" + word) <= 12]
    available = [
        name for name in base_candidates
        if not account_artifacts_exist(prepared_dir, accounts_dir, name)
    ]
    if available:
        return secrets.choice(available)
    for _ in range(200):
        word = secrets.choice(MR_NAME_WORDS)
        suffix = str(secrets.randbelow(90) + 10)
        name = ("Mr" + word)[:12 - len(suffix)] + suffix
        if not account_artifacts_exist(prepared_dir, accounts_dir, name):
            return name
    fail("could not find an unused Mr-style player name")


def reject_symlink(path, label):
    if path.is_symlink():
        fail("{} must not be a symlink: {}".format(label, path))


def prepared_bundle_exists(prepared_dir):
    required = [
        prepared_dir / "agent-scape-client" / "MANIFEST.txt",
        prepared_dir / "agent-scape-client" / "client.properties",
        prepared_dir / "agent-scape-client.zip",
        prepared_dir / "server-deployment" / "player-handoff-template.md",
    ]
    return all(path.is_file() and not path.is_symlink() for path in required)


def run_json(argv, label, env=None, verbose=False):
    completed = subprocess.run(
        argv,
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = completed.stdout or ""
    if completed.returncode != 0:
        fail("{} failed:\n{}".format(label, output.strip()))
    if verbose and output.strip():
        print(output.rstrip())
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        fail("{} did not return JSON: {}\n{}".format(label, exc, output.strip()))


def run_checked(argv, label, env=None, verbose=False):
    completed = subprocess.run(
        argv,
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = completed.stdout or ""
    if completed.returncode != 0:
        fail("{} failed:\n{}".format(label, output.strip()))
    if verbose and output.strip():
        print(output.rstrip())
    return output


def prepare_bundle(args, prepared_dir):
    if args.prepare_policy == "never":
        if not prepared_bundle_exists(prepared_dir):
            fail("prepared deployment bundle is missing and --prepare-policy never was set: {}".format(prepared_dir))
        return False
    if args.prepare_policy == "auto" and prepared_bundle_exists(prepared_dir):
        return False

    argv = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "prepare-external-deployment.py"),
        "--config",
        args.config,
        "--output-dir",
        str(prepared_dir),
        "--accounts-dir",
        args.accounts_dir,
    ]
    if args.skip_build:
        argv.append("--skip-build")
    if args.allow_empty_accounts:
        argv.append("--allow-empty-accounts")
    if args.allow_wildcard_bind:
        argv.append("--allow-wildcard-bind")
    if args.allow_placeholder_network_config:
        argv.append("--allow-placeholder-network-config")
    if args.allow_placeholder_discord_secrets:
        argv.append("--allow-placeholder-discord-secrets")
    if args.require_encrypted_external:
        argv.append("--require-encrypted-external")
    run_checked(argv, "external deployment prepare", verbose=args.verbose)
    return True


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Prepare an external deployment bundle when needed, provision one PBKDF2 player "
            "account, create the public-safe player kit, and optionally build a macOS app/DMG. "
            "Passwords are never printed and are written only to ignored private env files."
        )
    )
    parser.add_argument("username", nargs="?", help="Player account username.")
    parser.add_argument("--random-name", action="store_true",
            help="Choose an unused Mr-style username/character, inspired by existing test names.")
    parser.add_argument("--character", default="", help="Allowed/logged-in character. Defaults to username.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="External-player server config for bundle preparation.")
    parser.add_argument("--prepared-dir", default=str(DEFAULT_PREPARED_DIR), help="Prepared deployment output directory.")
    parser.add_argument("--accounts-dir", default=str(DEFAULT_ACCOUNTS_DIR), help="Ignored PBKDF2 account-record directory.")
    parser.add_argument("--prepare-policy", choices=("auto", "always", "never"), default="auto",
            help="auto prepares only when key bundle files are missing; always reruns prepare; never requires an existing bundle.")
    parser.add_argument("--skip-prepare", action="store_true", help="Alias for --prepare-policy never.")
    parser.add_argument("--skip-build", action="store_true", help="Pass --skip-build to prepare-external-deployment.py.")
    parser.add_argument("--allow-empty-accounts", action="store_true")
    parser.add_argument("--allow-wildcard-bind", action="store_true")
    parser.add_argument("--allow-placeholder-network-config", action="store_true")
    parser.add_argument("--allow-placeholder-discord-secrets", action="store_true")
    parser.add_argument("--require-encrypted-external", action="store_true")
    parser.add_argument("--agent-gateway-url", default="", help="Optional HTTPS /agent gateway URL for the handoff note.")
    parser.add_argument("--password-env", default="", help="Use an existing password from this environment variable.")
    parser.add_argument("--password-length", type=int, default=20, help="Generated password length; minimum enforced downstream.")
    parser.add_argument("--allow-weak-password", action="store_true", help="Local throwaway/source-validation accounts only.")
    parser.add_argument("--overwrite-account", action="store_true", help="Replace an existing account record.")
    parser.add_argument("--preserve-metadata", action="store_true", help="Preserve metadata when overwriting an account record.")
    parser.add_argument("--role", action="append", default=[], help="Optional account role. May be repeated.")
    parser.add_argument("--discord-user-id", default="", help="Optional Discord user id metadata.")
    parser.add_argument("--mac-app", action="store_true", help="Also build a macOS .app wrapper.")
    parser.add_argument("--mac-dmg", action="store_true", help="Also build a macOS .app wrapper and DMG with hdiutil.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary.")
    parser.add_argument("--verbose", action="store_true", help="Print child command output. Child scripts do not print passwords.")
    args = parser.parse_args()
    if args.skip_prepare:
        args.prepare_policy = "never"

    prepared_dir = resolve_under_root(Path(args.prepared_dir))
    accounts_dir = resolve_under_root(Path(args.accounts_dir))
    reject_symlink(prepared_dir, "prepared deployment directory")
    if accounts_dir.exists():
        reject_symlink(accounts_dir, "accounts directory")
    if args.random_name:
        if args.username:
            fail("--random-name cannot be combined with an explicit username")
        if args.character:
            fail("--random-name cannot be combined with --character; the generated character matches the username")
        args.username = suggest_mr_name(prepared_dir, accounts_dir)
        args.character = args.username
    elif not args.username:
        fail("username is required unless --random-name is set")

    prepared = prepare_bundle(args, prepared_dir)

    provision_argv = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "provision-player-account.py"),
        args.username,
        "--character",
        args.character or args.username,
        "--prepared-dir",
        str(prepared_dir),
        "--accounts-dir",
        str(accounts_dir),
        "--password-length",
        str(args.password_length),
        "--json",
    ]
    if args.password_env:
        provision_argv.extend(["--password-env", args.password_env])
    if args.agent_gateway_url:
        provision_argv.extend(["--agent-gateway-url", args.agent_gateway_url])
    if args.allow_weak_password:
        provision_argv.append("--allow-weak-password")
    if args.overwrite_account:
        provision_argv.append("--overwrite")
    if args.preserve_metadata:
        provision_argv.append("--preserve-metadata")
    for role in args.role:
        provision_argv.extend(["--role", role])
    if args.discord_user_id:
        provision_argv.extend(["--discord-user-id", args.discord_user_id])
    provision = run_json(provision_argv, "player account provision", verbose=args.verbose)

    kit_argv = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "package-player-kit.py"),
        args.username,
        "--character",
        args.character or args.username,
        "--prepared-dir",
        str(prepared_dir),
        "--handoff-note",
        provision["handoffNote"],
        "--json",
    ]
    if args.agent_gateway_url:
        kit_argv.extend(["--agent-gateway-url", args.agent_gateway_url])
    kit = run_json(kit_argv, "player kit package", verbose=args.verbose)

    mac_package = {}
    if args.mac_app or args.mac_dmg:
        mac_argv = [
            sys.executable,
            str(ROOT_DIR / "scripts" / "package-macos-player-app.py"),
            args.username,
            "--character",
            args.character or args.username,
            "--prepared-dir",
            str(prepared_dir),
            "--handoff-note",
            provision["handoffNote"],
            "--json",
        ]
        if args.mac_dmg:
            mac_argv.append("--dmg")
        mac_package = run_json(mac_argv, "macOS player app package", verbose=args.verbose)

    result = {
        "success": True,
        "username": provision["username"],
        "character": provision["character"],
        "nameGenerated": bool(args.random_name),
        "preparedDir": str(prepared_dir),
        "preparedBundleCreated": prepared,
        "playerKit": kit["playerKit"],
        "playerKitSha256": kit["playerKitSha256"],
        "privateCredentials": provision["privateCredentials"],
        "accountRecord": str(accounts_dir / safe_account_file_name(provision["username"])),
        "handoffNote": provision["handoffNote"],
        "macApp": mac_package.get("appBundle", ""),
        "macDmg": mac_package.get("dmg", ""),
        "macDmgSha256": mac_package.get("dmgSha256", ""),
        "passwordPrinted": False,
        "runtimeTouched": False,
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("ok: prepared player package for {}".format(result["username"]))
        print("player kit to send: {}".format(result["playerKit"]))
        if result["macDmg"]:
            print("mac DMG to send: {}".format(result["macDmg"]))
        elif result["macApp"]:
            print("mac app bundle: {}".format(result["macApp"]))
        print("private credentials: {}".format(result["privateCredentials"]))
        print("account record to install on server: {}".format(result["accountRecord"]))
        print("password: not printed; send it from the private credentials file through a private channel")
        print("runtime: not started, stopped, or restarted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
