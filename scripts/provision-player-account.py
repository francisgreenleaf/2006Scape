#!/usr/bin/env python3
"""Provision a PBKDF2 player account and public-safe handoff note."""

import argparse
import json
import os
import re
import secrets
import string
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PREPARED_DIR = ROOT_DIR / "dist" / "external-deployment"
DEFAULT_ACCOUNTS_DIR = ROOT_DIR / "2006Scape Server" / "data" / "accounts"
USERNAME_RE = re.compile(r"[a-z0-9 .]{1,12}", re.IGNORECASE)
ROLE_RE = re.compile(r"[A-Za-z0-9_.:-]{1,32}")
DISCORD_USER_ID_RE = re.compile(r"\d{15,25}")
SAFE_ENV_RE = re.compile(r"[^A-Za-z0-9_]+")
UNSAFE_ENV_VALUE_RE = re.compile(r"[\x00\r\n]")
MIN_PASSWORD_LENGTH = 12
DEFAULT_PASSWORD_LENGTH = 20


def fail(message):
    raise SystemExit(message)


def chmod_private(path, mode):
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def reject_symlinked_path(path, label):
    if path.is_symlink():
        fail("{} must not be a symlink: {}".format(label, path))


def reject_symlinked_output_path(path, label):
    reject_symlinked_path(path, label)
    parent = path.parent
    while True:
        if parent.is_symlink():
            fail("refusing to write {} through symlinked parent directory: {}".format(label, parent))
        if parent.exists():
            if not parent.is_dir():
                fail("{} parent must be a directory: {}".format(label, parent))
            return
        if parent == parent.parent:
            fail("{} parent does not exist: {}".format(label, path.parent))
        parent = parent.parent


def resolve_under_root(path):
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def normalize_player_name(value, label):
    clean = (value or "").strip()
    if not USERNAME_RE.fullmatch(clean):
        fail("{} must be 1-12 characters: letters, numbers, spaces, or dots".format(label))
    return clean


def normalize_role(value):
    clean = (value or "").strip()
    if not ROLE_RE.fullmatch(clean):
        fail("role must be 1-32 chars: letters, numbers, underscore, dot, colon, or hyphen")
    return clean


def normalize_discord_user_id(value):
    clean = (value or "").strip()
    if not clean:
        return ""
    if not DISCORD_USER_ID_RE.fullmatch(clean):
        fail("discord user id must be a numeric Discord snowflake string")
    return clean


def safe_file_stem(value):
    clean = SAFE_ENV_RE.sub("_", value.strip()).strip("_").lower()
    return clean or "player"


def env_key(value):
    clean = SAFE_ENV_RE.sub("_", value.strip()).strip("_").upper()
    if not clean:
        clean = "PLAYER"
    if clean[0].isdigit():
        clean = "PLAYER_" + clean
    return clean


def generate_password(length):
    if length < MIN_PASSWORD_LENGTH:
        fail("generated password length must be at least {}".format(MIN_PASSWORD_LENGTH))
    alphabet = string.ascii_letters + string.digits
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(ch.islower() for ch in value)
            and any(ch.isupper() for ch in value)
            and any(ch.isdigit() for ch in value)
        ):
            return value


def reject_unsafe_private_env_value(value, label):
    if UNSAFE_ENV_VALUE_RE.search(value):
        fail("{} must not contain NUL or newline characters".format(label))


def read_password(args):
    if args.password_env:
        password = os.environ.get(args.password_env, "")
        if not password:
            fail("password environment variable is not set: {}".format(args.password_env))
        if len(password) < MIN_PASSWORD_LENGTH and not args.allow_weak_password:
            fail("password must be at least {} characters".format(MIN_PASSWORD_LENGTH))
        reject_unsafe_private_env_value(password, "password")
        return password, "env:{}".format(args.password_env)
    password = generate_password(args.password_length)
    reject_unsafe_private_env_value(password, "password")
    return password, "generated"


