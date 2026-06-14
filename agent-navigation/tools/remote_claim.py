#!/usr/bin/env python3
"""Claim a remote 2006Scape agent bridge session for repo-side tools."""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from profile_utils import (
    normalize_player_name,
    resolve_profile,
    safe_profile,
    session_file_for_profile,
)


CLAIM_TIMEOUT_SECONDS = 30.0
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_claim_code() -> str:
    raw = base64.b32encode(secrets.token_bytes(8)).decode("ascii").rstrip("=")
    return "{}-{}-{}".format(raw[:4], raw[4:8], raw[8:12])


def normalize_bridge_url(value: str, allow_http_for_test: bool = False) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("bridge URL is required")
    if any(ord(ch) < 32 for ch in text):
        raise ValueError("bridge URL must be a single-line URL")
    text = text.rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("bridge URL must be an http(s) base URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("bridge URL must not include user info, query, or fragment")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" and host not in LOCAL_HOSTS and not allow_http_for_test:
        raise ValueError("remote bridge URLs must use HTTPS")
    return text


def endpoint(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def json_request(method: str, url: str, payload: dict | None = None,
        token: str = "", timeout: float = 4.0) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["X-Agent-Token"] = token
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            status = response.getcode()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    if not body:
        return status, {}
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = {"success": False, "message": body[:500]}
    return status, parsed


def wait_for_claim(base_url: str, nonce: str, timeout_seconds: float,
        poll_interval: float) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last_message = ""
    while time.monotonic() < deadline:
        status, response = json_request("POST", endpoint(base_url, "/agent/session/claim"), {"nonce": nonce})
        if status == 200 and response.get("success") and response.get("token"):
            return response
        last_message = str(response.get("message") or response.get("error") or "HTTP {}".format(status))
        time.sleep(max(0.2, poll_interval))
    raise RuntimeError("claim timed out before the server accepted it: {}".format(last_message))


def verify_observe_xxs(base_url: str, token: str) -> dict:
    status, response = json_request(
        "POST",
        endpoint(base_url, "/agent/tool"),
        {"tool": "observe_state_XXS", "arguments": {}},
        token=token,
        timeout=8.0,
    )
    if status != 200 or not response.get("success"):
        raise RuntimeError("observe_state_XXS verification failed: {}".format(
            response.get("message") or response.get("error") or "HTTP {}".format(status)
        ))
    return response


def write_session_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(text)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(str(tmp), str(path))


def sanitized_session_summary(path: Path, payload: dict, verified: bool) -> dict:
    return {
        "success": True,
        "profile": payload.get("profile"),
        "playerName": payload.get("playerName"),
        "sessionId": payload.get("sessionId"),
        "bridgeUrl": payload.get("bridgeUrl"),
        "sessionFile": str(path),
        "verifiedObserveXXS": verified,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Claim a remote 2006Scape agent bridge session and write the profile-scoped session file."
    )
    parser.add_argument("--profile", default=resolve_profile(default=""),
            help="Character/profile name. Defaults to RS_PROFILE/RSBRIDGE_PROFILE or MrFlame.")
    parser.add_argument("--bridge-url", default=os.environ.get("AGENT_BRIDGE_URL") or os.environ.get("RSBRIDGE_URL") or "",
            help="HTTPS base URL for the operator agent gateway, for example https://agents.example.com")
    parser.add_argument("--nonce", default="", help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=float, default=CLAIM_TIMEOUT_SECONDS)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--session-file", default="", help="Override the output session file path.")
    parser.add_argument("--allow-http-for-test", action="store_true",
            help="Allow non-local http:// bridge URLs. Use only for local tests.")
    parser.add_argument("--verify", action="store_true",
            help="After claim, run a harmless observe_state_XXS through the remote bridge.")
    parser.add_argument("--json", action="store_true", help="Print a token-redacted JSON summary.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    profile = resolve_profile(args.profile)
    bridge_url = normalize_bridge_url(args.bridge_url, allow_http_for_test=args.allow_http_for_test)
    nonce = args.nonce or generate_claim_code()
    session_file = Path(args.session_file).expanduser() if args.session_file else session_file_for_profile(profile)
    expected = normalize_player_name(profile)

    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.poll_interval <= 0:
        raise SystemExit("--poll-interval must be positive")

    if not args.json:
        print("Remote 2006Scape agent claim for profile {}.".format(profile))
        print("Type this exact command in the logged-in game client within {:.0f} seconds:".format(args.timeout))
        print()
        print("  ::agent claim {}".format(nonce))
        print()
        print("If that command is not available on the running server, type:")
        print("  ::agentbridge claim {}".format(nonce))
        print()
        sys.stdout.flush()

    claim = wait_for_claim(bridge_url, nonce, args.timeout, args.poll_interval)
    actual = normalize_player_name(claim.get("playerName"))
    if expected and actual and expected != actual:
        raise RuntimeError("claimed player mismatch: expected {} but server returned {}".format(profile, claim.get("playerName")))

    payload = {
        "bridgeUrl": bridge_url,
        "createdAt": utc_now(),
        "playerId": claim.get("playerId"),
        "playerName": claim.get("playerName"),
        "profile": profile,
        "profileKey": safe_profile(profile),
        "sessionId": claim.get("sessionId"),
        "source": "remote_claim.py",
        "token": claim.get("token"),
    }
    write_session_file(session_file, payload)

    verified = False
    if args.verify:
        verify_observe_xxs(bridge_url, payload["token"])
        verified = True

    summary = sanitized_session_summary(session_file, payload, verified)
    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print("Claimed remote bridge session for {}.".format(summary["playerName"]))
        print("Session file: {}".format(session_file))
        if verified:
            print("Verified observe_state_XXS through the remote bridge.")
        else:
            print("Run with --verify to prove observe_state_XXS through the remote bridge.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
