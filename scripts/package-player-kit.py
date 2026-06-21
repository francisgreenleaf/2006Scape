#!/usr/bin/env python3
"""Package a public-safe per-player client handoff kit."""

import argparse
import datetime as _datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PREPARED_DIR = ROOT_DIR / "dist" / "external-deployment"
USERNAME_RE = re.compile(r"[a-z0-9 .]{1,12}", re.IGNORECASE)
SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9_.-]+")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?im)^\s*[A-Za-z0-9_]*(password|token|secret|nonce|api[_-]?key|bot[_-]?token)[A-Za-z0-9_]*\s*="
)
SENSITIVE_PARTS = {
    "accounts",
    "characters",
}
SENSITIVE_NAMES = {
    "secrets.json",
    "rsbridge-session.json",
    "vps-character-credentials.env",
}


def fail(message):
    raise SystemExit(message)


def utc_now():
    return _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0)


def iso_z(value):
    return value.isoformat().replace("+00:00", "Z")


def resolve_under_root(path):
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def normalize_player_name(value, label):
    clean = (value or "").strip()
    if not USERNAME_RE.fullmatch(clean):
        fail("{} must be 1-12 characters: letters, numbers, spaces, or dots".format(label))
    return clean


def safe_stem(value):
    clean = SAFE_STEM_RE.sub("-", value.strip()).strip("-._").lower()
    return clean or "player"


def reject_symlink(path, label):
    if path.is_symlink():
        fail("{} must not be a symlink: {}".format(label, path))


def reject_symlinked_output_path(path, label):
    reject_symlink(path, label)
    parent = path.parent
    while True:
        if parent.is_symlink():
            fail("refusing to write {} through symlinked parent directory: {}".format(label, parent))
        if parent.exists():
            if not parent.is_dir():
                fail("{} parent must be a directory: {}".format(label, parent))
            return
        if parent == parent.parent:
            fail("{} parent does not exist: {}".format(label, path.parent))
        parent = parent.parent


def require_file(path, label):
    reject_symlink(path, label)
    if not path.is_file():
        fail("{} is missing: {}".format(label, path))
    if is_sensitive_path(path):
        fail("{} points at private/runtime data and cannot be bundled: {}".format(label, path))
    return path


def is_sensitive_path(path):
    parts = [part.lower() for part in path.parts]
    if any(part in SENSITIVE_PARTS for part in parts):
        return True
    for index, part in enumerate(parts):
        if part == "private" and index > 1:
            return True
    name = path.name.lower()
    if name.startswith("player-handoff-") or name.startswith("player-kit-"):
        return False
    if name in SENSITIVE_NAMES:
        return True
    if "credential" in name or "password" in name or "secret" in name or "token" in name:
        return True
    return False


def parse_key_value_file(path):
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_public_text(path, label):
    text = path.read_text(encoding="utf-8")
    if SECRET_ASSIGNMENT_RE.search(text):
        fail("{} appears to contain a secret-like assignment: {}".format(label, path))
    return text


def zip_entry_is_symlink(info):
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def zip_entry_is_sensitive(name):
    parts = [part.lower() for part in Path(name).parts]
    if any(part in SENSITIVE_PARTS for part in parts):
        return True
    basename = Path(name).name.lower()
    if basename in SENSITIVE_NAMES:
        return True
    if "credential" in basename or "password" in basename or "secret" in basename or "token" in basename:
        return True
    return False


def validate_client_archive(path):
    try:
        with zipfile.ZipFile(str(path), "r") as archive:
            bad_entries = []
            for info in archive.infolist():
                if info.filename.startswith("/") or ".." in Path(info.filename).parts:
                    bad_entries.append(info.filename)
                elif zip_entry_is_symlink(info):
                    bad_entries.append(info.filename)
                elif zip_entry_is_sensitive(info.filename):
                    bad_entries.append(info.filename)
            if bad_entries:
                fail("client archive contains private, symlinked, or unsafe entries: {}".format(", ".join(bad_entries[:8])))
    except zipfile.BadZipFile as exc:
        fail("client archive is not a valid zip: {}: {}".format(path, exc))


