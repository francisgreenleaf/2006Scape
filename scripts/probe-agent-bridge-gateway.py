#!/usr/bin/env python3
"""Probe a public agent bridge gateway without logging in or mutating gameplay."""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlparse


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def fail(message: str) -> None:
    raise SystemExit("agent bridge gateway probe failed: {}".format(message))


def normalize_gateway_url(value: str, allow_http_for_test: bool = False) -> str:
    text = str(value or "").strip().rstrip("/")
    if not text:
        fail("--gateway-url is required")
    if any(ord(ch) < 32 for ch in text):
        fail("--gateway-url must be a single-line URL")
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        fail("--gateway-url must be an http(s) base URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail("--gateway-url must not include user info, query, or fragment")
    if parsed.scheme != "https" and (parsed.hostname or "").lower() not in LOCAL_HOSTS and not allow_http_for_test:
        fail("public agent bridge gateways must use HTTPS")
    return text


def http_json(method: str, url: str, payload: dict | None, timeout: float,
        allow_untrusted_tls: bool) -> tuple[int, dict, str]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    context = None
    if allow_untrusted_tls and url.lower().startswith("https://"):
        context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read().decode("utf-8", errors="replace")
            status = response.getcode()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except urllib.error.URLError as exc:
        fail("{} {} failed: {}".format(method, url, exc.reason))
    if not body:
        return status, {}, ""
    try:
        return status, json.loads(body), body
    except json.JSONDecodeError:
        return status, {}, body[:500]


def can_connect(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_gateway(gateway_url: str, raw_host: str = "", raw_port: int = 43610,
        timeout: float = 3.0, allow_http_for_test: bool = False,
        allow_untrusted_tls: bool = False) -> dict:
    base = normalize_gateway_url(gateway_url, allow_http_for_test=allow_http_for_test)
    parsed = urlparse(base)
    checks: list[str] = []

    status, body, raw = http_json("GET", base + "/agent/health", None, timeout, allow_untrusted_tls)
    if status != 200 or not body.get("ok"):
        fail("/agent/health did not return ok JSON: status={} body={}".format(status, raw[:200] or body))
    checks.append("gateway health ok {}".format(base))

    status, body, raw = http_json("POST", base + "/agent/session/claim", {"nonce": "probe-missing"}, timeout, allow_untrusted_tls)
    if status not in (404, 429):
        fail("/agent/session/claim should be reachable but fail closed for missing nonce; got status={} body={}".format(status, raw[:200] or body))
    checks.append("gateway claim endpoint reachable and fail-closed status={}".format(status))

    status, body, raw = http_json("GET", base + "/agent/not-approved", None, timeout, allow_untrusted_tls)
    if status not in (403, 404, 405):
        fail("unapproved /agent path should be rejected; got status={} body={}".format(status, raw[:200] or body))
    checks.append("gateway rejects unapproved /agent path status={}".format(status))

    external_raw_host = raw_host or parsed.hostname or ""
    if not external_raw_host:
        fail("could not determine raw bridge host")
    if can_connect(external_raw_host, raw_port, timeout):
        fail("raw bridge port {} is reachable at {}; do not expose it".format(raw_port, external_raw_host))
    checks.append("raw bridge TCP not reachable {}:{}".format(external_raw_host, raw_port))
    return {
        "success": True,
        "gatewayUrl": base,
        "rawHost": external_raw_host,
        "rawPort": raw_port,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check an HTTPS /agent gateway and confirm raw 43610 is not exposed."
    )
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--raw-host", default="", help="Host to test for raw bridge exposure. Defaults to gateway host.")
    parser.add_argument("--raw-port", type=int, default=43610)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--allow-http-for-test", action="store_true")
    parser.add_argument("--allow-untrusted-tls", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.timeout <= 0:
        fail("--timeout must be positive")
    if args.raw_port <= 0 or args.raw_port > 65535:
        fail("--raw-port must be between 1 and 65535")
    result = probe_gateway(
        args.gateway_url,
        raw_host=args.raw_host,
        raw_port=args.raw_port,
        timeout=args.timeout,
        allow_http_for_test=args.allow_http_for_test,
        allow_untrusted_tls=args.allow_untrusted_tls,
    )
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        for check in result["checks"]:
            print("gateway-check: {}".format(check))
        print("ok: agent bridge gateway probe passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
