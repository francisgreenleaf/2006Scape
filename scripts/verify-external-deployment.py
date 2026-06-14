#!/usr/bin/env python3
"""Verify external-player deployment artifacts without starting the server."""

import argparse
import base64
import binascii
import hashlib
import ipaddress
import json
import os
import re
import socket
import ssl
import stat
import subprocess
import sys
import time
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts" / "lib"))

from discord_bot_probe import DiscordProbeError, probe_discord_bots  # noqa: E402
from deployment_proof_manifest import validate_proof_manifest_template  # noqa: E402
from game_login_probe import LoginProbeError, create_tls_client_context, login_socket, probe_login  # noqa: E402

MIN_EXTERNAL_PBKDF2_ITERATIONS = 120000
MIN_PASSWORD_LENGTH = 12
MIN_PASSWORD_POLICY_VERSION = 1
AGENT_BRIDGE_PORT = 43610
ACCOUNT_USERNAME_RE = re.compile(r"[a-z0-9 .]{1,12}")
ACCOUNT_ROLE_RE = re.compile(r"[A-Za-z0-9_.:-]{1,32}")
DISCORD_USER_ID_RE = re.compile(r"\d{15,25}")
SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")
DEPLOYMENT_PATH_RE = re.compile(r"^/[A-Za-z0-9._@:+,=/-]+$")
BASE_EXPECTED_CLIENT_FILES = {
    "2006scape-client.jar",
    "Check-Setup.command",
    "Run-2006Scape.command",
    "client.properties",
    "check-setup-macos-linux.sh",
    "check-setup-windows.bat",
    "MANIFEST.txt",
    "SHA256SUMS",
    "run-macos-linux.sh",
    "run-windows.bat",
    "README.txt",
}
CLIENT_TLS_TUNNEL_CLIENT_FILES = {
    "client-tls-tunnel/README.txt",
    "client-tls-tunnel/stunnel-client.conf",
}
PLACEHOLDER_DISCORD_VALUES = {
    "REPLACE_WITH_DISCORD_BOT_TOKEN",
    "DISCORD_BOT_TOKEN",
    "123456789012345678",
}
PLACEHOLDER_NETWORK_VALUES = {
    "example-tailnet-host",
    "example-vpn-host",
    "example-server",
    "server.example.com",
    "100.64.0.10",
    "REPLACE_WITH_TAILSCALE_IP",
    "REPLACE_WITH_WIREGUARD_IP",
    "REPLACE_WITH_PUBLIC_GAME_HOST",
    "REPLACE_WITH_PUBLIC_INTERFACE_IP",
}


def fail(message):
    raise SystemExit("deployment verification failed: {}".format(message))


def warn(warnings, message):
    warnings.append(message)


def load_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        fail("could not read {}: {}".format(path, exc))
    except json.JSONDecodeError as exc:
        fail("invalid JSON in {}: {}".format(path, exc))


def read_key_values(path):
    values = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        fail("could not read {}: {}".format(path, exc))
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def sha256_file(path):
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        fail("could not read {}: {}".format(path, exc))
    return digest.hexdigest()


def require_key(values, key, label):
    value = values.get(key)
    if not value:
        fail("{} is missing {}".format(label, key))
    return value


def require_no_control_chars(value, label):
    if any(ord(ch) < 32 for ch in str(value)):
        fail("{} must be a single-line value without control characters".format(label))


def validate_live_local_host(value):
    clean = str(value or "").strip()
    if clean != str(value or "") or not clean:
        fail("--live-local-host must be localhost or a loopback IP address for same-host local login proof")
    require_no_control_chars(clean, "--live-local-host")
    if clean.lower() == "localhost":
        return clean
    try:
        if ipaddress.ip_address(clean).is_loopback:
            return clean
    except ValueError:
        pass
    fail("--live-local-host must be localhost or a loopback IP address for same-host local login proof")


def validate_tls_sni_host(value, allow_placeholders):
    clean = str(value or "").strip()
    if not clean:
        return ""
    if clean != str(value or ""):
        fail("--tls-sni-host must not contain leading or trailing whitespace")
    require_no_control_chars(clean, "--tls-sni-host")
    validate_not_placeholder_network_value(clean, "--tls-sni-host", allow_placeholders)
    lower = clean.lower()
    if lower in {"localhost", "127.0.0.1", "::1", "0.0.0.0", "::", "*"}:
        fail("--tls-sni-host must be a specific non-loopback, non-wildcard certificate host")
    try:
        if ipaddress.ip_address(clean).is_loopback:
            fail("--tls-sni-host must be a specific non-loopback, non-wildcard certificate host")
    except ValueError:
        pass
    return clean


def validate_service_name(value, label):
    clean = str(value or "").strip()
    if clean != str(value or "") or SERVICE_NAME_RE.fullmatch(clean) is None:
        fail("{} must be a simple service user/group name, got {!r}".format(label, value))
    return clean


def validate_deployment_path(value, label, allow_root=False):
    clean = str(value or "").strip()
    if clean != str(value or ""):
        fail("{} must not contain leading or trailing whitespace, got {!r}".format(label, value))
    if DEPLOYMENT_PATH_RE.fullmatch(clean) is None:
        fail("{} must be an absolute path with simple characters and no whitespace/control chars, got {!r}".format(
            label,
            value,
        ))
    if clean == "/" and not allow_root:
        fail("{} must not be the filesystem root".format(label))
    return clean


def require_file(path, label):
    if not path.is_file():
        fail("{} is missing: {}".format(label, path))


def require_not_symlink(path, label):
    if path.is_symlink():
        fail("{} must not be a symlink: {}".format(label, path))


def require_executable(path, label):
    require_file(path, label)
    if not path.stat().st_mode & 0o111:
        fail("{} is not executable: {}".format(label, path))


def require_directory(path, label):
    if not path.is_dir():
        fail("{} is missing: {}".format(label, path))


def require_not_executable(path, label):
    require_file(path, label)
    if path.stat().st_mode & 0o111:
        fail("{} should not be executable: {}".format(label, path))


def require_text(path, label, expected):
    require_file(path, label)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail("could not read {} {}: {}".format(label, path, exc))
    if expected not in text:
        fail("{} is missing required text {!r}: {}".format(label, expected, path))


def require_crlf_line_endings(path, label):
    require_file(path, label)
    try:
        data = path.read_bytes()
    except OSError as exc:
        fail("could not read {} {}: {}".format(label, path, exc))
    if b"\r\n" not in data or b"\n" in data.replace(b"\r\n", b""):
        fail("{} must use CRLF line endings for Windows compatibility: {}".format(label, path))


def verify_owner_only_permissions(path, label, allow_executable):
    if os.name != "posix":
        return
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        fail("could not inspect {} permissions {}: {}".format(label, path, exc))
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        fail("{} permissions must be owner-only, got {:03o}: {}".format(label, mode, path))
    if not allow_executable and mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        fail("{} must not be executable, got {:03o}: {}".format(label, mode, path))


def string_value(data, key, fallback=""):
    value = data.get(key, fallback)
    return "" if value is None else str(value).strip()


def string_values(data, plural_key, singular_key, fallback=""):
    raw = data.get(plural_key)
    values = []
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, str):
        values = raw.split(",")
    if not values:
        values = [data.get(singular_key, fallback)]
    output = []
    for value in values:
        clean = str(value or "").strip()
        if clean:
            output.append(clean)
    return output


def account_username(value):
    if not isinstance(value, str):
        return ""
    normalized = value.strip().lower()
    return normalized if ACCOUNT_USERNAME_RE.fullmatch(normalized) else ""


def account_file_name(username):
    return re.sub(r"[^a-z0-9._-]", "_", username.replace(" ", "_")) + ".json"


def validate_account_string_list(record, key, record_path, item_label, validator):
    if key not in record:
        return
    value = record.get(key)
    if not isinstance(value, list):
        fail("account record {} field must be an array: {}".format(key, record_path))
    for index, item in enumerate(value):
        if not isinstance(item, str):
            fail("account record {}[{}] must be a string: {}".format(key, index, record_path))
        clean = item.strip()
        if not clean:
            fail("account record {}[{}] must not be empty: {}".format(key, index, record_path))
        if not validator(clean):
            fail("account record {}[{}] has invalid {}: {}".format(key, index, item_label, record_path))


