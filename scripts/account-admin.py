#!/usr/bin/env python3
"""Inspect and update 2006Scape PBKDF2 account records."""

import argparse
import base64
import binascii
import json
import os
import re
import stat
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ACCOUNTS_DIR = ROOT_DIR / "2006Scape Server" / "data" / "accounts"
MIN_ITERATIONS = 120000
MIN_PASSWORD_LENGTH = 12
MIN_PASSWORD_POLICY_VERSION = 1
USERNAME_RE = re.compile(r"[a-z0-9 .]{1,12}")
ROLE_RE = re.compile(r"[A-Za-z0-9_.:-]{1,32}")
DISCORD_USER_ID_RE = re.compile(r"\d{15,25}")
SUPPORTED_ALGORITHMS = {"PBKDF2WithHmacSHA256", "PBKDF2WithHmacSHA1"}


def normalize_username(value):
    normalized = (value or "").strip().lower()
    if not USERNAME_RE.fullmatch(normalized):
        raise SystemExit("username must be 1-12 chars: letters, numbers, spaces, or dots")
    return normalized


def account_file_name(username):
    return re.sub(r"[^a-z0-9._-]", "_", username.replace(" ", "_")) + ".json"


def chmod_private(path, mode):
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def owner_only_permission_issue(path, label, allow_executable):
    if os.name != "posix":
        return ""
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        return "could not inspect {} permissions: {}".format(label, exc)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        return "{} permissions must be owner-only, got {:03o}".format(label, mode)
    if not allow_executable and mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        return "{} must not be executable, got {:03o}".format(label, mode)
    return ""


def decode_base64_field(record, key, expected_length, issues):
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append("missing {}".format(key))
        return
    try:
        decoded = base64.b64decode(value.strip(), validate=True)
    except (binascii.Error, ValueError):
        issues.append("invalid base64 {}".format(key))
        return
    if len(decoded) != expected_length:
        issues.append("{} must decode to {} bytes".format(key, expected_length))


def validate_string_array(record, key, item_label, validator, issues):
    value = record.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        issues.append("{} must be an array".format(key))
        return []
    output = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            issues.append("{}[{}] must be a string".format(key, index))
            continue
        clean = item.strip()
        if not clean:
            issues.append("{}[{}] must not be empty".format(key, index))
            continue
        if not validator(clean):
            issues.append("{}[{}] has invalid {}".format(key, index, item_label))
            continue
        output.append(clean)
    return output


def validate_password_policy(record, issues, require_policy):
    value = record.get("passwordPolicy")
    if value is None:
        if require_policy:
            issues.append("passwordPolicy is required")
        return {
            "present": False,
            "valid": not require_policy,
            "version": 0,
            "minLength": 0,
            "allowWeakPassword": None,
        }
    policy = {
        "present": True,
        "valid": False,
        "version": 0,
        "minLength": 0,
        "allowWeakPassword": None,
    }
    if not isinstance(value, dict):
        issues.append("passwordPolicy must be an object")
        return policy
    try:
        version = int(value.get("version", 0))
    except (TypeError, ValueError):
        version = 0
        issues.append("passwordPolicy.version must be an integer")
    if version < MIN_PASSWORD_POLICY_VERSION:
        issues.append("passwordPolicy.version must be at least {}".format(MIN_PASSWORD_POLICY_VERSION))
    try:
        min_length = int(value.get("minLength", 0))
    except (TypeError, ValueError):
        min_length = 0
        issues.append("passwordPolicy.minLength must be an integer")
    if min_length < MIN_PASSWORD_LENGTH:
        issues.append("passwordPolicy.minLength must be at least {}".format(MIN_PASSWORD_LENGTH))
    allow_weak = value.get("allowWeakPassword", False)
    if not isinstance(allow_weak, bool):
        issues.append("passwordPolicy.allowWeakPassword must be a boolean")
        allow_weak = None
    elif allow_weak:
        issues.append("passwordPolicy must not allow weak passwords")
    policy.update({
        "valid": version >= MIN_PASSWORD_POLICY_VERSION
        and min_length >= MIN_PASSWORD_LENGTH
        and allow_weak is False,
        "version": version,
        "minLength": min_length,
        "allowWeakPassword": allow_weak,
    })
    return policy


