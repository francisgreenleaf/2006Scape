#!/usr/bin/env python3
"""Create a PBKDF2 account record for external 2006Scape login."""

import argparse
import base64
import getpass
import hashlib
import json
import os
import re
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
MIN_ITERATIONS = 120000
MIN_PASSWORD_LENGTH = 12
PASSWORD_POLICY_VERSION = 1
ROLE_RE = re.compile(r"[A-Za-z0-9_.:-]{1,32}")
DISCORD_USER_ID_RE = re.compile(r"\d{15,25}")
ALGORITHMS = {
    "sha256": ("sha256", "PBKDF2WithHmacSHA256"),
    "sha1": ("sha1", "PBKDF2WithHmacSHA1"),
}


def normalize_username(value):
    normalized = (value or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9 .]{1,12}", normalized):
        raise SystemExit("username must be 1-12 chars: letters, numbers, spaces, or dots")
    return normalized


def safe_file_name(username):
    return re.sub(r"[^a-z0-9._-]", "_", username.replace(" ", "_"))


def normalize_role(value):
    clean = (value or "").strip()
    if not ROLE_RE.fullmatch(clean):
        raise SystemExit("role must be 1-32 chars: letters, numbers, underscore, dot, colon, or hyphen")
    return clean


def normalize_discord_user_id(value):
    clean = (value or "").strip()
    if not DISCORD_USER_ID_RE.fullmatch(clean):
        raise SystemExit("discord user id must be a numeric Discord snowflake string")
    return clean


def validate_password(password, allow_weak_password):
    if not password:
        raise SystemExit("password is required")
    if not allow_weak_password and len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            "password must be at least {} characters; pass --allow-weak-password "
            "only for local throwaway/source validation accounts".format(MIN_PASSWORD_LENGTH)
        )


def unique_preserving_order(values):
    seen = set()
    output = []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            output.append(value)
    return output


def chmod_private(path, mode):
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def write_private_json(path, record):
    if path.is_symlink():
        raise SystemExit("refusing to write symlinked account record: {}".format(path))
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(path), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
            handle.write("\n")
    finally:
        chmod_private(path, 0o600)


def load_existing_record(path):
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("could not read existing account record for metadata preservation: {}".format(exc))
    if not isinstance(record, dict):
        raise SystemExit("existing account record must be a JSON object to preserve metadata: {}".format(path))
    return record


def existing_string_list(record, key, normalizer):
    value = record.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise SystemExit("existing account record field {} must be an array to preserve metadata".format(key))
    normalized = []
    for item in value:
        if not isinstance(item, str):
            raise SystemExit("existing account record field {} entries must be strings to preserve metadata".format(key))
        normalized.append(normalizer(item))
    return unique_preserving_order(normalized)


def existing_discord_user_id(record):
    value = record.get("discordUserId", "")
    if value is None or str(value).strip() == "":
        return ""
    if not isinstance(value, str):
        raise SystemExit("existing account record discordUserId must be a string to preserve metadata")
    return normalize_discord_user_id(str(value))


def existing_disabled(record):
    value = record.get("disabled", False)
    if not isinstance(value, bool):
        raise SystemExit("existing account record disabled field must be a boolean to preserve metadata")
    return value