def validate_account_metadata(record, record_path):
    validate_account_string_list(
        record,
        "roles",
        record_path,
        "role",
        lambda value: ACCOUNT_ROLE_RE.fullmatch(value) is not None,
    )
    validate_account_string_list(
        record,
        "allowedCharacters",
        record_path,
        "character name",
        lambda value: account_username(value) != "",
    )
    if "discordUserId" in record:
        value = record.get("discordUserId")
        if not isinstance(value, str) or not value.strip():
            fail("account record discordUserId must be a non-empty string: {}".format(record_path))
        if DISCORD_USER_ID_RE.fullmatch(value.strip()) is None:
            fail("account record discordUserId must be a numeric Discord snowflake string: {}".format(record_path))
    validate_account_password_policy(record, record_path)


def validate_account_password_policy(record, record_path):
    policy = record.get("passwordPolicy")
    if not isinstance(policy, dict):
        fail("account record passwordPolicy must be an object created by scripts/create-account.py: {}".format(record_path))
    if int_value(policy, "version", 0) < MIN_PASSWORD_POLICY_VERSION:
        fail("account record passwordPolicy.version must be at least {}: {}".format(
            MIN_PASSWORD_POLICY_VERSION, record_path))
    if int_value(policy, "minLength", 0) < MIN_PASSWORD_LENGTH:
        fail("account record passwordPolicy.minLength must be at least {}: {}".format(
            MIN_PASSWORD_LENGTH, record_path))
    allow_weak = policy.get("allowWeakPassword", False)
    if not isinstance(allow_weak, bool):
        fail("account record passwordPolicy.allowWeakPassword must be a boolean: {}".format(record_path))
    if allow_weak:
        fail("account record passwordPolicy must not allow weak passwords: {}".format(record_path))


def decode_account_base64(record, key, record_path, expected_length):
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        fail("account record has no {}: {}".format(key, record_path))
    try:
        decoded = base64.b64decode(value.strip(), validate=True)
    except (binascii.Error, ValueError):
        fail("account record has invalid base64 {}: {}".format(key, record_path))
    if len(decoded) != expected_length:
        fail("account record {} must decode to {} bytes: {}".format(key, expected_length, record_path))
    return decoded


def first_present(data, keys):
    for key in keys:
        if key in data:
            return key, data.get(key)
    return "", None


def discord_string(bot, index, keys, label, required):
    key, value = first_present(bot, keys)
    if not key:
        if required:
            fail("agent-discord-bots[{}] needs {}".format(index, label))
        return ""
    if not isinstance(value, str):
        fail("agent-discord-bots[{}].{} must be a string".format(index, key))
    clean = value.strip()
    if required and not clean:
        fail("agent-discord-bots[{}].{} must not be empty".format(index, key))
    return clean


def validate_discord_allow_list(bot, index, camel_key, snake_key):
    key, value = first_present(bot, (camel_key, snake_key))
    if not key:
        return
    if isinstance(value, str):
        names = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        names = []
        for item_index, item in enumerate(value):
            if not isinstance(item, str):
                fail("agent-discord-bots[{}].{}[{}] must be a string".format(index, key, item_index))
            names.append(item.strip())
    else:
        fail("agent-discord-bots[{}].{} must be a string or array of strings".format(index, key))
    if not [name for name in names if name]:
        fail("agent-discord-bots[{}].{} is empty; omit it for open routing".format(index, key))


def validate_discord_bool(bot, index, camel_key, snake_key):
    key, value = first_present(bot, (camel_key, snake_key))
    if key and not isinstance(value, bool):
        fail("agent-discord-bots[{}].{} must be a boolean".format(index, key))


def validate_not_placeholder_discord_secret(value, index, label, allow_placeholders):
    if allow_placeholders:
        return
    clean = value.strip()
    upper = clean.upper()
    if clean in PLACEHOLDER_DISCORD_VALUES or upper.startswith("REPLACE_") or "PLACEHOLDER" in upper:
        fail("agent-discord-bots[{}].{} still contains a placeholder value".format(index, label))


def validate_not_placeholder_network_value(value, label, allow_placeholders):
    if allow_placeholders:
        return
    clean = str(value or "").strip()
    if not clean:
        return
    lower = clean.lower()
    upper = clean.upper()
    known_placeholders = {item.lower() for item in PLACEHOLDER_NETWORK_VALUES}
    if lower in known_placeholders or upper.startswith("REPLACE_") or "PLACEHOLDER" in upper:
        fail("{} still contains a placeholder network value: {}".format(label, clean))


def verify_network_placeholders(config, allow_placeholders):
    validate_not_placeholder_network_value(
        string_value(config, "public_game_host"),
        "public_game_host",
        allow_placeholders,
    )
    for key, values in (
        ("game_bind_hosts", string_values(config, "game_bind_hosts", "game_bind_host", "")),
        ("http_bind_hosts", string_values(config, "http_bind_hosts", "http_bind_host", "")),
        ("jaggrab_bind_hosts", string_values(config, "jaggrab_bind_hosts", "jaggrab_bind_host", "")),
        ("client_connect_host", [string_value(config, "client_connect_host")]),
        ("client_tls_tunnel_server_accept_host", [string_value(config, "client_tls_tunnel_server_accept_host")]),
    ):
        for value in values:
            validate_not_placeholder_network_value(value, key, allow_placeholders)


def int_value(data, key, fallback):
    try:
        return int(data.get(key, fallback))
    except (TypeError, ValueError):
        fail("{} must be an integer".format(key))


def expect_equal(actual, expected, label):
    if str(actual) != str(expected):
        fail("{} mismatch: expected {}, got {}".format(label, expected, actual))


def effective_client_host(config):
    mode = string_value(config, "external_transport_mode").lower()
    if mode == "client_tls_tunnel":
        return string_value(config, "client_connect_host", "127.0.0.1") or "127.0.0.1"
    return string_value(config, "public_game_host")


def expected_client_files(config):
    expected = set(BASE_EXPECTED_CLIENT_FILES)
    if string_value(config, "external_transport_mode").lower() == "client_tls_tunnel":
        expected.update(CLIENT_TLS_TUNNEL_CLIENT_FILES)
    return expected


def expected_client_dirs(expected_files):
    dirs = set()
    for relative in expected_files:
        parent = Path(relative).parent
        while str(parent) not in ("", "."):
            dirs.add(str(parent).rstrip("/") + "/")
            parent = parent.parent
    return dirs


def require_no_symlink_under(path, label, root):
    current = Path(path)
    root = Path(root)
    while True:
        if current.is_symlink():
            fail("{} must not be or contain a symlinked path: {}".format(label, current))
        if current == root or current.parent == current:
            return
        current = current.parent


def run_preflight(config_path, allow_wildcard_bind):
    command = [sys.executable, str(ROOT_DIR / "scripts" / "preflight-external-config.py"), str(config_path)]
    if allow_wildcard_bind:
        command.append("--allow-wildcard-bind")
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if completed.returncode != 0:
        output = (completed.stdout + completed.stderr).strip()
        fail("preflight failed for {}{}{}".format(config_path, ": " if output else "", output))


def verify_client_package(config, config_path, client_dist, warnings):
    require_directory(client_dist, "client distribution directory")
    require_not_symlink(client_dist, "client distribution directory")
    for relative in sorted(expected_client_files(config)):
        require_no_symlink_under(client_dist / relative, "client package file", client_dist)
    require_file(client_dist / "2006scape-client.jar", "client jar")
    require_file(client_dist / "client.properties", "client properties")
    require_file(client_dist / "MANIFEST.txt", "client manifest")
    require_file(client_dist / "SHA256SUMS", "client checksums")
    require_executable(client_dist / "Check-Setup.command", "macOS setup checker wrapper")
    require_executable(client_dist / "Run-2006Scape.command", "macOS launcher wrapper")
    require_executable(client_dist / "check-setup-macos-linux.sh", "macOS/Linux setup checker")
    require_file(client_dist / "check-setup-windows.bat", "Windows setup checker")
    require_executable(client_dist / "run-macos-linux.sh", "macOS/Linux launcher")
    require_file(client_dist / "run-windows.bat", "Windows launcher")
    reject_unexpected_client_files(config, client_dist)
    verify_client_package_text(config, client_dist)

    properties = read_key_values(client_dist / "client.properties")
    manifest = read_key_values(client_dist / "MANIFEST.txt")
    expected_client_host = effective_client_host(config)
    expect_equal(properties.get("server.host", ""), expected_client_host, "client server.host")
    expect_equal(properties.get("server.port", ""), int_value(config, "game_port", 43594), "client server.port")
    expect_equal(properties.get("server.world", ""), int_value(config, "world_id", 1), "client server.world")
    expect_equal(properties.get("http.port", ""), int_value(config, "http_port", 8080), "client http.port")
    expect_equal(properties.get("jaggrab.port", ""), int_value(config, "jaggrab_port", 43595), "client jaggrab.port")
    expect_equal(properties.get("secure.transport", ""), string_value(config, "external_transport_mode"), "client secure.transport")

    expect_equal(manifest.get("server_host", ""), expected_client_host, "manifest server_host")
    expect_equal(
        manifest.get("public_game_host", ""),
        string_value(config, "public_game_host"),
        "manifest public_game_host",
    )
    expect_equal(manifest.get("server_port", ""), int_value(config, "game_port", 43594), "manifest server_port")
    expect_equal(manifest.get("http_port", ""), int_value(config, "http_port", 8080), "manifest http_port")
    expect_equal(manifest.get("jaggrab_port", ""), int_value(config, "jaggrab_port", 43595), "manifest jaggrab_port")
    expect_equal(manifest.get("expected_external_transport", ""), string_value(config, "external_transport_mode"), "manifest expected_external_transport")
    if not manifest.get("source_server_config", ""):
        warn(warnings, "client manifest does not record source_server_config")
    expect_equal(
        manifest.get("source_server_config_sha256", ""),
        sha256_file(config_path),
        "manifest source_server_config_sha256",
    )

    verify_checksums(config, client_dist)