def load_record(path, issues):
    if path.is_symlink():
        issues.append("account record must not be a symlink")
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            record = json.load(handle)
    except OSError as exc:
        issues.append("could not read record: {}".format(exc))
        return {}
    except json.JSONDecodeError as exc:
        issues.append("invalid JSON: {}".format(exc))
        return {}
    if not isinstance(record, dict):
        issues.append("record must be a JSON object")
        return {}
    return record


def summarize_record(path, min_iterations, require_password_policy=False):
    issues = []
    permission_issue = owner_only_permission_issue(path, "account record", False)
    if permission_issue:
        issues.append(permission_issue)
    record = load_record(path, issues)
    username = record.get("username", "")
    if not isinstance(username, str) or not USERNAME_RE.fullmatch(username.strip().lower()):
        issues.append("invalid username")
        normalized_username = ""
    else:
        normalized_username = username.strip().lower()
        expected_name = account_file_name(normalized_username)
        if path.name != expected_name:
            issues.append("filename should be {}".format(expected_name))

    decode_base64_field(record, "passwordHash", 32, issues)
    decode_base64_field(record, "passwordSalt", 16, issues)
    try:
        iterations = int(record.get("passwordIterations", 0))
    except (TypeError, ValueError):
        iterations = 0
        issues.append("passwordIterations must be an integer")
    if iterations < min_iterations:
        issues.append("passwordIterations must be at least {}".format(min_iterations))

    algorithm = record.get("algorithm", "")
    if algorithm not in SUPPORTED_ALGORITHMS:
        issues.append("unsupported algorithm {}".format(algorithm))

    disabled = record.get("disabled", False)
    if not isinstance(disabled, bool):
        issues.append("disabled must be a boolean")
        disabled = False

    roles = validate_string_array(
        record,
        "roles",
        "role",
        lambda value: ROLE_RE.fullmatch(value) is not None,
        issues,
    )
    allowed_characters = validate_string_array(
        record,
        "allowedCharacters",
        "character name",
        lambda value: USERNAME_RE.fullmatch(value.strip().lower()) is not None,
        issues,
    )
    discord_user_id = record.get("discordUserId", "")
    if discord_user_id:
        if not isinstance(discord_user_id, str) or DISCORD_USER_ID_RE.fullmatch(discord_user_id.strip()) is None:
            issues.append("discordUserId must be a numeric Discord snowflake string")
            discord_user_id = ""
        else:
            discord_user_id = discord_user_id.strip()
    password_policy = validate_password_policy(record, issues, require_password_policy)

    return {
        "file": str(path),
        "username": normalized_username,
        "disabled": bool(disabled),
        "algorithm": algorithm if isinstance(algorithm, str) else "",
        "passwordIterations": iterations,
        "roles": roles,
        "allowedCharacters": [value.strip().lower() for value in allowed_characters],
        "discordUserId": discord_user_id,
        "passwordPolicy": password_policy,
        "valid": not issues,
        "issues": issues,
    }


def scan_accounts(accounts_dir, min_iterations, require_password_policy=False):
    accounts_dir = Path(accounts_dir)
    directory_issues = []
    if not accounts_dir.exists():
        directory_issues.append("accounts directory is missing")
        records = []
    elif accounts_dir.is_symlink():
        directory_issues.append("accounts directory must not be a symlink")
        records = []
    elif not accounts_dir.is_dir():
        directory_issues.append("accounts path is not a directory")
        records = []
    else:
        permission_issue = owner_only_permission_issue(accounts_dir, "accounts directory", True)
        if permission_issue:
            directory_issues.append(permission_issue)
        records = sorted(accounts_dir.glob("*.json"))

    accounts = [summarize_record(path, min_iterations, require_password_policy) for path in records]
    enabled = sum(1 for account in accounts if account["valid"] and not account["disabled"])
    disabled = sum(1 for account in accounts if account["valid"] and account["disabled"])
    invalid = sum(1 for account in accounts if not account["valid"]) + (1 if directory_issues else 0)
    return {
        "accountsDir": str(accounts_dir),
        "total": len(accounts),
        "enabled": enabled,
        "disabled": disabled,
        "invalid": invalid,
        "directoryIssues": directory_issues,
        "accounts": accounts,
    }