def run_checked(argv, env, label, verbose):
    completed = subprocess.run(
        argv,
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        output = (completed.stdout or "").strip()
        fail("{} failed:\n{}".format(label, output))
    if verbose and completed.stdout:
        print(completed.stdout.rstrip())
    return completed.stdout or ""


def shell_quote_single(value):
    return "'" + value.replace("'", "'\"'\"'") + "'"


def write_private_credentials(path, username, character, password, password_source):
    reject_symlinked_output_path(path, "private credentials file")
    path.parent.mkdir(parents=True, exist_ok=True)
    chmod_private(path.parent, 0o700)
    prefix = env_key(username)
    text = "\n".join([
        "# Private 2006Scape player credentials. Do not commit or send in public channels.",
        "{}_USERNAME={}".format(prefix, shell_quote_single(username)),
        "{}_CHARACTER={}".format(prefix, shell_quote_single(character)),
        "{}_PASSWORD={}".format(prefix, shell_quote_single(password)),
        "{}_PASSWORD_SOURCE={}".format(prefix, shell_quote_single(password_source)),
        "",
    ])
    if path.is_symlink():
        fail("refusing to write symlinked private credentials file: {}".format(path))
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(path), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
    finally:
        chmod_private(path, 0o600)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create a PBKDF2 account record, run account audit, render a public-safe "
            "player handoff note, and write the password only to an ignored private file."
        )
    )
    parser.add_argument("username", help="Player account username.")
    parser.add_argument("--character", default="", help="Allowed/logged-in character. Defaults to username.")
    parser.add_argument("--prepared-dir", default=str(DEFAULT_PREPARED_DIR),
            help="Prepared deployment directory. Defaults to dist/external-deployment.")
    parser.add_argument("--accounts-dir", default=str(DEFAULT_ACCOUNTS_DIR),
            help="Ignored PBKDF2 account-record directory.")
    parser.add_argument("--handoff-output", default="",
            help="Public-safe handoff note output. Defaults to PREPARED_DIR/player-handoff-USERNAME.md.")
    parser.add_argument("--credentials-output", default="",
            help="Private credentials env file. Defaults to PREPARED_DIR/private/player-credentials-USERNAME.env.")
    parser.add_argument("--password-env", default="",
            help="Use an existing password from this environment variable instead of generating one.")
    parser.add_argument("--password-length", type=int, default=DEFAULT_PASSWORD_LENGTH,
            help="Length for generated passwords. Defaults to 20; minimum is 12.")
    parser.add_argument("--allow-weak-password", action="store_true",
            help="Pass through only for local throwaway/source-validation accounts.")
    parser.add_argument("--overwrite", action="store_true",
            help="Replace an existing account record.")
    parser.add_argument("--preserve-metadata", action="store_true",
            help="When overwriting, preserve existing account metadata unless explicitly supplied.")
    parser.add_argument("--role", action="append", default=[], help="Optional account role. May be repeated.")
    parser.add_argument("--discord-user-id", default="", help="Optional Discord user id metadata.")
    parser.add_argument("--agent-gateway-url", default="",
            help="Optional HTTPS /agent gateway URL to show in the public handoff note.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary.")
    parser.add_argument("--verbose", action="store_true", help="Print child command output, never passwords.")
    args = parser.parse_args()

    username = normalize_player_name(args.username, "username")
    character = normalize_player_name(args.character or args.username, "character")
    roles = [normalize_role(role) for role in args.role]
    discord_user_id = normalize_discord_user_id(args.discord_user_id)
    prepared_dir = resolve_under_root(Path(args.prepared_dir))
    accounts_dir = resolve_under_root(Path(args.accounts_dir))
    if accounts_dir.exists() and accounts_dir.is_symlink():
        fail("accounts directory must not be a symlink: {}".format(accounts_dir))
    if prepared_dir.is_symlink():
        fail("prepared deployment directory must not be a symlink: {}".format(prepared_dir))
    if not prepared_dir.is_dir():
        fail("prepared deployment directory is missing: {}".format(prepared_dir))

    stem = safe_file_stem(username)
    handoff_output = resolve_under_root(Path(args.handoff_output)) if args.handoff_output else prepared_dir / "player-handoff-{}.md".format(stem)
    credentials_output = (
        resolve_under_root(Path(args.credentials_output))
        if args.credentials_output
        else prepared_dir / "private" / "player-credentials-{}.env".format(stem)
    )
    password, password_source = read_password(args)

    child_env = os.environ.copy()
    child_env["PLAYER_ACCOUNT_PASSWORD"] = password
    create_argv = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "create-account.py"),
        username,
        "--accounts-dir",
        str(accounts_dir),
        "--password-env",
        "PLAYER_ACCOUNT_PASSWORD",
        "--allowed-character",
        character,
    ]
    for role in roles:
        create_argv.extend(["--role", role])
    if discord_user_id:
        create_argv.extend(["--discord-user-id", discord_user_id])
    if args.allow_weak_password:
        create_argv.append("--allow-weak-password")
    if args.overwrite:
        create_argv.append("--overwrite")
    if args.preserve_metadata:
        create_argv.append("--preserve-metadata")
    run_checked(create_argv, child_env, "account creation", args.verbose)

    audit_argv = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "account-admin.py"),
        "--accounts-dir",
        str(accounts_dir),
        "--require-password-policy",
        "audit",
    ]
    run_checked(audit_argv, os.environ.copy(), "account audit", args.verbose)

    write_private_credentials(credentials_output, username, character, password, password_source)

    handoff_argv = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "render-player-handoff.py"),
        "--prepared-dir",
        str(prepared_dir),
        "--username",
        username,
        "--character",
        character,
        "--output",
        str(handoff_output),
    ]
    if args.agent_gateway_url:
        handoff_argv.extend(["--agent-gateway-url", args.agent_gateway_url])
    run_checked(handoff_argv, os.environ.copy(), "player handoff render", args.verbose)

    result = {
        "success": True,
        "username": username,
        "character": character,
        "accountsDir": str(accounts_dir),
        "handoffNote": str(handoff_output),
        "privateCredentials": str(credentials_output),
        "passwordPrinted": False,
        "runtimeTouched": False,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("ok: provisioned player account {}".format(username))
        print("handoff note: {}".format(handoff_output))
        print("private credentials: {}".format(credentials_output))
        print("password: not printed; send it from the private credentials file through a private channel")
        print("runtime: not started, stopped, or restarted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
