#!/usr/bin/env python3
"""Probe a 2006Scape game login over raw TCP or a client/server TLS tunnel."""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts" / "lib"))

from game_login_probe import LoginProbeError, probe_login  # noqa: E402


def fail(message):
    raise SystemExit("game login probe failed: {}".format(message))


def password_from_args(args):
    if args.password_env:
        value = os.environ.get(args.password_env)
        if value is None:
            fail("environment variable {} is not set".format(args.password_env))
        return value
    return getpass.getpass("Password for {}: ".format(args.username))


def parse_expected_statuses(value):
    statuses = set()
    for raw in str(value or "").split(","):
        item = raw.strip()
        if not item:
            continue
        try:
            status = int(item)
        except ValueError:
            fail("--expect-statuses must be a comma-separated list of numeric login status codes")
        if status < 0 or status > 255:
            fail("--expect-statuses values must be between 0 and 255")
        statuses.add(status)
    return statuses


def main():
    parser = argparse.ArgumentParser(description="Probe 2006Scape game-protocol login without launching the GUI client.")
    parser.add_argument("--host", default="127.0.0.1", help="Game host or TLS tunnel endpoint.")
    parser.add_argument("--port", type=int, default=43594, help="Game port.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="",
            help="Read the password from this environment variable. If omitted, prompt securely.")
    parser.add_argument("--tls", action="store_true",
            help="Wrap the game socket in TLS first. Use for client_tls_tunnel public endpoints.")
    parser.add_argument("--tls-sni-host", default="",
            help="SNI/hostname for --tls. Defaults to --host.")
    parser.add_argument("--allow-untrusted-tls", action="store_true",
            help="Allow self-signed or otherwise untrusted TLS certificates for private tunnel tests.")
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--hold-seconds", type=float, default=0.0,
            help="Keep the successful login socket open briefly to prove the server accepts the session.")
    parser.add_argument("--expect-failure", action="store_true",
            help="Pass only if login is rejected. Useful for wrong-password, missing-account, and disabled-account fail-closed checks.")
    parser.add_argument("--expect-statuses", default="",
            help="With --expect-failure, require one of these comma-separated numeric rejection status codes.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.expect_statuses and not args.expect_failure:
        fail("--expect-statuses requires --expect-failure")

    password = password_from_args(args)
    try:
        result = probe_login(
            args.host,
            args.port,
            args.username,
            password,
            timeout=args.timeout,
            use_tls=args.tls,
            tls_sni_host=args.tls_sni_host,
            allow_untrusted_tls=args.allow_untrusted_tls,
            hold_seconds=args.hold_seconds,
        )
    except (OSError, LoginProbeError) as exc:
        fail(str(exc))

    success = result.get("status") == 2
    expected_statuses = parse_expected_statuses(args.expect_statuses)
    if args.expect_failure and success:
        fail("login unexpectedly succeeded for {}".format(args.username))
    if args.expect_failure and expected_statuses and result.get("status") not in expected_statuses:
        fail("login rejected for {} with status {} ({}) but expected one of {}".format(
            args.username,
            result.get("status"),
            result.get("statusName"),
            ",".join(str(item) for item in sorted(expected_statuses)),
        ))
    if not args.expect_failure and not success:
        fail("login rejected for {} with status {} ({})".format(
            args.username, result.get("status"), result.get("statusName")))

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        outcome = "accepted" if success else "rejected"
        suffix = ""
        if expected_statuses:
            suffix = " expected={}".format(",".join(str(item) for item in sorted(expected_statuses)))
        print("ok: login {} for {} at {}:{} status={} ({}) tls={}{}".format(
            outcome,
            args.username,
            args.host,
            args.port,
            result.get("status"),
            result.get("statusName"),
            "yes" if args.tls else "no",
            suffix,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