def verify_client_package_text(config, client_dist):
    require_text(
        client_dist / "Check-Setup.command",
        "macOS setup checker wrapper",
        "check-setup-macos-linux.sh",
    )
    require_text(
        client_dist / "Run-2006Scape.command",
        "macOS launcher wrapper",
        "run-macos-linux.sh",
    )
    require_text(
        client_dist / "check-setup-macos-linux.sh",
        "macOS/Linux setup checker",
        "Java is required to run 2006Scape",
    )
    require_text(
        client_dist / "check-setup-macos-linux.sh",
        "macOS/Linux setup checker",
        "server.host",
    )
    require_text(
        client_dist / "check-setup-macos-linux.sh",
        "macOS/Linux setup checker",
        "secure.transport",
    )
    require_text(
        client_dist / "check-setup-macos-linux.sh",
        "macOS/Linux setup checker",
        "TCP check",
    )
    require_text(
        client_dist / "check-setup-macos-linux.sh",
        "macOS/Linux setup checker",
        "nc -G 3",
    )
    require_text(
        client_dist / "check-setup-windows.bat",
        "Windows setup checker",
        "Java is required to run 2006Scape",
    )
    require_text(
        client_dist / "check-setup-windows.bat",
        "Windows setup checker",
        "server.host",
    )
    require_text(
        client_dist / "check-setup-windows.bat",
        "Windows setup checker",
        "secure.transport",
    )
    require_text(
        client_dist / "check-setup-windows.bat",
        "Windows setup checker",
        "TCP check",
    )
    require_text(
        client_dist / "check-setup-windows.bat",
        "Windows setup checker",
        "PowerShell",
    )
    require_crlf_line_endings(
        client_dist / "check-setup-windows.bat",
        "Windows setup checker",
    )
    require_text(
        client_dist / "run-macos-linux.sh",
        "macOS/Linux launcher",
        "Java is required to run 2006Scape",
    )
    require_text(
        client_dist / "run-macos-linux.sh",
        "macOS/Linux launcher",
        "-no-java-warnings",
    )
    require_text(
        client_dist / "run-windows.bat",
        "Windows launcher",
        "Java is required to run 2006Scape",
    )
    require_text(
        client_dist / "run-windows.bat",
        "Windows launcher",
        "-no-java-warnings",
    )
    require_crlf_line_endings(
        client_dist / "run-windows.bat",
        "Windows launcher",
    )
    require_text(
        client_dist / "README.txt",
        "client README",
        "double-click Check-Setup.command",
    )
    require_text(
        client_dist / "README.txt",
        "client README",
        "double-click Run-2006Scape.command",
    )
    require_text(
        client_dist / "README.txt",
        "client README",
        "Check setup:",
    )
    require_text(
        client_dist / "README.txt",
        "client README",
        "without logging in",
    )
    require_text(
        client_dist / "README.txt",
        "client README",
        "Install Java 8 or newer",
    )
    require_text(
        client_dist / "README.txt",
        "client README",
        "suppress the legacy Parabot-focused Java-version warning",
    )
    require_text(
        client_dist / "README.txt",
        "client README",
        "expected external transport",
    )
    require_text(
        client_dist / "README.txt",
        "client README",
        "Transport setup:",
    )
    require_text(
        client_dist / "README.txt",
        "client README",
        "public game host",
    )
    require_text(
        client_dist / "README.txt",
        "client README",
        "Use the username and password provided by the server operator",
    )
    require_text(
        client_dist / "README.txt",
        "client README",
        "Do not use a RuneScape.com password or reuse passwords from other services",
    )
    mode = string_value(config, "external_transport_mode").lower()
    if mode == "direct_tcp":
        require_text(
            client_dist / "README.txt",
            "client README",
            "No VPN or client-side tunnel is required",
        )
        require_text(
            client_dist / "README.txt",
            "client README",
            "connects directly",
        )
        require_text(
            client_dist / "README.txt",
            "client README",
            "plaintext TCP",
        )
        require_text(
            client_dist / "README.txt",
            "client README",
            "use a password unique to this 2006Scape server",
        )
    else:
        require_text(
            client_dist / "README.txt",
            "client README",
            "connect that transport first",
        )
    require_text(
        client_dist / "MANIFEST.txt",
        "client manifest",
        "The legacy Java client speaks plaintext",
    )
    require_text(
        client_dist / "MANIFEST.txt",
        "client manifest",
        "External play should use an encrypted transport boundary",
    )
    if mode == "direct_tcp":
        require_text(
            client_dist / "MANIFEST.txt",
            "client manifest",
            "direct_tcp intentionally connects directly over plaintext TCP",
        )
    if mode == "client_tls_tunnel":
        expected_host = effective_client_host(config)
        public_host = string_value(config, "public_game_host")
        game_port = int_value(config, "game_port", 43594)
        require_text(
            client_dist / "run-macos-linux.sh",
            "macOS/Linux launcher",
            "Starting stunnel for encrypted 2006Scape transport",
        )
        require_text(
            client_dist / "run-windows.bat",
            "Windows launcher",
            "Starting stunnel for encrypted 2006Scape transport",
        )
        require_text(
            client_dist / "README.txt",
            "client README",
            "the launchers try to start the bundled",
        )
        require_text(
            client_dist / "client-tls-tunnel" / "README.txt",
            "client TLS tunnel README",
            "it starts this stunnel config",
        )
        require_text(
            client_dist / "client-tls-tunnel" / "README.txt",
            "client TLS tunnel README",
            "The Java client still speaks plaintext to {}".format(expected_host),
        )
        require_text(
            client_dist / "client-tls-tunnel" / "README.txt",
            "client TLS tunnel README",
            "requires TLS handshakes on the public game/cache ports",
        )
        require_text(
            client_dist / "client-tls-tunnel" / "stunnel-client.conf",
            "client stunnel config",
            "verifyChain = yes",
        )
        require_text(
            client_dist / "client-tls-tunnel" / "stunnel-client.conf",
            "client stunnel config",
            "sslVersionMin = TLSv1.2",
        )
        require_text(
            client_dist / "client-tls-tunnel" / "stunnel-client.conf",
            "client stunnel config",
            "checkHost = {}".format(public_host),
        )
        require_text(
            client_dist / "client-tls-tunnel" / "stunnel-client.conf",
            "client stunnel config",
            "accept = {}:{}".format(expected_host, game_port),
        )
        require_text(
            client_dist / "client-tls-tunnel" / "stunnel-client.conf",
            "client stunnel config",
            "connect = {}:{}".format(public_host, game_port),
        )