def render_handoff(prepared_dir, username, character, output, agent_gateway_url):
    argv = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "render-player-handoff.py"),
        "--prepared-dir",
        str(prepared_dir),
        "--username",
        username,
        "--character",
        character,
        "--output",
        str(output),
    ]
    if agent_gateway_url:
        argv.extend(["--agent-gateway-url", agent_gateway_url])
    completed = subprocess.run(
        argv,
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        fail("player handoff render failed:\n{}".format((completed.stdout or "").strip()))


def verify_generated_kit(output, prepared_dir, username, character, client_archive, handoff_note):
    argv = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "verify-player-kit.py"),
        "--kit",
        str(output),
        "--prepared-dir",
        str(prepared_dir),
        "--client-archive",
        str(client_archive),
        "--handoff-note",
        str(handoff_note),
        "--username",
        username,
        "--character",
        character,
        "--json",
    ]
    completed = subprocess.run(
        argv,
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        fail("player kit self-verification failed:\n{}".format((completed.stdout or "").strip()))
    try:
        summary = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        fail("player kit self-verification returned invalid JSON: {}".format(exc))
    if summary.get("success") is not True:
        fail("player kit self-verification did not report success")
    if summary.get("clientArchiveMatchesExpected") is not True:
        fail("player kit self-verification did not match expected client archive")
    if summary.get("handoffNoteMatchesExpected") is not True:
        fail("player kit self-verification did not match expected handoff note")
    return summary


def zip_info(name, mode=0o644):
    info = zipfile.ZipInfo(name)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.external_attr = (mode & 0xFFFF) << 16
    return info


def add_file(archive, source, archive_name, mode=0o644):
    if archive_name.startswith("/") or ".." in Path(archive_name).parts:
        fail("unsafe archive entry path: {}".format(archive_name))
    archive.writestr(zip_info(archive_name, mode), source.read_bytes())


def add_text(archive, archive_name, text, mode=0o644):
    if SECRET_ASSIGNMENT_RE.search(text):
        fail("refusing to package secret-like assignment in {}".format(archive_name))
    archive.writestr(zip_info(archive_name, mode), text.encode("utf-8"))


def build_kit(args):
    prepared_dir = resolve_under_root(Path(args.prepared_dir))
    reject_symlink(prepared_dir, "prepared deployment directory")
    if not prepared_dir.is_dir():
        fail("prepared deployment directory is missing: {}".format(prepared_dir))

    username = normalize_player_name(args.username, "username")
    character = normalize_player_name(args.character or args.username, "character")
    stem = safe_stem(username)

    client_dist = resolve_under_root(Path(args.client_dist)) if args.client_dist else prepared_dir / "agent-scape-client"
    client_archive = resolve_under_root(Path(args.client_archive)) if args.client_archive else prepared_dir / "agent-scape-client.zip"
    handoff_note = resolve_under_root(Path(args.handoff_note)) if args.handoff_note else prepared_dir / "player-handoff-{}.md".format(stem)
    output = resolve_under_root(Path(args.output)) if args.output else prepared_dir / "player-kit-{}.zip".format(stem)

    manifest = require_file(client_dist / "MANIFEST.txt", "client MANIFEST.txt")
    checksums = require_file(client_dist / "SHA256SUMS", "client SHA256SUMS")
    client_props = require_file(client_dist / "client.properties", "client.properties")
    client_archive = require_file(client_archive, "client archive")
    validate_client_archive(client_archive)

    if not handoff_note.exists():
        render_handoff(prepared_dir, username, character, handoff_note, args.agent_gateway_url)
    handoff_note = require_file(handoff_note, "player handoff note")
    handoff_text = validate_public_text(handoff_note, "player handoff note")

    reject_symlinked_output_path(output, "player kit")
    if is_sensitive_path(output):
        fail("player kit output must not be written under a private/runtime path: {}".format(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.resolve() in {client_archive.resolve(), handoff_note.resolve()}:
        fail("player kit output must not overwrite an input file: {}".format(output))

    manifest_values = parse_key_value_file(manifest)
    prop_values = parse_key_value_file(client_props)
    generated_at = utc_now()
    kit_dir = "agent-scape-player-kit-{}".format(stem)
    client_sha = sha256_file(client_archive)
    handoff_sha = sha256_file(handoff_note)
    metadata = {
        "schemaVersion": 1,
        "generatedAt": iso_z(generated_at),
        "username": username,
        "character": character,
        "clientArchive": client_archive.name,
        "clientArchiveSha256": client_sha,
        "handoffNoteSha256": handoff_sha,
        "expectedExternalTransport": manifest_values.get("expected_external_transport") or prop_values.get("secure.transport", ""),
        "publicGameHost": manifest_values.get("public_game_host") or prop_values.get("server.host", ""),
        "gamePort": manifest_values.get("game_port") or prop_values.get("server.port", ""),
        "httpPort": manifest_values.get("http_port") or prop_values.get("http.port", ""),
        "jaggrabPort": manifest_values.get("jaggrab_port") or prop_values.get("jaggrab.port", ""),
        "agentBridgeUrl": manifest_values.get("agent_bridge_url") or prop_values.get("agent.bridge.url", ""),
        "passwordIncluded": False,
        "privateFilesIncluded": False,
        "runtimeTouched": False,
    }
    kit_manifest = [
        "generated_at={}".format(metadata["generatedAt"]),
        "username={}".format(username),
        "character={}".format(character),
        "client_archive={}".format(client_archive.name),
        "client_archive_sha256={}".format(client_sha),
        "handoff_note_sha256={}".format(handoff_sha),
        "expected_external_transport={}".format(metadata["expectedExternalTransport"]),
        "public_game_host={}".format(metadata["publicGameHost"]),
        "game_port={}".format(metadata["gamePort"]),
        "http_port={}".format(metadata["httpPort"]),
        "jaggrab_port={}".format(metadata["jaggrabPort"]),
        "agent_bridge_url={}".format(metadata["agentBridgeUrl"]),
        "password_included: 0",
        "private_files_included: 0",
        "runtime_touched: 0",
        "",
    ]

    with zipfile.ZipFile(str(output), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zip_info(kit_dir + "/", 0o755), b"")
        add_file(archive, client_archive, kit_dir + "/" + client_archive.name)
        add_text(archive, kit_dir + "/README-FIRST.md", handoff_text)
        add_file(archive, checksums, kit_dir + "/client-SHA256SUMS.txt")
        add_file(archive, manifest, kit_dir + "/client-MANIFEST.txt")
        add_text(archive, kit_dir + "/KIT-MANIFEST.txt", "\n".join(kit_manifest))
        add_text(archive, kit_dir + "/KIT-METADATA.json", json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    metadata["playerKit"] = str(output)
    metadata["playerKitSha256"] = sha256_file(output)
    verification = verify_generated_kit(output, prepared_dir, username, character, client_archive, handoff_note)
    metadata["selfVerified"] = True
    metadata["clientArchiveMatchesExpected"] = verification.get("clientArchiveMatchesExpected")
    metadata["handoffNoteMatchesExpected"] = verification.get("handoffNoteMatchesExpected")
    return metadata


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create a public-safe per-player zip containing the downloadable client archive, "
            "README-first handoff note, and checksums, then self-verify it. "
            "Passwords and private runtime files are never included."
        )
    )
    parser.add_argument("username", help="Player account username.")
    parser.add_argument("--character", default="", help="Allowed/logged-in character. Defaults to username.")
    parser.add_argument("--prepared-dir", default=str(DEFAULT_PREPARED_DIR),
            help="Directory created by prepare-external-deployment.py. Defaults to dist/external-deployment.")
    parser.add_argument("--client-dist", default="", help="Packaged client directory. Defaults to PREPARED_DIR/agent-scape-client.")
    parser.add_argument("--client-archive", default="", help="Client zip path. Defaults to PREPARED_DIR/agent-scape-client.zip.")
    parser.add_argument("--handoff-note", default="",
            help="Public handoff note path. Defaults to PREPARED_DIR/player-handoff-USERNAME.md and is rendered if missing.")
    parser.add_argument("--agent-gateway-url", default="",
            help="Optional HTTPS /agent gateway URL used only if the handoff note must be rendered.")
    parser.add_argument("--output", default="", help="Output player kit zip. Defaults to PREPARED_DIR/player-kit-USERNAME.zip.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary.")
    args = parser.parse_args()

    metadata = build_kit(args)
    if args.json:
        print(json.dumps(metadata, indent=2, sort_keys=True))
    else:
        print("ok: wrote player kit {}".format(metadata["playerKit"]))
        print("player kit SHA-256: {}".format(metadata["playerKitSha256"]))
        print("self verified: yes")
        print("password included: no")
        print("private files included: no")
        print("runtime: not started, stopped, or restarted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
