#!/usr/bin/env python3
"""Verify a public-safe per-player client handoff kit."""

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PREPARED_DIR = ROOT_DIR / "dist" / "external-deployment"
SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9_.-]+")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?im)^\s*[A-Za-z0-9_]*(password|token|secret|nonce|api[_-]?key|bot[_-]?token)[A-Za-z0-9_]*\s*="
)
HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SENSITIVE_PARTS = {
    "accounts",
    "characters",
    "private",
}
SENSITIVE_NAMES = {
    "secrets.json",
    "rsbridge-session.json",
    "vps-character-credentials.env",
}
TEXT_EXTENSIONS = {
    ".bat",
    ".command",
    ".conf",
    ".json",
    ".md",
    ".properties",
    ".ps1",
    ".sh",
    ".txt",
}


def fail(message):
    raise SystemExit(message)


def resolve_under_root(path):
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def safe_stem(value):
    clean = SAFE_STEM_RE.sub("-", value.strip()).strip("-._").lower()
    return clean or "player"


def reject_symlink(path, label):
    if path.is_symlink():
        fail("{} must not be a symlink: {}".format(label, path))


def require_file(path, label):
    reject_symlink(path, label)
    if not path.is_file():
        fail("{} is missing: {}".format(label, path))
    return path


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_text(data, label):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail("{} must be UTF-8 text: {}".format(label, exc))


def parse_key_value_text(text):
    values = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        values[key.strip()] = value.strip()
    return values


def zip_entry_is_symlink(info):
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def unsafe_zip_entry_name(name):
    if not name or name.startswith("/") or "\\" in name:
        return True
    return ".." in Path(name).parts


def zip_entry_is_sensitive(name):
    path = Path(name)
    parts = [part.lower() for part in path.parts]
    if any(part in SENSITIVE_PARTS for part in parts):
        return True
    if name.endswith("/"):
        return False
    basename = path.name.lower()
    if basename in SENSITIVE_NAMES:
        return True
    if (
        "credential" in basename
        or "password" in basename
        or "secret" in basename
        or "token" in basename
        or "nonce" in basename
        or "api-key" in basename
        or "apikey" in basename
        or "bot-token" in basename
    ):
        return True
    return False


def validate_archive_entries(archive, label):
    bad = []
    for info in archive.infolist():
        if unsafe_zip_entry_name(info.filename):
            bad.append(info.filename)
        elif zip_entry_is_symlink(info):
            bad.append(info.filename)
        elif zip_entry_is_sensitive(info.filename):
            bad.append(info.filename)
    if bad:
        fail("{} contains private, symlinked, or unsafe entries: {}".format(label, ", ".join(bad[:8])))


def validate_no_secret_assignments_in_text_entries(archive, label, allowed_entries=None):
    allowed = set(allowed_entries or ())
    for info in archive.infolist():
        if info.is_dir():
            continue
        suffix = Path(info.filename).suffix.lower()
        if suffix not in TEXT_EXTENSIONS:
            continue
        text = decode_text(archive.read(info.filename), "{} {}".format(label, info.filename))
        if SECRET_ASSIGNMENT_RE.search(text):
            if info.filename not in allowed:
                fail("{} text entry appears to contain a secret-like assignment: {}".format(label, info.filename))