def verify_client_archive(config, client_dist, archive_path):
    require_file(archive_path, "client archive")
    expected_prefix = client_dist.name + "/"
    expected_files = expected_client_files(config)
    required_entries = {expected_prefix + name for name in expected_files}
    allowed_dirs = {expected_prefix}
    allowed_dirs.update(expected_prefix + name for name in expected_client_dirs(expected_files))
    try:
        with zipfile.ZipFile(str(archive_path), "r") as archive:
            names = set(archive.namelist())
            bad_names = [name for name in names if name.startswith("/") or ".." in Path(name).parts]
            if bad_names:
                fail("client archive contains unsafe path names: {}".format(", ".join(sorted(bad_names)[:5])))
            missing = sorted(required_entries - names)
            if missing:
                fail("client archive is missing entries: {}".format(", ".join(missing)))
            corrupt = archive.testzip()
            if corrupt is not None:
                fail("client archive has a corrupt entry: {}".format(corrupt))
            unexpected = sorted(name for name in names - required_entries - allowed_dirs)
            if unexpected:
                fail("client archive contains unexpected entries: {}".format(", ".join(unexpected[:5])))
            for entry in sorted(required_entries):
                info = archive.getinfo(entry)
                verify_client_archive_permissions(entry, info)
                folder_path = client_dist / entry[len(expected_prefix):]
                folder_digest = hashlib.sha256(folder_path.read_bytes()).hexdigest()
                archive_digest = hashlib.sha256(archive.read(entry)).hexdigest()
                if folder_digest != archive_digest:
                    fail("client archive entry does not match packaged folder file: {}".format(entry))
    except zipfile.BadZipFile:
        fail("client archive is not a valid zip file: {}".format(archive_path))


def verify_server_deployment(config, server_deployment_dir):
    if server_deployment_dir is None:
        return
    require_directory(server_deployment_dir, "server deployment directory")
    require_not_symlink(server_deployment_dir, "server deployment directory")
    config_copy = server_deployment_dir / "ServerConfig.json"
    service = server_deployment_dir / "2006scape-server.service"
    env_file = server_deployment_dir / "2006scape-server.env"
    firewall = server_deployment_dir / "firewall-ufw-example.sh"
    readme = server_deployment_dir / "README.md"
    proof_manifest_template = server_deployment_dir / "proof-templates" / "deployment-proof-manifest.json"
    desktop_proof_template = server_deployment_dir / "proof-templates" / "desktop-client-proof.md"
    backup_proof_template = server_deployment_dir / "proof-templates" / "runtime-data-backup-proof.md"

    for path, label in (
        (config_copy, "server deployment config copy"),
        (service, "server deployment systemd unit"),
        (env_file, "server deployment environment file"),
        (firewall, "server deployment firewall helper"),
        (readme, "server deployment README"),
        (proof_manifest_template, "deployment proof manifest template"),
        (desktop_proof_template, "desktop client proof template"),
        (backup_proof_template, "runtime data backup proof template"),
    ):
        require_not_symlink(path, label)
    require_file(config_copy, "server deployment config copy")
    require_file(service, "server deployment systemd unit")
    require_file(env_file, "server deployment environment file")
    require_executable(firewall, "server deployment firewall helper")
    require_file(readme, "server deployment README")
    require_file(proof_manifest_template, "deployment proof manifest template")
    require_file(desktop_proof_template, "desktop client proof template")
    require_file(backup_proof_template, "runtime data backup proof template")
    require_not_executable(service, "server deployment systemd unit")
    require_not_executable(env_file, "server deployment environment file")
    require_not_executable(readme, "server deployment README")
    require_not_executable(proof_manifest_template, "deployment proof manifest template")
    require_not_executable(desktop_proof_template, "desktop client proof template")
    require_not_executable(backup_proof_template, "runtime data backup proof template")

    copied_config = load_json(config_copy)
    if copied_config != config:
        fail("server deployment ServerConfig.json does not match --config")

    require_text(service, "server deployment systemd unit", "ExecStart=")
    require_text(service, "server deployment systemd unit", "scripts/start-server.sh")
    require_text(service, "server deployment systemd unit", "EnvironmentFile=")
    require_text(service, "server deployment systemd unit", "Restart=on-failure")
    require_text(service, "server deployment systemd unit", "AmbientCapabilities=")
    require_text(service, "server deployment systemd unit", "CapabilityBoundingSet=")
    require_text(service, "server deployment systemd unit", "NoNewPrivileges=true")
    require_text(service, "server deployment systemd unit", "PrivateDevices=true")
    require_text(service, "server deployment systemd unit", "PrivateTmp=true")
    require_text(service, "server deployment systemd unit", "ProtectControlGroups=true")
    require_text(service, "server deployment systemd unit", "ProtectSystem=full")
    require_text(service, "server deployment systemd unit", "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX")
    require_text(service, "server deployment systemd unit", "RestrictSUIDSGID=true")
    require_text(service, "server deployment systemd unit", "SystemCallArchitectures=native")
    service_text = service.read_text(encoding="utf-8")
    if "ReadWritePaths" in service_text:
        fail("server deployment systemd unit should not contain brittle ReadWritePaths entries")

    service_values = read_key_values(service)
    service_user = validate_service_name(
        require_key(service_values, "User", "server deployment systemd unit"),
        "server deployment systemd unit User",
    )
    service_group = validate_service_name(
        require_key(service_values, "Group", "server deployment systemd unit"),
        "server deployment systemd unit Group",
    )
    working_directory = validate_deployment_path(
        require_key(service_values, "WorkingDirectory", "server deployment systemd unit"),
        "server deployment systemd unit WorkingDirectory",
    ).rstrip("/")
    environment_file = validate_deployment_path(
        require_key(service_values, "EnvironmentFile", "server deployment systemd unit"),
        "server deployment systemd unit EnvironmentFile",
    )
    exec_start = validate_deployment_path(
        require_key(service_values, "ExecStart", "server deployment systemd unit"),
        "server deployment systemd unit ExecStart",
    )
    expect_equal(
        exec_start,
        working_directory + "/scripts/start-server.sh",
        "server deployment systemd ExecStart",
    )
    if service_user == "root" or service_group == "root":
        fail("server deployment systemd unit must not run the server as root")

    env_values = read_key_values(env_file)
    validate_deployment_path(
        require_key(env_values, "JAVA_BIN", "server deployment environment file"),
        "server deployment environment JAVA_BIN",
    )
    server_config_path = validate_deployment_path(
        require_key(env_values, "SERVER_CONFIG", "server deployment environment file"),
        "server deployment environment SERVER_CONFIG",
    )
    validate_deployment_path(
        require_key(env_values, "SERVER_RUN_DIR", "server deployment environment file"),
        "server deployment environment SERVER_RUN_DIR",
    )
    server_java_opts = require_key(env_values, "SERVER_JAVA_OPTS", "server deployment environment file")
    require_no_control_chars(server_java_opts, "server deployment environment SERVER_JAVA_OPTS")
    if not server_java_opts.strip():
        fail("server deployment environment SERVER_JAVA_OPTS must not be empty")
    if server_config_path == environment_file:
        fail("server deployment environment SERVER_CONFIG must not point at the systemd environment file")

    require_text(firewall, "server deployment firewall helper", "Default is dry-run")
    require_text(firewall, "server deployment firewall helper", "Do not expose 2006Scape AgentBridgeServer")
    require_text(firewall, "server deployment firewall helper", str(int_value(config, "agent_bridge_port", AGENT_BRIDGE_PORT)))
    mode = string_value(config, "external_transport_mode").lower()
    if mode == "client_tls_tunnel":
        require_text(firewall, "server deployment firewall helper", "client_tls_tunnel mode")
    elif mode == "direct_tcp":
        require_text(firewall, "server deployment firewall helper", "direct_tcp mode")
    elif mode == "tailscale":
        require_text(firewall, "server deployment firewall helper", "Tailscale mode")
    elif mode in ("wireguard", "vpn"):
        require_text(firewall, "server deployment firewall helper", "VPN mode")

    require_text(readme, "server deployment README", "They do not start or stop a server by themselves.")
    require_text(readme, "server deployment README", "This bundle does not include real `data/secrets.json`")
    require_text(readme, "server deployment README", "## Account And Secret Files")
    require_text(readme, "server deployment README", "2006Scape Server/data/accounts")
    require_text(readme, "server deployment README", "2006Scape Server/data/secrets.json")
    require_text(readme, "server deployment README", "scripts/account-admin.py --accounts-dir")
    require_text(readme, "server deployment README", "--require-password-policy audit")
    require_text(readme, "server deployment README", "scripts/create-account.py --overwrite --preserve-metadata")
    require_text(readme, "server deployment README", "rejects passwords shorter than 12 characters")
    require_text(readme, "server deployment README", "reject missing or weak-override password policy metadata")
    require_text(readme, "server deployment README", "Do not symlink `data/secrets.json` or `data/accounts`")
    require_text(readme, "server deployment README", "## Runtime Data Safety")
    require_text(readme, "server deployment README", "2006Scape Server/data/characters")
    require_text(readme, "server deployment README", "Back up those paths before an intentional remote restart or migration")
    require_text(readme, "server deployment README", "Do not overwrite `data/characters`, `data/accounts`, or `data/secrets.json`")
    require_text(readme, "server deployment README", "scripts/backup-runtime-data.py")
    require_text(readme, "server deployment README", "--runtime-data-backup-proof-file")
    require_text(readme, "server deployment README", "backup archive sha256")
    require_text(readme, "server deployment README", "## Proof Note Templates")
    require_text(readme, "server deployment README", "proof-templates/deployment-proof-manifest.json")
    require_text(readme, "server deployment README", "proof-templates/desktop-client-proof.md")
    require_text(readme, "server deployment README", "proof-templates/runtime-data-backup-proof.md")
    require_text(readme, "server deployment README", "--proof-manifest")
    require_text(readme, "server deployment README", "scripts/check-deployment-proof-manifest.py deployment-proof-manifest.json")
    require_text(readme, "server deployment README", "--secrets")
    require_text(readme, "server deployment README", "--check-files --check-env")
    require_text(readme, "server deployment README", "runtime-backup archive/checksum")
    require_text(readme, "server deployment README", "## Live Chat Proof")
    require_text(readme, "server deployment README", "agent_chat_player_delivery")
    require_text(readme, "server deployment README", "--agent-chat-delivery-log-text")
    require_text(readme, "server deployment README", "After the service is intentionally running")
    require_text(proof_manifest_template, "deployment proof manifest template", "live_login_password_env")
    require_text(proof_manifest_template, "deployment proof manifest template", "live_local_login_password_env")
    require_text(proof_manifest_template, "deployment proof manifest template", "runtime_data_backup_proof_file")
    require_text(proof_manifest_template, "deployment proof manifest template", "agent_chat_delivery_log_text")
    require_text(proof_manifest_template, "deployment proof manifest template", "discord_channel_message_text")
    try:
        proof_manifest_values = validate_proof_manifest_template(
            proof_manifest_template,
            required_fields={
                "live",
                "live_login_username",
                "live_login_password_env",
                "live_local_login_username",
                "live_local_login_password_env",
                "live_reject_login_username",
                "live_reject_login_password_env",
                "live_reject_login_expected_statuses",
                "desktop_client_proof_file",
                "runtime_data_backup_proof_file",
                "agent_chat_delivery_log_text",
                "agent_chat_delivery_log_to_name",
                "require_full_proof",
            },
        )
        if proof_manifest_values.get("require_full_proof") is not True:
            fail("deployment proof manifest template must set require_full_proof=true")
    except ValueError as exc:
        fail("deployment proof manifest template is invalid: {}".format(exc))
    require_text(desktop_proof_template, "desktop client proof template", "LOCAL_USERNAME")
    require_text(desktop_proof_template, "desktop client proof template", "EXTERNAL_USERNAME")
    require_text(desktop_proof_template, "desktop client proof template", "same-host/local Java client")
    require_text(desktop_proof_template, "desktop client proof template", "external Java client")
    require_text(desktop_proof_template, "desktop client proof template", "external transport path")
    require_text(desktop_proof_template, "desktop client proof template", "both desktop clients remained online at the same time")
    require_text(desktop_proof_template, "desktop client proof template", "evidence:")
    require_text(desktop_proof_template, "desktop client proof template", "--desktop-client-proof-file")
    require_text(backup_proof_template, "runtime data backup proof template", "BACKUP_ARCHIVE")
    require_text(backup_proof_template, "runtime data backup proof template", "BACKUP_ARCHIVE_SHA256")
    require_text(backup_proof_template, "runtime data backup proof template", "scripts/backup-runtime-data.py")
    require_text(backup_proof_template, "runtime data backup proof template", "data/characters")
    require_text(backup_proof_template, "runtime data backup proof template", "runtime: not started, stopped, or restarted")
    require_text(backup_proof_template, "runtime data backup proof template", "readiness argument: --runtime-data-backup-proof-file")
    require_text(backup_proof_template, "runtime data backup proof template", "--runtime-data-backup-proof-file")


