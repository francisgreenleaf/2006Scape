"""Shared proof-manifest loading for external deployment readiness tools."""

import json
import re
from pathlib import Path


ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

FIELD_TYPES = {
    "require_full_proof": bool,
    "live": bool,
    "timeout": float,
    "tls_sni_host": str,
    "allow_untrusted_client_tls": bool,
    "live_login_username": str,
    "live_login_password_env": str,
    "live_login_hold_seconds": float,
    "live_local_login_username": str,
    "live_local_login_password_env": str,
    "live_local_host": str,
    "live_local_port": int,
    "live_reject_login_username": str,
    "live_reject_login_password_env": str,
    "live_reject_login_expected_statuses": str,
    "live_discord": bool,
    "agent_chat_log_root": str,
    "agent_chat_log_text": str,
    "agent_chat_log_from_type": str,
    "agent_chat_log_from_name": str,
    "agent_chat_log_from_profile": str,
    "agent_chat_log_from_bot": str,
    "agent_chat_log_discord_message_id": str,
    "agent_chat_log_to_type": str,
    "agent_chat_log_to_name": str,
    "agent_chat_log_channel": str,
    "agent_chat_log_since_seconds": float,
    "agent_chat_log_since_id": int,
    "agent_chat_blocked_log_root": str,
    "agent_chat_blocked_log_text": str,
    "agent_chat_blocked_log_channel": str,
    "agent_chat_blocked_log_since_seconds": float,
    "agent_chat_blocked_log_since_id": int,
    "agent_chat_delivery_log_root": str,
    "agent_chat_delivery_log_text": str,
    "agent_chat_delivery_log_to_name": str,
    "agent_chat_delivery_log_channel": str,
    "agent_chat_delivery_log_since_seconds": float,
    "agent_chat_delivery_log_since_id": int,
    "desktop_client_proof_file": str,
    "runtime_data_backup_proof_file": str,
    "discord_channel_message_text": str,
    "discord_channel_message_agent": list,
    "discord_channel_message_limit": int,
    "discord_channel_message_after_id": str,
    "discord_channel_message_allow_human_author": bool,
    "discord_channel_message_require_all": bool,
    "command_timeout": float,
}

PASSWORD_ENV_FIELDS = {
    "live_login_password_env",
    "live_local_login_password_env",
    "live_reject_login_password_env",
}

MANIFEST_RELATIVE_PATH_FIELDS = {
    "desktop_client_proof_file",
    "runtime_data_backup_proof_file",
}

SECRETISH_KEY_RE = re.compile(r"(?i)(password|token|secret|authorization|api[_-]?key)")
PLACEHOLDER_VALUE_RE = re.compile(
    r"^(PATH_TO_|REPLACE_|TODO$|TBD$|.*_MARKER$|.*_USERNAME$|.*_TEST_USERNAME$|"
    r"AGENT_PROFILE$|PLAYER_USERNAME$|DISCORD_MESSAGE_ID$|"
    r"EXTERNAL_TEST_PASSWORD$|LOCAL_TEST_PASSWORD$|REJECT_TEST_PASSWORD$)"
)


def normalize_key(key):
    return str(key).strip().lstrip("-").replace("-", "_")


def cli_dest_names(argv):
    names = set()
    for value in argv:
        if not str(value).startswith("--"):
            continue
        option = str(value).split("=", 1)[0]
        dest = normalize_key(option)
        if dest == "proof_manifest":
            continue
        names.add(dest)
    return names


def reject_raw_secret_key(key):
    normalized = normalize_key(key)
    if normalized in PASSWORD_ENV_FIELDS:
        return
    if SECRETISH_KEY_RE.search(normalized):
        raise ValueError(
            "proof manifest key {!r} looks like a raw secret; store only env var names such as *_password_env".format(
                key
            )
        )