def print_table(report):
    if report["directoryIssues"]:
        for issue in report["directoryIssues"]:
            print("directory issue: {}".format(issue), file=sys.stderr)
    rows = report["accounts"]
    if not rows:
        print("no account records found in {}".format(report["accountsDir"]))
        return
    print("{:<12} {:<8} {:<24} {:<10} {:<18} {:<18} {}".format(
        "username", "status", "algorithm", "iterations", "roles", "characters", "issues"))
    for account in rows:
        status = "invalid"
        if account["valid"]:
            status = "disabled" if account["disabled"] else "enabled"
        roles = ",".join(account["roles"]) if account["roles"] else "-"
        characters = ",".join(account["allowedCharacters"]) if account["allowedCharacters"] else "-"
        issues = "; ".join(account["issues"]) if account["issues"] else "-"
        print("{:<12} {:<8} {:<24} {:<10} {:<18} {:<18} {}".format(
            account["username"] or "?",
            status,
            account["algorithm"] or "?",
            account["passwordIterations"],
            roles[:18],
            characters[:18],
            issues,
        ))


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


def load_mutable_account(accounts_dir, username):
    normalized = normalize_username(username)
    path = Path(accounts_dir) / account_file_name(normalized)
    if path.is_symlink():
        raise SystemExit("refusing to modify symlinked account record: {}".format(path))
    if not path.exists():
        raise SystemExit("account record does not exist: {}".format(path))
    issues = []
    record = load_record(path, issues)
    if issues:
        raise SystemExit("could not load account record {}: {}".format(path, "; ".join(issues)))
    record_username = record.get("username", "")
    if not isinstance(record_username, str) or record_username.strip().lower() != normalized:
        raise SystemExit("account record username does not match requested account: {}".format(path))
    return path, record


def set_account_enabled(accounts_dir, username, enabled):
    path, record = load_mutable_account(accounts_dir, username)
    record["disabled"] = not enabled
    write_private_json(path, record)
    print("{} account record: {}".format("enabled" if enabled else "disabled", path))


def command_list(args):
    report = scan_accounts(args.accounts_dir, args.min_iterations, args.require_password_policy)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_table(report)
        print("summary: total={total} enabled={enabled} disabled={disabled} invalid={invalid}".format(**report))
    return 0


def command_audit(args):
    report = scan_accounts(args.accounts_dir, args.min_iterations, args.require_password_policy)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_table(report)
        print("summary: total={total} enabled={enabled} disabled={disabled} invalid={invalid}".format(**report))
    if report["invalid"]:
        return 1
    return 0


def command_show(args):
    username = normalize_username(args.username)
    report = scan_accounts(args.accounts_dir, args.min_iterations, args.require_password_policy)
    for account in report["accounts"]:
        if account["username"] == username:
            if args.json:
                print(json.dumps(account, indent=2, sort_keys=True))
            else:
                print_table({"accountsDir": report["accountsDir"], "directoryIssues": [], "accounts": [account]})
            return 0 if account["valid"] else 1
    raise SystemExit("account record does not exist: {}".format(username))


def command_enable(args):
    set_account_enabled(args.accounts_dir, args.username, True)
    return 0


def command_disable(args):
    set_account_enabled(args.accounts_dir, args.username, False)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Inspect and update 2006Scape PBKDF2 account records.")
    parser.add_argument("--accounts-dir", default=str(DEFAULT_ACCOUNTS_DIR))
    parser.add_argument("--min-iterations", type=int, default=MIN_ITERATIONS)
    parser.add_argument("--require-password-policy", action="store_true",
            help="Require helper-stamped passwordPolicy metadata proving the weak-password override was not used.")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="List account records without failing on invalid records.")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=command_list)

    audit_parser = subparsers.add_parser("audit", help="Validate all account records and fail if any are invalid.")
    audit_parser.add_argument("--json", action="store_true")
    audit_parser.set_defaults(func=command_audit)

    show_parser = subparsers.add_parser("show", help="Show one account record summary.")
    show_parser.add_argument("username")
    show_parser.add_argument("--json", action="store_true")
    show_parser.set_defaults(func=command_show)

    enable_parser = subparsers.add_parser("enable", help="Clear the disabled flag on one account record.")
    enable_parser.add_argument("username")
    enable_parser.set_defaults(func=command_enable)

    disable_parser = subparsers.add_parser("disable", help="Set the disabled flag on one account record.")
    disable_parser.add_argument("username")
    disable_parser.set_defaults(func=command_disable)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        args.func = command_audit
        args.json = False
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