def verify_client_tls_tunnel_operator(config, tunnel_dir, tls_sni_host, warnings, allow_placeholders):
    mode = string_value(config, "external_transport_mode").lower()
    if tunnel_dir is None:
        if mode == "client_tls_tunnel":
            warn(warnings, "client_tls_tunnel operator stunnel directory was not supplied; use --client-tls-tunnel-dir for static tunnel artifact verification")
        return
    if mode != "client_tls_tunnel":
        fail("--client-tls-tunnel-dir is only valid when external_transport_mode=client_tls_tunnel")
    require_directory(tunnel_dir, "client TLS tunnel operator directory")
    require_not_symlink(tunnel_dir, "client TLS tunnel operator directory")
    expected_files = {
        "README.txt",
        "stunnel-client.conf",
        "stunnel-server.conf",
    }
    unexpected = []
    for path in tunnel_dir.rglob("*"):
        if path.is_dir():
            continue
        relative = str(path.relative_to(tunnel_dir))
        if relative not in expected_files:
            unexpected.append(relative)
    if unexpected:
        fail("client TLS tunnel operator directory contains unexpected files: {}".format(
            ", ".join(sorted(unexpected)[:5])
        ))
    for relative in sorted(expected_files):
        path = tunnel_dir / relative
        require_not_symlink(path, "client TLS tunnel operator file")
        require_file(path, "client TLS tunnel operator file")
        require_not_executable(path, "client TLS tunnel operator file")

    public_host = string_value(config, "public_game_host")
    cert_host = validate_tls_sni_host(tls_sni_host, allow_placeholders) or public_host
    server_accept_host = string_value(
        config,
        "client_tls_tunnel_server_accept_host",
        public_host,
    ) or public_host
    client_host = string_value(config, "client_connect_host", "127.0.0.1") or "127.0.0.1"
    game_port = int_value(config, "game_port", 43594)

    require_text(tunnel_dir / "README.txt", "client TLS tunnel operator README", "server-side tunnel")
    require_text(tunnel_dir / "README.txt", "client TLS tunnel operator README", "remote TLS endpoint: {}".format(public_host))
    require_text(tunnel_dir / "README.txt", "client TLS tunnel operator README", "server-side tunnel accept host: {}".format(server_accept_host))
    require_text(tunnel_dir / "README.txt", "client TLS tunnel operator README", "certificate host checked by stunnel: {}".format(cert_host))
    require_text(tunnel_dir / "README.txt", "client TLS tunnel operator README", "requires TLS handshakes on the public game/cache ports")

    require_text(tunnel_dir / "stunnel-client.conf", "client TLS tunnel client config", "client = yes")
    require_text(tunnel_dir / "stunnel-client.conf", "client TLS tunnel client config", "verifyChain = yes")
    require_text(tunnel_dir / "stunnel-client.conf", "client TLS tunnel client config", "sslVersionMin = TLSv1.2")
    require_text(tunnel_dir / "stunnel-client.conf", "client TLS tunnel client config", "checkHost = {}".format(cert_host))
    require_text(tunnel_dir / "stunnel-client.conf", "client TLS tunnel client config", "accept = {}:{}".format(client_host, game_port))
    require_text(tunnel_dir / "stunnel-client.conf", "client TLS tunnel client config", "connect = {}:{}".format(public_host, game_port))

    require_text(tunnel_dir / "stunnel-server.conf", "client TLS tunnel server config", "client = no")
    require_text(tunnel_dir / "stunnel-server.conf", "client TLS tunnel server config", "sslVersionMin = TLSv1.2")
    require_text(tunnel_dir / "stunnel-server.conf", "client TLS tunnel server config", "cert = /etc/letsencrypt/live/{}/fullchain.pem".format(cert_host))
    require_text(tunnel_dir / "stunnel-server.conf", "client TLS tunnel server config", "key = /etc/letsencrypt/live/{}/privkey.pem".format(cert_host))
    require_text(tunnel_dir / "stunnel-server.conf", "client TLS tunnel server config", "accept = {}:{}".format(server_accept_host, game_port))
    require_text(tunnel_dir / "stunnel-server.conf", "client TLS tunnel server config", "connect = 127.0.0.1:{}".format(game_port))


def archive_unix_mode(info):
    return stat.S_IMODE((info.external_attr >> 16) & 0o177777)


def archive_unix_file_type(info):
    return stat.S_IFMT((info.external_attr >> 16) & 0o177777)