def convert_value(key, value, expected_type):
    if expected_type is bool:
        if type(value) is not bool:
            raise ValueError("proof manifest field {} must be a JSON boolean".format(key))
        return value
    if expected_type is int:
        if type(value) is not int:
            raise ValueError("proof manifest field {} must be a JSON integer".format(key))
        return value
    if expected_type is float:
        if type(value) not in (int, float) or type(value) is bool:
            raise ValueError("proof manifest field {} must be a JSON number".format(key))
        return float(value)
    if expected_type is str:
        if not isinstance(value, str):
            raise ValueError("proof manifest field {} must be a JSON string".format(key))
        return value
    if expected_type is list:
        if isinstance(value, str):
            return [value]
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            raise ValueError("proof manifest field {} must be a string or list of non-empty strings".format(key))
        return list(value)
    raise ValueError("unsupported proof manifest field type for {}".format(key))


def string_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                yield item


def reject_placeholder_value(key, value):
    for item in string_values(value):
        if PLACEHOLDER_VALUE_RE.match(item.strip()):
            raise ValueError(
                "proof manifest field {} still contains placeholder value {!r}; copy the template and replace placeholders before use".format(
                    key,
                    item,
                )
            )


def read_manifest(path):
    manifest_path = Path(path)
    if not str(path).strip():
        return {}
    if manifest_path.is_symlink():
        raise ValueError("proof manifest must not be a symlink: {}".format(manifest_path))
    if not manifest_path.is_file():
        raise ValueError("proof manifest is missing or not a file: {}".format(manifest_path))
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("proof manifest is not valid JSON: {}: {}".format(manifest_path, exc))
    if not isinstance(data, dict):
        raise ValueError("proof manifest must be a JSON object: {}".format(manifest_path))
    return data


def validate_manifest_data(data, allow_placeholders=False):
    values = {}
    for raw_key, raw_value in data.items():
        if str(raw_key).startswith("_"):
            continue
        reject_raw_secret_key(raw_key)
        key = normalize_key(raw_key)
        if key not in FIELD_TYPES:
            raise ValueError("proof manifest has unknown field {!r}".format(raw_key))
        value = convert_value(key, raw_value, FIELD_TYPES[key])
        if key in PASSWORD_ENV_FIELDS and value and not ENV_NAME_RE.match(value):
            raise ValueError(
                "proof manifest field {} must name an environment variable, not contain a password".format(key)
            )
        if not allow_placeholders:
            reject_placeholder_value(key, value)
        values[key] = value
    return values


def validate_proof_manifest_template(path, required_fields=None):
    values = validate_manifest_data(read_manifest(path), allow_placeholders=True)
    missing = sorted(set(required_fields or ()) - set(values.keys()))
    if missing:
        raise ValueError(
            "deployment proof manifest template is missing required field(s): {}".format(
                ", ".join(missing)
            )
        )
    return values


def resolve_manifest_relative_paths(values, manifest_path, cli_names=None):
    """Resolve proof-note file fields relative to the manifest file.

    CLI-supplied values keep normal command-line semantics and are not resolved
    here. Manifest-owned proof notes are usually copied beside the manifest in a
    prepared deployment directory, so resolving from the manifest parent makes
    handoff bundles and final readiness commands independent of the caller's
    shell working directory.
    """
    cli_names = set(cli_names or ())
    manifest_parent = Path(manifest_path).parent
    resolved = dict(values)
    for field in MANIFEST_RELATIVE_PATH_FIELDS:
        if field in cli_names:
            continue
        value = resolved.get(field)
        if not isinstance(value, str) or not value.strip():
            continue
        candidate = Path(value.strip())
        if candidate.is_absolute():
            continue
        resolved[field] = str(manifest_parent / candidate)
    return resolved


def read_manifest_values(path, allow_placeholders=False, resolve_relative_paths=True, cli_names=None):
    values = validate_manifest_data(read_manifest(path), allow_placeholders=allow_placeholders)
    if resolve_relative_paths:
        values = resolve_manifest_relative_paths(values, path, cli_names=cli_names)
    return values


def apply_proof_manifest(parser, args, argv):
    manifest_path = getattr(args, "proof_manifest", "")
    if not manifest_path:
        return args
    try:
        cli_names = cli_dest_names(argv)
        data = read_manifest_values(
            manifest_path,
            allow_placeholders=False,
            resolve_relative_paths=True,
            cli_names=cli_names,
        )
        for key, value in data.items():
            if key in cli_names:
                continue
            setattr(args, key, value)
    except ValueError as exc:
        parser.error(str(exc))
    return args
