#!/usr/bin/env python3
"""Plan or install one PBKDF2 account record onto a remote deployment host."""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ACCOUNTS_DIR = ROOT_DIR / "2006Scape Server" / "data" / "accounts"
USERNAME_RE = re.compile(r"[a-z0-9 .]{1,12}", re.IGNORECASE)


def fail(message):
    raise SystemExit(message)


def resolve_under_root(path):
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def normalize_username(value):
    clean = (value or "").strip().lower()
    if not USERNAME_RE.fullmatch(clean):
        fail("username must be 1-12 chars: letters, numbers, spaces, or dots")
    return clean


def safe_file_name(username):
    return re.sub(r"[^a-z0-9._-]", "_", username.replace(" ", "_"))


def reject_symlink(path, label):
    if path.is_symlink():
        fail("{} must not be a symlink: {}".format(label, path))


def load_account_record(path):
    reject_symlink(path, "account record")
    if not path.is_file():
        fail("account record is missing: {}".format(path))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail("could not read account record {}: {}".format(path, exc))
    if not isinstance(data, dict):
        fail("account record must be a JSON object: {}".format(path))
    for key in ("username", "passwordHash", "passwordSalt", "passwordIterations", "algorithm"):
        if key not in data:
            fail("account record is missing required key {}: {}".format(key, path))
    return data


def remote_install_command(remote_tmp, remote_account_path, remote_accounts_dir, owner, group):
    parts = [
        "install",
        "-d",
        "-m",
        "700",
    ]
    if owner:
        parts.extend(["-o", owner])
    if group:
        parts.extend(["-g", group])
    parts.append(remote_accounts_dir)
    commands = [" ".join(shlex.quote(part) for part in parts)]

    install_parts = ["install", "-m", "600"]
    if owner:
        install_parts.extend(["-o", owner])
    if group:
        install_parts.extend(["-g", group])
    install_parts.extend([remote_tmp, remote_account_path])
    commands.append(" ".join(shlex.quote(part) for part in install_parts))
    commands.append("rm -f {}".format(shlex.quote(remote_tmp)))
    return " && ".join(commands)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run by default helper for installing one ignored PBKDF2 account JSON "
            "onto a VPS/deployment host. It never restarts runtime and never prints account contents."
        )
    )
    parser.add_argument("username", help="Account username to install.")
    parser.add_argument("--accounts-dir", default=str(DEFAULT_ACCOUNTS_DIR), help="Local ignored account-record directory.")
    parser.add_argument("--account-record", default="", help="Explicit local account JSON path.")
    parser.add_argument("--ssh-target", required=True, help="SSH target such as user@example.com.")
    parser.add_argument("--ssh-key", default="", help="Optional private key path for ssh/scp.")
    parser.add_argument("--remote-accounts-dir", required=True, help="Remote 2006Scape Server/data/accounts directory.")
    parser.add_argument("--remote-owner", default="", help="Optional remote file owner for install -o.")
    parser.add_argument("--remote-group", default="", help="Optional remote file group for install -g.")
    parser.add_argument("--apply", action="store_true", help="Actually copy/install the account record. Default is dry-run.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary.")
    args = parser.parse_args()

    username = normalize_username(args.username)
    account_name = "{}.json".format(safe_file_name(username))
    accounts_dir = resolve_under_root(Path(args.accounts_dir))
    account_path = resolve_under_root(Path(args.account_record)) if args.account_record else accounts_dir / account_name
    record = load_account_record(account_path)
    if record.get("username") != username:
        fail("account record username mismatch: expected {}, found {}".format(username, record.get("username")))

    remote_accounts_dir = args.remote_accounts_dir.rstrip("/")
    if not remote_accounts_dir or "\x00" in remote_accounts_dir or "\n" in remote_accounts_dir:
        fail("--remote-accounts-dir must be a non-empty single-line path")
    remote_account_path = "{}/{}".format(remote_accounts_dir, account_name)
    remote_tmp = "/tmp/2006scape-account-{}-{}.json".format(account_name[:-5], os.getpid())
    install_script = remote_install_command(
        remote_tmp,
        remote_account_path,
        remote_accounts_dir,
        args.remote_owner,
        args.remote_group,
    )

    scp_argv = ["scp"]
    ssh_argv = ["ssh"]
    if args.ssh_key:
        scp_argv.extend(["-i", args.ssh_key])
        ssh_argv.extend(["-i", args.ssh_key])
    scp_argv.extend([str(account_path), "{}:{}".format(args.ssh_target, remote_tmp)])
    ssh_argv.extend([args.ssh_target, install_script])

    result = {
        "success": True,
        "dryRun": not args.apply,
        "username": username,
        "localAccountRecord": str(account_path),
        "sshTarget": args.ssh_target,
        "remoteAccountRecord": remote_account_path,
        "scpCommand": " ".join(shlex.quote(part) for part in scp_argv),
        "sshInstallCommand": " ".join(shlex.quote(part) for part in ssh_argv),
        "runtimeTouched": False,
        "passwordPrinted": False,
    }

    if args.apply:
        subprocess.check_call(scp_argv, cwd=str(ROOT_DIR))
        subprocess.check_call(ssh_argv, cwd=str(ROOT_DIR))
        result["applied"] = True
    else:
        result["applied"] = False

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if args.apply:
            print("ok: installed account record for {}".format(username))
        else:
            print("dry-run: account record install plan for {}".format(username))
            print("copy: {}".format(result["scpCommand"]))
            print("install: {}".format(result["sshInstallCommand"]))
            print("pass --apply to perform the copy/install")
        print("local account record: {}".format(account_path))
        print("remote account record: {}".format(remote_account_path))
        print("password: not printed")
        print("runtime: not started, stopped, or restarted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