def verify_client_archive_permissions(entry, info):
    mode = archive_unix_mode(info)
    if entry.endswith("/"):
        if archive_unix_file_type(info) not in (0, stat.S_IFDIR):
            fail("client archive directory entry must be a directory: {}".format(entry))
        return
    if archive_unix_file_type(info) not in (0, stat.S_IFREG):
        fail("client archive file entry must be a regular file: {}".format(entry))
    if entry.endswith("/Run-2006Scape.command"):
        if not mode & 0o111:
            fail("client archive macOS launcher wrapper is not executable: {}".format(entry))
    elif entry.endswith("/Check-Setup.command"):
        if not mode & 0o111:
            fail("client archive macOS setup checker wrapper is not executable: {}".format(entry))
    elif entry.endswith("/run-macos-linux.sh"):
        if not mode & 0o111:
            fail("client archive macOS/Linux launcher is not executable: {}".format(entry))
    elif entry.endswith("/check-setup-macos-linux.sh"):
        if not mode & 0o111:
            fail("client archive macOS/Linux setup checker is not executable: {}".format(entry))
    elif mode & 0o111:
        fail("client archive entry should not be executable: {}".format(entry))


def reject_unexpected_client_files(config, client_dist):
    expected = expected_client_files(config)
    unexpected = []
    for path in client_dist.rglob("*"):
        if path.is_symlink():
            fail("client package contains symlinked path: {}".format(path.relative_to(client_dist)))
        if not path.is_file():
            continue
        relative = str(path.relative_to(client_dist))
        if relative not in expected:
            unexpected.append(relative)
    if unexpected:
        fail("client package contains unexpected files: {}".format(", ".join(sorted(unexpected)[:5])))


def verify_checksums(config, client_dist):
    checksum_path = client_dist / "SHA256SUMS"
    try:
        lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        fail("could not read {}: {}".format(checksum_path, exc))
    if not lines:
        fail("SHA256SUMS is empty")
    required_entries = expected_client_files(config) - {"SHA256SUMS"}
    seen = set()
    for line in lines:
        parts = line.strip().split()
        if len(parts) < 2:
            fail("malformed checksum line in {}: {}".format(checksum_path, line))
        expected, relative = parts[0], parts[-1]
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            fail("SHA256SUMS contains unsafe entry: {}".format(relative))
        if relative not in required_entries:
            fail("SHA256SUMS contains unexpected entries: {}".format(relative))
        if relative in seen:
            fail("duplicate checksum entry for {}".format(relative))
        seen.add(relative)
        path = client_dist / relative
        require_file(path, "checksummed file")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            fail("checksum mismatch for {}".format(path))
    missing = sorted(required_entries - seen)
    if missing:
        fail("SHA256SUMS is missing entries: {}".format(", ".join(missing)))


def verify_accounts(config, accounts_dir, allow_empty_accounts, warnings):
    if not bool(config.get("account_auth_enabled", False)):
        return
    if not accounts_dir.exists():
        if allow_empty_accounts:
            warn(warnings, "accounts directory is missing: {}".format(accounts_dir))
            return
        fail("accounts directory is missing: {}".format(accounts_dir))
    require_not_symlink(accounts_dir, "accounts directory")
    verify_owner_only_permissions(accounts_dir, "accounts directory", True)
    records = sorted(accounts_dir.glob("*.json"))
    if not records:
        if allow_empty_accounts:
            warn(warnings, "accounts directory has no account records: {}".format(accounts_dir))
            return
        fail("accounts directory has no account records: {}".format(accounts_dir))
    enabled_records = 0
    for record_path in records:
        require_not_symlink(record_path, "account record")
        verify_owner_only_permissions(record_path, "account record", False)
        record = load_json(record_path)
        if not isinstance(record, dict):
            fail("account record must be a JSON object: {}".format(record_path))
        username = account_username(record.get("username"))
        if username == "":
            fail("account record has invalid username: {}".format(record_path))
        expected_file_name = account_file_name(username)
        if record_path.name != expected_file_name:
            fail("account record filename does not match username: {} should be {}".format(
                record_path.name, expected_file_name))
        decode_account_base64(record, "passwordHash", record_path, 32)
        decode_account_base64(record, "passwordSalt", record_path, 16)
        if int_value(record, "passwordIterations", 0) < MIN_EXTERNAL_PBKDF2_ITERATIONS:
            fail("account record uses too few PBKDF2 iterations: {}".format(record_path))
        if not isinstance(record.get("algorithm"), str):
            fail("account record has invalid algorithm type: {}".format(record_path))
        algorithm = string_value(record, "algorithm")
        if algorithm not in ("PBKDF2WithHmacSHA256", "PBKDF2WithHmacSHA1"):
            fail("account record has unsupported algorithm {}: {}".format(algorithm, record_path))
        if "disabled" in record and not isinstance(record.get("disabled"), bool):
            fail("account record disabled field must be a boolean: {}".format(record_path))
        validate_account_metadata(record, record_path)
        if not record.get("disabled", False):
            enabled_records += 1
    if enabled_records == 0:
        fail("all account records are disabled in {}".format(accounts_dir))


def verify_discord(config, secrets_path, allow_placeholder_discord_secrets):
    if not bool(config.get("agent_chat_discord_enabled", False)):
        return
    if not allow_placeholder_discord_secrets:
        require_not_symlink(secrets_path, "Discord secrets")
        verify_owner_only_permissions(secrets_path, "Discord secrets", False)
    secrets = load_json(secrets_path)
    bots = secrets.get("agent-discord-bots", [])
    if not isinstance(bots, list) or not bots:
        fail("agent_chat_discord_enabled=true but no agent-discord-bots are configured in {}".format(secrets_path))
    seen_agents = set()
    for index, bot in enumerate(bots):
        if not isinstance(bot, dict):
            fail("agent-discord-bots[{}] must be an object".format(index))
        agent = discord_string(bot, index, ("agent", "profile", "name"), "agent/profile/name", True)
        token = discord_string(bot, index, ("token",), "token", True)
        channel_id = discord_string(bot, index, ("channelId", "channel_id"), "channelId/channel_id", False)
        channel_name = discord_string(bot, index, ("channelName", "channel_name"), "channelName/channel_name", False)
        discord_string(bot, index, ("channel",), "channel", False)
        validate_not_placeholder_discord_secret(token, index, "token", allow_placeholder_discord_secrets)
        if channel_id:
            validate_not_placeholder_discord_secret(channel_id, index, "channelId/channel_id", allow_placeholder_discord_secrets)
        if channel_name:
            validate_not_placeholder_discord_secret(channel_name, index, "channelName/channel_name", allow_placeholder_discord_secrets)
        validate_discord_allow_list(bot, index, "allowedAgents", "allowed_agents")
        validate_discord_allow_list(bot, index, "allowedPlayers", "allowed_players")
        validate_discord_bool(bot, index, "allowBroadcast", "allow_broadcast")
        if not token or not (channel_id or channel_name):
            fail("agent-discord-bots[{}] needs token and channelId/channelName".format(index))
        agent_key = agent.lower()
        if agent_key in seen_agents:
            fail("duplicate Discord bot config for agent/profile: {}".format(agent))
        seen_agents.add(agent_key)


def can_connect(host, port, timeout):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def tls_connect_error(host, port, timeout, server_hostname, allow_untrusted):
    try:
        raw_socket = socket.create_connection((host, port), timeout=timeout)
        try:
            context = create_tls_client_context(allow_untrusted)
            with context.wrap_socket(raw_socket, server_hostname=server_hostname or host):
                return ""
        except Exception:
            raw_socket.close()
            raise
    except (OSError, ssl.SSLError, ssl.CertificateError) as exc:
        return str(exc) or exc.__class__.__name__


def verify_live_ports(config, timeout, warnings, allow_untrusted_client_tls=False, tls_sni_host=""):
    host = string_value(config, "public_game_host")
    if not host:
        fail("public_game_host is required for live checks")
    mode = string_value(config, "external_transport_mode").lower()
    client_tls_tunnel = mode == "client_tls_tunnel"
    if client_tls_tunnel and allow_untrusted_client_tls:
        warn(warnings, "client_tls_tunnel TLS checks allowed untrusted certificates; prefer a certificate trusted by players' machines")
    ports = [("game", int_value(config, "game_port", 43594))]
    if bool(config.get("file_server", True)):
        ports.append(("http cache", int_value(config, "http_port", 8080)))
        ports.append(("jaggrab cache", int_value(config, "jaggrab_port", 43595)))
    checked = []
    for label, port in ports:
        if client_tls_tunnel:
            server_hostname = tls_sni_host or host
            error = tls_connect_error(host, port, timeout, server_hostname, allow_untrusted_client_tls)
            if error:
                fail("could not complete TLS handshake to {} port {} at {}: {}".format(label, port, host, error))
            checked.append("{} TLS handshake {}:{} sni={}".format(label, host, port, server_hostname))
        elif not can_connect(host, port, timeout):
            fail("could not connect to {} port {} at {}".format(label, port, host))
        else:
            checked.append("{} TCP connect {}:{}".format(label, host, port))
    bridge_port = int_value(config, "agent_bridge_port", AGENT_BRIDGE_PORT)
    if can_connect(host, bridge_port, timeout):
        fail("agent bridge port {} is reachable at {}; do not expose it externally".format(bridge_port, host))
    else:
        checked.append("agent bridge TCP not reachable {}:{}".format(host, bridge_port))
    return checked