def validate_client_archive_bytes(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            validate_archive_entries(archive, "nested client archive")
            validate_no_secret_assignments_in_text_entries(archive, "nested client archive")
            names = set(archive.namelist())
            required = {"agent-scape-client/client.properties", "agent-scape-client/MANIFEST.txt"}
            missing = sorted(required - names)
            if missing:
                fail("nested client archive is missing required entries: {}".format(", ".join(missing)))
    except zipfile.BadZipFile as exc:
        fail("nested client archive is not a valid zip: {}".format(exc))


def read_required_entry(archive, name):
    try:
        return archive.read(name)
    except KeyError:
        fail("player kit is missing required entry: {}".format(name))


def normalize_expected_path(path_value):
    if not path_value:
        return None
    path = resolve_under_root(Path(path_value))
    return path


def verify_kit(args):
    kit_path = resolve_under_root(Path(args.kit))
    require_file(kit_path, "player kit")

    expected_username = args.username.strip() if args.username else ""
    expected_character = args.character.strip() if args.character else ""

    try:
        with zipfile.ZipFile(str(kit_path), "r") as archive:
            validate_archive_entries(archive, "player kit")
            names = [name for name in archive.namelist() if name]
            top_levels = {name.split("/", 1)[0] for name in names if not name.startswith("/")}
            if len(top_levels) != 1:
                fail("player kit must contain exactly one top-level directory; found {}".format(sorted(top_levels)))
            kit_dir = next(iter(top_levels))
            if not kit_dir.startswith("agent-scape-player-kit-"):
                fail("player kit top-level directory has unexpected name: {}".format(kit_dir))

            metadata_name = kit_dir + "/KIT-METADATA.json"
            metadata_text = decode_text(read_required_entry(archive, metadata_name), metadata_name)
            if SECRET_ASSIGNMENT_RE.search(metadata_text):
                fail("KIT-METADATA.json appears to contain a secret-like assignment")
            try:
                metadata = json.loads(metadata_text)
            except json.JSONDecodeError as exc:
                fail("KIT-METADATA.json is not valid JSON: {}".format(exc))
            if not isinstance(metadata, dict):
                fail("KIT-METADATA.json must contain an object")

            client_archive_name = metadata.get("clientArchive") or "agent-scape-client.zip"
            if Path(client_archive_name).name != client_archive_name or zip_entry_is_sensitive(client_archive_name):
                fail("KIT-METADATA.json has unsafe clientArchive: {}".format(client_archive_name))
            client_entry = kit_dir + "/" + client_archive_name
            required_entries = {
                kit_dir + "/",
                client_entry,
                kit_dir + "/README-FIRST.md",
                kit_dir + "/client-SHA256SUMS.txt",
                kit_dir + "/client-MANIFEST.txt",
                kit_dir + "/KIT-MANIFEST.txt",
                metadata_name,
            }
            missing = sorted(entry for entry in required_entries if entry not in names)
            if missing:
                fail("player kit is missing required entries: {}".format(", ".join(missing)))
            unexpected = sorted(name for name in names if name not in required_entries)
            if unexpected:
                fail("player kit contains unexpected entries: {}".format(", ".join(unexpected[:8])))

            readme_data = read_required_entry(archive, kit_dir + "/README-FIRST.md")
            readme_text = decode_text(readme_data, "README-FIRST.md")
            if SECRET_ASSIGNMENT_RE.search(readme_text):
                fail("README-FIRST.md appears to contain a secret-like assignment")
            kit_manifest_text = decode_text(read_required_entry(archive, kit_dir + "/KIT-MANIFEST.txt"), "KIT-MANIFEST.txt")
            if SECRET_ASSIGNMENT_RE.search(kit_manifest_text):
                fail("KIT-MANIFEST.txt appears to contain a secret-like assignment")
            client_manifest_text = decode_text(read_required_entry(archive, kit_dir + "/client-MANIFEST.txt"), "client-MANIFEST.txt")
            if SECRET_ASSIGNMENT_RE.search(client_manifest_text):
                fail("client-MANIFEST.txt appears to contain a secret-like assignment")
            checksum_text = decode_text(read_required_entry(archive, kit_dir + "/client-SHA256SUMS.txt"), "client-SHA256SUMS.txt")
            if SECRET_ASSIGNMENT_RE.search(checksum_text):
                fail("client-SHA256SUMS.txt appears to contain a secret-like assignment")

            client_data = read_required_entry(archive, client_entry)
            validate_client_archive_bytes(client_data)
    except zipfile.BadZipFile as exc:
        fail("player kit is not a valid zip: {}: {}".format(kit_path, exc))

    client_sha = sha256_bytes(client_data)
    handoff_sha = sha256_bytes(readme_data)
    kit_manifest = parse_key_value_text(kit_manifest_text)

    if metadata.get("schemaVersion") != 1:
        fail("KIT-METADATA.json schemaVersion must be 1")
    if metadata.get("passwordIncluded") is not False:
        fail("KIT-METADATA.json must say passwordIncluded=false")
    if metadata.get("privateFilesIncluded") is not False:
        fail("KIT-METADATA.json must say privateFilesIncluded=false")
    if metadata.get("runtimeTouched") is not False:
        fail("KIT-METADATA.json must say runtimeTouched=false")
    if metadata.get("clientArchiveSha256") != client_sha:
        fail("clientArchiveSha256 does not match embedded client archive")
    if metadata.get("handoffNoteSha256") != handoff_sha:
        fail("handoffNoteSha256 does not match README-FIRST.md")
    if not HEX_SHA256_RE.fullmatch(client_sha) or not HEX_SHA256_RE.fullmatch(handoff_sha):
        fail("computed SHA-256 value has unexpected format")

    username = metadata.get("username") or kit_manifest.get("username") or ""
    character = metadata.get("character") or kit_manifest.get("character") or ""
    if expected_username and username != expected_username:
        fail("kit username mismatch: expected {}, found {}".format(expected_username, username))
    if expected_character and character != expected_character:
        fail("kit character mismatch: expected {}, found {}".format(expected_character, character))
    if kit_manifest.get("client_archive_sha256") != client_sha:
        fail("KIT-MANIFEST.txt client_archive_sha256 does not match embedded client archive")
    if kit_manifest.get("handoff_note_sha256") != handoff_sha:
        fail("KIT-MANIFEST.txt handoff_note_sha256 does not match README-FIRST.md")
    if kit_manifest.get("password_included") != "0":
        fail("KIT-MANIFEST.txt must say password_included: 0")
    if kit_manifest.get("private_files_included") != "0":
        fail("KIT-MANIFEST.txt must say private_files_included: 0")
    if kit_manifest.get("runtime_touched") != "0":
        fail("KIT-MANIFEST.txt must say runtime_touched: 0")

    prepared_dir = normalize_expected_path(args.prepared_dir)
    client_archive_path = normalize_expected_path(args.client_archive)
    handoff_note_path = normalize_expected_path(args.handoff_note)
    if prepared_dir and not client_archive_path:
        candidate = prepared_dir / "agent-scape-client.zip"
        if candidate.is_file():
            client_archive_path = candidate
    if prepared_dir and not handoff_note_path:
        stem_source = expected_username or username
        candidate = prepared_dir / "player-handoff-{}.md".format(safe_stem(stem_source))
        if candidate.is_file():
            handoff_note_path = candidate

    client_archive_match = None
    handoff_note_match = None
    if client_archive_path:
        require_file(client_archive_path, "expected client archive")
        expected_client_sha = sha256_file(client_archive_path)
        client_archive_match = expected_client_sha == client_sha
        if not client_archive_match:
            fail("embedded client archive does not match expected client archive: {}".format(client_archive_path))
    if handoff_note_path:
        require_file(handoff_note_path, "expected handoff note")
        expected_handoff_sha = sha256_file(handoff_note_path)
        handoff_note_match = expected_handoff_sha == handoff_sha
        if not handoff_note_match:
            fail("README-FIRST.md does not match expected handoff note: {}".format(handoff_note_path))

    kit_sha = sha256_file(kit_path)
    return {
        "success": True,
        "playerKit": str(kit_path),
        "playerKitSha256": kit_sha,
        "kitDirectory": kit_dir,
        "username": username,
        "character": character,
        "clientArchive": client_archive_name,
        "clientArchiveSha256": client_sha,
        "handoffNoteSha256": handoff_sha,
        "expectedExternalTransport": metadata.get("expectedExternalTransport", ""),
        "publicGameHost": metadata.get("publicGameHost", ""),
        "gamePort": metadata.get("gamePort", ""),
        "agentBridgeUrl": metadata.get("agentBridgeUrl", ""),
        "passwordIncluded": False,
        "privateFilesIncluded": False,
        "runtimeTouched": False,
        "clientArchiveMatchesExpected": client_archive_match,
        "handoffNoteMatchesExpected": handoff_note_match,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Verify a player-kit zip before distribution. Checks required public entries, embedded checksums, "
            "nested client archive safety, optional prepared-artifact matches, and absence of passwords/private files."
        )
    )
    parser.add_argument("--kit", required=True, help="Player kit zip to verify.")
    parser.add_argument("--prepared-dir", default="", help="Prepared deployment directory used for optional expected-file checks.")
    parser.add_argument("--client-archive", default="", help="Expected client zip. Defaults to PREPARED_DIR/agent-scape-client.zip when present.")
    parser.add_argument("--handoff-note", default="", help="Expected handoff note. Defaults to PREPARED_DIR/player-handoff-USERNAME.md when present.")
    parser.add_argument("--username", default="", help="Expected username.")
    parser.add_argument("--character", default="", help="Expected character.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary.")
    args = parser.parse_args(argv)

    summary = verify_kit(args)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print("ok: verified player kit {}".format(summary["playerKit"]))
        print("player kit SHA-256: {}".format(summary["playerKitSha256"]))
        print("username: {}".format(summary["username"]))
        print("character: {}".format(summary["character"]))
        print("client archive SHA-256: {}".format(summary["clientArchiveSha256"]))
        print("password included: no")
        print("private files included: no")
        print("runtime: not started, stopped, or restarted")
        if summary["clientArchiveMatchesExpected"] is True:
            print("expected client archive: matches")
        if summary["handoffNoteMatchesExpected"] is True:
            print("expected handoff note: matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