def main():
    parser = argparse.ArgumentParser(description="Create a 2006Scape PBKDF2 account JSON record.")
    parser.add_argument("username")
    parser.add_argument("--password-env", default="")
    parser.add_argument("--accounts-dir", default=str(ROOT_DIR / "2006Scape Server" / "data" / "accounts"))
    parser.add_argument("--iterations", type=int, default=MIN_ITERATIONS)
    parser.add_argument("--algorithm", choices=sorted(ALGORITHMS), default="sha256",
            help="PBKDF2 digest to write. Use sha256 normally; sha1 is only for older Java 8 runtimes that lack PBKDF2WithHmacSHA256.")
    parser.add_argument("--allow-weak-password", action="store_true",
            help="Allow passwords shorter than {} characters for local throwaway/source validation accounts only.".format(MIN_PASSWORD_LENGTH))
    parser.add_argument("--disabled", action="store_true")
    parser.add_argument("--discord-user-id", default="")
    parser.add_argument("--role", action="append", default=[],
            help="Optional account role metadata. May be passed multiple times.")
    parser.add_argument("--allowed-character", action="append", default=[],
            help="Optional allowed character name metadata. May be passed multiple times.")
    parser.add_argument("--preserve-metadata", action="store_true",
            help="When overwriting an existing account, preserve roles, allowedCharacters, discordUserId, and disabled state unless explicitly overridden.")
    parser.add_argument("--enabled", action="store_true",
            help="When used with --overwrite --preserve-metadata, clear an existing disabled flag.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.disabled and args.enabled:
        raise SystemExit("--disabled and --enabled cannot both be set")

    username = normalize_username(args.username)
    roles = unique_preserving_order([normalize_role(role) for role in args.role])
    allowed_characters = unique_preserving_order([
        normalize_username(character) for character in args.allowed_character
    ])
    discord_user_id = normalize_discord_user_id(args.discord_user_id) if args.discord_user_id else ""
    if args.password_env:
        password = os.environ.get(args.password_env, "")
        if not password:
            raise SystemExit("password environment variable is not set: {}".format(args.password_env))
    else:
        password = getpass.getpass("Password for {}: ".format(username))
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            raise SystemExit("passwords did not match")
    validate_password(password, args.allow_weak_password)

    accounts_dir = Path(args.accounts_dir)
    if accounts_dir.exists() and accounts_dir.is_symlink():
        raise SystemExit("refusing to use symlinked accounts directory: {}".format(accounts_dir))
    accounts_dir.mkdir(parents=True, exist_ok=True)
    if accounts_dir.is_symlink():
        raise SystemExit("refusing to use symlinked accounts directory: {}".format(accounts_dir))
    chmod_private(accounts_dir, 0o700)
    path = accounts_dir / "{}.json".format(safe_file_name(username))
    if path.exists() and not args.overwrite:
        raise SystemExit("account already exists; pass --overwrite to replace: {}".format(path))
    existing_record = load_existing_record(path) if args.preserve_metadata else {}
    if args.preserve_metadata and not args.overwrite:
        raise SystemExit("--preserve-metadata requires --overwrite")
    if args.preserve_metadata:
        if not args.role:
            roles = existing_string_list(existing_record, "roles", normalize_role)
        if not args.allowed_character:
            allowed_characters = existing_string_list(existing_record, "allowedCharacters", normalize_username)
        if not args.discord_user_id:
            discord_user_id = existing_discord_user_id(existing_record)

    salt = os.urandom(16)
    iterations = int(args.iterations)
    if iterations < MIN_ITERATIONS:
        raise SystemExit("iterations must be at least {}".format(MIN_ITERATIONS))
    digest_name, java_algorithm = ALGORITHMS[args.algorithm]
    digest = hashlib.pbkdf2_hmac(digest_name, password.encode("utf-8"), salt, iterations, dklen=32)
    record = {
        "username": username,
        "passwordHash": base64.b64encode(digest).decode("ascii"),
        "passwordSalt": base64.b64encode(salt).decode("ascii"),
        "passwordIterations": iterations,
        "algorithm": java_algorithm,
        "createdAt": int(time.time() * 1000),
        "createdBy": "scripts/create-account.py",
        "disabled": bool(args.disabled)
        or bool(args.preserve_metadata and existing_disabled(existing_record) and not args.enabled),
        "passwordPolicy": {
            "version": PASSWORD_POLICY_VERSION,
            "minLength": MIN_PASSWORD_LENGTH,
            "allowWeakPassword": bool(args.allow_weak_password),
        },
        "roles": roles,
        "allowedCharacters": allowed_characters,
    }
    if discord_user_id:
        record["discordUserId"] = discord_user_id
    write_private_json(path, record)
    print("created account record: {}".format(path))


if __name__ == "__main__":
    main()