def verify_live_login(config, username, password, timeout, allow_untrusted_client_tls=False,
        tls_sni_host="", hold_seconds=0.0):
    host = string_value(config, "public_game_host")
    if not host:
        fail("public_game_host is required for live login checks")
    port = int_value(config, "game_port", 43594)
    mode = string_value(config, "external_transport_mode").lower()
    use_tls = mode == "client_tls_tunnel"
    try:
        result = probe_login(
            host,
            port,
            username,
            password,
            timeout=timeout,
            use_tls=use_tls,
            tls_sni_host=tls_sni_host,
            allow_untrusted_tls=allow_untrusted_client_tls,
            hold_seconds=hold_seconds,
        )
    except (OSError, LoginProbeError) as exc:
        fail("live login probe failed for {} at {}:{}: {}".format(username, host, port, exc))
    if result.get("status") != 2:
        fail("live login probe rejected {} at {}:{} with status {} ({})".format(
            username, host, port, result.get("status"), result.get("statusName")))
    return "game login accepted {} at {}:{} tls={}".format(
        username, host, port, "yes" if use_tls else "no")


def verify_live_rejected_login(config, username, password, timeout,
        allow_untrusted_client_tls=False, tls_sni_host="", expected_statuses=""):
    host = string_value(config, "public_game_host")
    if not host:
        fail("public_game_host is required for rejected live login checks")
    port = int_value(config, "game_port", 43594)
    mode = string_value(config, "external_transport_mode").lower()
    use_tls = mode == "client_tls_tunnel"
    try:
        result = probe_login(
            host,
            port,
            username,
            password,
            timeout=timeout,
            use_tls=use_tls,
            tls_sni_host=tls_sni_host,
            allow_untrusted_tls=allow_untrusted_client_tls,
        )
    except (OSError, LoginProbeError) as exc:
        fail("rejected live login probe failed for {} at {}:{}: {}".format(username, host, port, exc))
    status = result.get("status")
    status_name = result.get("statusName")
    if status == 2:
        fail("rejected live login probe was accepted for {} at {}:{}; auth did not fail closed".format(
            username, host, port))
    expected = parse_expected_statuses(expected_statuses)
    if expected and status not in expected:
        fail("rejected live login probe for {} returned status {} ({}) but expected one of {}".format(
            username,
            status,
            status_name,
            ", ".join(str(item) for item in sorted(expected)),
        ))
    if expected:
        return "game login rejected {} at {}:{} tls={} status={} ({}) expected={}".format(
            username,
            host,
            port,
            "yes" if use_tls else "no",
            status,
            status_name,
            ",".join(str(item) for item in sorted(expected)),
        )
    return "game login rejected {} at {}:{} tls={} status={} ({})".format(
        username, host, port, "yes" if use_tls else "no", status, status_name)


def parse_expected_statuses(value):
    statuses = set()
    for raw in str(value or "").split(","):
        item = raw.strip()
        if not item:
            continue
        try:
            status = int(item)
        except ValueError:
            fail("--live-reject-login-expected-statuses must be a comma-separated list of numeric login status codes")
        if status < 0 or status > 255:
            fail("--live-reject-login-expected-statuses values must be between 0 and 255")
        statuses.add(status)
    return statuses


def close_socket_quietly(sock):
    if sock is None:
        return
    try:
        sock.close()
    except OSError:
        pass


def verify_live_concurrent_logins(config, external_username, external_password,
        local_username, local_password, timeout, allow_untrusted_client_tls=False,
        tls_sni_host="", local_host="127.0.0.1", local_port=0, hold_seconds=0.0):
    external_host = string_value(config, "public_game_host")
    if not external_host:
        fail("public_game_host is required for concurrent live login checks")
    local_host = validate_live_local_host(local_host)
    external_port = int_value(config, "game_port", 43594)
    local_game_port = int(local_port or external_port)
    mode = string_value(config, "external_transport_mode").lower()
    use_tls = mode == "client_tls_tunnel"
    external_sock = None
    local_sock = None
    try:
        external_sock, external_result = login_socket(
            external_host,
            external_port,
            external_username,
            external_password,
            timeout=timeout,
            use_tls=use_tls,
            tls_sni_host=tls_sni_host,
            allow_untrusted_tls=allow_untrusted_client_tls,
        )
        if external_result.get("status") != 2:
            fail("external live login probe rejected {} at {}:{} with status {} ({})".format(
                external_username,
                external_host,
                external_port,
                external_result.get("status"),
                external_result.get("statusName"),
            ))
        local_sock, local_result = login_socket(
            local_host,
            local_game_port,
            local_username,
            local_password,
            timeout=timeout,
            use_tls=False,
        )
        if local_result.get("status") != 2:
            fail("local live login probe rejected {} at {}:{} with status {} ({})".format(
                local_username,
                local_host,
                local_game_port,
                local_result.get("status"),
                local_result.get("statusName"),
            ))
        if hold_seconds > 0:
            time.sleep(hold_seconds)
        return "concurrent game logins accepted external {} at {}:{} tls={} and local {} at {}:{} tls=no".format(
            external_username,
            external_host,
            external_port,
            "yes" if use_tls else "no",
            local_username,
            local_host,
            local_game_port,
        )
    except (OSError, LoginProbeError) as exc:
        fail("concurrent live login probe failed: {}".format(exc))
    finally:
        close_socket_quietly(local_sock)
        close_socket_quietly(external_sock)


def verify_live_discord(secrets_path, timeout):
    try:
        results = probe_discord_bots(secrets_path, timeout=timeout)
    except DiscordProbeError as exc:
        fail("live Discord bot probe failed: {}".format(exc))
    checks = []
    for result in results:
        text = "Discord bot {} authenticated as {} ({})".format(
            result.get("agent"),
            result.get("botUsername") or "unknown",
            result.get("botUserId") or "unknown-id",
        )
        if result.get("channelChecked"):
            text += " and can read channel {}".format(result.get("channelId"))
            if result.get("channelName"):
                text += " ({})".format(result.get("channelName"))
        elif result.get("warning"):
            text += "; warning: {}".format(result.get("warning"))
        checks.append(text)
    return checks


