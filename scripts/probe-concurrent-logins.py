#!/usr/bin/env python3
"""Prove one external and one same-host local game login can coexist."""

import argparse
import getpass
import ipaddress
import json
import os
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts" / "lib"))

from game_login_probe import LoginProbeError, login_socket  # noqa: E402


def fail(message):
    raise SystemExit("concurrent login probe failed: {}".format(message))


def close_socket_quietly(sock):
    if sock is None:
        return
    try:
        sock.close()
    except OSError:
        pass


def validate_local_host(host):
    value = str(host or "").strip()
    if value != str(host or "") or not value:
        fail("--local-host must be localhost or a loopback IP address")
    if any(ord(ch) < 32 for ch in value):
        fail("--local-host must not contain control characters")
    if value.lower() == "localhost":
        return value
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        fail("--local-host must be localhost or a loopback IP address")
    if not address.is_loopback:
        fail("--local-host must be localhost or a loopback IP address")
    return value


def password_from_env_or_prompt(username, env_name, label):
    if env_name:
        value = os.environ.get(env_name)
        if value is None:
            fail("environment variable {} is not set".format(env_name))
        return value
    return getpass.getpass("Password for {} {}: ".format(label, username))


def accepted(result, label):
    return result.get("status") == 2


def probe_concurrent_logins(external_host, external_port, external_username, external_password,
        local_host, local_port, local_username, local_password, timeout=4.0,
        external_tls=False, tls_sni_host="", allow_untrusted_tls=False, hold_seconds=0.0):
    local_host = validate_local_host(local_host)
    external_sock = None
    local_sock = None
    try:
        external_sock, external_result = login_socket(
            external_host,
            external_port,
            external_username,
            external_password,
            timeout=timeout,
            use_tls=external_tls,
            tls_sni_host=tls_sni_host,
            allow_untrusted_tls=allow_untrusted_tls,
        )
        if not accepted(external_result, "external"):
            fail("external login rejected {} at {}:{} with status {} ({})".format(
                external_username,
                external_host,
                external_port,
                external_result.get("status"),
                external_result.get("statusName"),
            ))
        local_sock, local_result = login_socket(
            local_host,
            local_port,
            local_username,
            local_password,
            timeout=timeout,
            use_tls=False,
        )
        if not accepted(local_result, "local"):
            fail("local login rejected {} at {}:{} with status {} ({})".format(
                local_username,
                local_host,
                local_port,
                local_result.get("status"),
                local_result.get("statusName"),
            ))
        if hold_seconds > 0:
            time.sleep(hold_seconds)
        return {
            "success": True,
            "external": external_result,
            "local": local_result,
            "summary": (
                "concurrent game logins accepted external {} at {}:{} tls={} "
                "and local {} at {}:{} tls=no"
            ).format(
                external_username,
                external_host,
                int(external_port),
                "yes" if external_tls else "no",
                local_username,
                local_host,
                int(local_port),
            ),
        }
    except (OSError, LoginProbeError) as exc:
        fail(str(exc))
    finally:
        close_socket_quietly(local_sock)
        close_socket_quietly(external_sock)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Probe that an external game login and a same-host local game login can stay "
            "open concurrently without launching GUI clients."
        )
    )
    parser.add_argument("--external-host", required=True,
            help="External game host or TLS tunnel endpoint.")
    parser.add_argument("--external-port", type=int, default=43594,
            help="External game port.")
    parser.add_argument("--external-username", required=True)
    parser.add_argument("--external-password-env", default="",
            help="Read the external password from this environment variable. If omitted, prompt securely.")
    parser.add_argument("--local-host", default="127.0.0.1",
            help="Same-host local game host. Must be localhost or a loopback IP address.")
    parser.add_argument("--local-port", type=int, default=43594,
            help="Same-host local game port.")
    parser.add_argument("--local-username", required=True)
    parser.add_argument("--local-password-env", default="",
            help="Read the local password from this environment variable. If omitted, prompt securely.")
    parser.add_argument("--tls", action="store_true",
            help="Wrap only the external socket in TLS. Use for client_tls_tunnel public endpoints.")
    parser.add_argument("--tls-sni-host", default="",
            help="SNI/hostname for --tls. Defaults to --external-host.")
    parser.add_argument("--allow-untrusted-tls", action="store_true",
            help="Allow self-signed or otherwise untrusted TLS certificates for private tunnel tests.")
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--hold-seconds", type=float, default=0.0,
            help="Keep both successful login sockets open briefly before closing them.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.external_port < 1 or args.external_port > 65535:
        fail("--external-port must be between 1 and 65535")
    if args.local_port < 1 or args.local_port > 65535:
        fail("--local-port must be between 1 and 65535")
    if args.hold_seconds < 0:
        fail("--hold-seconds must be non-negative")

    external_password = password_from_env_or_prompt(
        args.external_username, args.external_password_env, "external")
    local_password = password_from_env_or_prompt(
        args.local_username, args.local_password_env, "local")
    result = probe_concurrent_logins(
        args.external_host,
        args.external_port,
        args.external_username,
        external_password,
        args.local_host,
        args.local_port,
        args.local_username,
        local_password,
        timeout=args.timeout,
        external_tls=args.tls,
        tls_sni_host=args.tls_sni_host,
        allow_untrusted_tls=args.allow_untrusted_tls,
        hold_seconds=args.hold_seconds,
    )
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("ok: {}".format(result["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