def main():
    parser = argparse.ArgumentParser(description="Verify 2006Scape external deployment artifacts.")
    parser.add_argument("--config", default=str(ROOT_DIR / "2006Scape Server" / "ServerConfig.json"))
    parser.add_argument("--client-dist", default=str(ROOT_DIR / "dist" / "2006scape-client"))
    parser.add_argument("--archive", default="",
            help="Client zip to verify. Defaults to CLIENT_DIST.zip next to --client-dist.")
    parser.add_argument("--server-deployment-dir", default="",
            help="Optional server-deployment/ directory to verify alongside the client package.")
    parser.add_argument("--client-tls-tunnel-dir", default="",
            help="Optional operator-side client_tls_tunnel stunnel template directory to verify.")
    parser.add_argument("--accounts-dir", default=str(ROOT_DIR / "2006Scape Server" / "data" / "accounts"))
    parser.add_argument("--secrets", default=str(ROOT_DIR / "2006Scape Server" / "data" / "secrets.json"))
    parser.add_argument("--allow-empty-accounts", action="store_true",
            help="Allow no account records; useful only for source/sample validation.")
    parser.add_argument("--allow-wildcard-bind", action="store_true",
            help="Pass through to preflight for deliberate wildcard binds behind a verified firewall/VPN.")
    parser.add_argument("--live", action="store_true",
            help="Also check live socket reachability for public game/cache ports and bridge non-exposure.")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--tls-sni-host", default="",
            help="SNI/hostname to use for --live client_tls_tunnel TLS checks. Defaults to public_game_host.")
    parser.add_argument("--allow-untrusted-client-tls", action="store_true",
            help="Allow self-signed or otherwise untrusted TLS certs during --live client_tls_tunnel checks. Prefer a trusted cert for real players.")
    parser.add_argument("--live-login-username", default="",
            help="Optional username for a live game-protocol login proof. Use a throwaway PBKDF2 account.")
    parser.add_argument("--live-login-password-env", default="",
            help="Environment variable containing the password for --live-login-username.")
    parser.add_argument("--live-login-hold-seconds", type=float, default=0.0,
            help="Hold a successful live login socket open briefly before closing it.")
    parser.add_argument("--live-local-login-username", default="",
            help="Optional second username for concurrent same-host local login proof. Requires --live-login-username.")
    parser.add_argument("--live-local-login-password-env", default="",
            help="Environment variable containing the password for --live-local-login-username.")
    parser.add_argument("--live-local-host", default="127.0.0.1",
            help="Loopback host for same-host local login proof. Defaults to 127.0.0.1.")
    parser.add_argument("--live-local-port", type=int, default=0,
            help="Port for same-host local login proof. Defaults to the configured game_port.")
    parser.add_argument("--live-reject-login-username", default="",
            help="Optional username for a live fail-closed login proof. Use with a wrong password, missing account, or disabled throwaway account.")
    parser.add_argument("--live-reject-login-password-env", default="",
            help="Environment variable containing the password for --live-reject-login-username.")
    parser.add_argument("--live-reject-login-expected-statuses", default="",
            help="Optional comma-separated status codes expected for the rejected login, for example 3 or 3,4.")
    parser.add_argument("--live-discord", action="store_true",
            help="Probe configured Discord bot tokens and channelId reachability through the Discord REST API. Does not send messages.")
    parser.add_argument("--allow-placeholder-discord-secrets", action="store_true",
            help="Allow tracked sample Discord token/channel placeholders. Source validation only; do not use for real deployments.")
    parser.add_argument("--allow-placeholder-network-config", action="store_true",
            help="Allow tracked sample public_game_host/bind host placeholders. Source validation only; do not use for real deployments.")
    args = parser.parse_args()

    config_path = Path(args.config)
    client_dist = Path(args.client_dist)
    archive_path = Path(args.archive) if args.archive else client_dist.with_suffix(".zip")
    server_deployment_dir = Path(args.server_deployment_dir) if args.server_deployment_dir else None
    client_tls_tunnel_dir = Path(args.client_tls_tunnel_dir) if args.client_tls_tunnel_dir else None
    accounts_dir = Path(args.accounts_dir)
    secrets_path = Path(args.secrets)
    warnings = []

    config = load_json(config_path)
    if not bool(config.get("external_players_enabled", False)):
        fail("external_players_enabled is false in {}".format(config_path))
    args.tls_sni_host = validate_tls_sni_host(args.tls_sni_host, args.allow_placeholder_network_config)
    run_preflight(config_path, args.allow_wildcard_bind)
    verify_network_placeholders(config, args.allow_placeholder_network_config)
    verify_client_package(config, config_path, client_dist, warnings)
    verify_client_archive(config, client_dist, archive_path)
    verify_server_deployment(config, server_deployment_dir)
    verify_client_tls_tunnel_operator(
            config,
            client_tls_tunnel_dir,
            args.tls_sni_host,
            warnings,
            args.allow_placeholder_network_config)
    verify_accounts(config, accounts_dir, args.allow_empty_accounts, warnings)
    verify_discord(config, secrets_path, args.allow_placeholder_discord_secrets)
    if args.live_discord and args.allow_placeholder_discord_secrets:
        fail("--live-discord cannot be used with --allow-placeholder-discord-secrets")
    if args.live_discord and not bool(config.get("agent_chat_discord_enabled", False)):
        fail("--live-discord requires agent_chat_discord_enabled=true")
    if (args.live_login_username or args.live_login_password_env) and not args.live:
        fail("--live-login-username requires --live")
    if args.live_login_username and not args.live_login_password_env:
        fail("--live-login-username requires --live-login-password-env")
    if args.live_login_password_env and not args.live_login_username:
        fail("--live-login-password-env requires --live-login-username")
    if (args.live_local_login_username or args.live_local_login_password_env) and not args.live:
        fail("--live-local-login-username requires --live")
    if args.live_local_login_username and not args.live_local_login_password_env:
        fail("--live-local-login-username requires --live-local-login-password-env")
    if args.live_local_login_password_env and not args.live_local_login_username:
        fail("--live-local-login-password-env requires --live-local-login-username")
    if args.live_local_login_username and not args.live_login_username:
        fail("--live-local-login-username requires --live-login-username for concurrent external/local proof")
    args.live_local_host = validate_live_local_host(args.live_local_host)
    if args.live_local_port < 0 or args.live_local_port > 65535:
        fail("--live-local-port must be 0 or between 1 and 65535 when supplied")
    if (args.live_reject_login_username or args.live_reject_login_password_env) and not args.live:
        fail("--live-reject-login-username requires --live")
    if args.live_reject_login_username and not args.live_reject_login_password_env:
        fail("--live-reject-login-username requires --live-reject-login-password-env")
    if args.live_reject_login_password_env and not args.live_reject_login_username:
        fail("--live-reject-login-password-env requires --live-reject-login-username")
    if args.live_reject_login_expected_statuses and not args.live_reject_login_username:
        fail("--live-reject-login-expected-statuses requires --live-reject-login-username")
    live_checks = []
    if args.live:
        live_checks = verify_live_ports(config, args.timeout, warnings,
                allow_untrusted_client_tls=args.allow_untrusted_client_tls,
                tls_sni_host=args.tls_sni_host)
        if args.live_login_username:
            password = os.environ.get(args.live_login_password_env)
            if password is None:
                fail("environment variable {} is not set".format(args.live_login_password_env))
            if args.live_local_login_username:
                local_password = os.environ.get(args.live_local_login_password_env)
                if local_password is None:
                    fail("environment variable {} is not set".format(args.live_local_login_password_env))
                live_checks.append(verify_live_concurrent_logins(
                    config,
                    args.live_login_username,
                    password,
                    args.live_local_login_username,
                    local_password,
                    args.timeout,
                    allow_untrusted_client_tls=args.allow_untrusted_client_tls,
                    tls_sni_host=args.tls_sni_host,
                    local_host=args.live_local_host,
                    local_port=args.live_local_port,
                    hold_seconds=args.live_login_hold_seconds,
                ))
            else:
                live_checks.append(verify_live_login(config, args.live_login_username, password, args.timeout,
                        allow_untrusted_client_tls=args.allow_untrusted_client_tls,
                        tls_sni_host=args.tls_sni_host,
                        hold_seconds=args.live_login_hold_seconds))
        if args.live_reject_login_username:
            reject_password = os.environ.get(args.live_reject_login_password_env)
            if reject_password is None:
                fail("environment variable {} is not set".format(args.live_reject_login_password_env))
            live_checks.append(verify_live_rejected_login(
                config,
                args.live_reject_login_username,
                reject_password,
                args.timeout,
                allow_untrusted_client_tls=args.allow_untrusted_client_tls,
                tls_sni_host=args.tls_sni_host,
                expected_statuses=args.live_reject_login_expected_statuses,
            ))
    discord_checks = []
    if args.live_discord:
        discord_checks = verify_live_discord(secrets_path, args.timeout)

    print("ok: external deployment artifacts verified")
    print("config: {}".format(config_path))
    print("client_dist: {}".format(client_dist))
    print("archive: {}".format(archive_path))
    if server_deployment_dir is not None:
        print("server_deployment: {}".format(server_deployment_dir))
    if client_tls_tunnel_dir is not None:
        print("client_tls_tunnel: {}".format(client_tls_tunnel_dir))
    if args.live:
        if string_value(config, "external_transport_mode").lower() == "client_tls_tunnel":
            print("live: checked public game/cache TLS handshakes and bridge non-exposure")
        else:
            print("live: checked public game/cache ports and bridge non-exposure")
        for check in live_checks:
            print("live-check: {}".format(check))
    else:
        print("live: skipped; pass --live after the remote server is running")
    if args.live_discord:
        print("discord: checked live bot authentication and channel reachability")
        for check in discord_checks:
            print("discord-check: {}".format(check))
    elif bool(config.get("agent_chat_discord_enabled", False)):
        print("discord: skipped; pass --live-discord to prove configured bot tokens and channel reachability")
    for message in warnings:
        print("warning: {}".format(message))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
