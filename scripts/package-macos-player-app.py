#!/usr/bin/env python3
"""Build a macOS .app wrapper and optional DMG for a prepared player package."""

import argparse
import datetime as _datetime
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PREPARED_DIR = ROOT_DIR / "dist" / "external-deployment"
USERNAME_RE = re.compile(r"[a-z0-9 .]{1,12}", re.IGNORECASE)
SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9_.-]+")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?im)^\s*[A-Za-z0-9_]*(password|token|secret|nonce|api[_-]?key|bot[_-]?token)[A-Za-z0-9_]*\s*="
)
SENSITIVE_PARTS = {"accounts", "characters", "private"}
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


def chmod_executable(path):
    try:
        os.chmod(path, 0o755)
    except OSError:
        pass


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


def is_sensitive_name(name):
    lower = name.lower()
    return (
        lower in SENSITIVE_NAMES
        or "credential" in lower
        or "password" in lower
        or "secret" in lower
        or "token" in lower
        or "nonce" in lower
        or "api-key" in lower
        or "apikey" in lower
        or "bot-token" in lower
    )


def validate_public_tree(root, label):
    reject_symlink(root, label)
    if not root.is_dir():
        fail("{} is missing: {}".format(label, root))
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        lower_parts = [part.lower() for part in rel.parts]
        if path.is_symlink():
            fail("{} contains a symlink: {}".format(label, path))
        if any(part in SENSITIVE_PARTS for part in lower_parts):
            fail("{} contains private/runtime data path: {}".format(label, path))
        if is_sensitive_name(path.name):
            fail("{} contains a secret-like filename: {}".format(label, path))


def validate_public_text(path, label):
    reject_symlink(path, label)
    if not path.is_file():
        fail("{} is missing: {}".format(label, path))
    text = path.read_text(encoding="utf-8")
    if SECRET_ASSIGNMENT_RE.search(text):
        fail("{} appears to contain a secret-like assignment: {}".format(label, path))
    return text


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_tree(source, dest):
    if dest.exists():
        if dest.is_symlink():
            fail("refusing to replace symlinked output path: {}".format(dest))
        shutil.rmtree(str(dest))
    shutil.copytree(str(source), str(dest), symlinks=False)


def write_launcher(path):
    path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT_DIR="$APP_ROOT/Resources/2006scape-client"
cd "$CLIENT_DIR"
exec "$CLIENT_DIR/run-macos-linux.sh" "$@"
""",
        encoding="utf-8",
    )
    chmod_executable(path)


def write_info_plist(path, app_name, bundle_id):
    payload = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": app_name,
        "CFBundleExecutable": app_name,
        "CFBundleIdentifier": bundle_id,
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": app_name,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "10.13",
        "NSHighResolutionCapable": True,
    }
    with path.open("wb") as handle:
        plistlib.dump(payload, handle, sort_keys=True)


def build_app(args):
    username = normalize_player_name(args.username, "username")
    character = normalize_player_name(args.character or args.username, "character")
    stem = safe_stem(username)
    prepared_dir = resolve_under_root(Path(args.prepared_dir))
    reject_symlink(prepared_dir, "prepared deployment directory")
    if not prepared_dir.is_dir():
        fail("prepared deployment directory is missing: {}".format(prepared_dir))

    client_dist = resolve_under_root(Path(args.client_dist)) if args.client_dist else prepared_dir / "2006scape-client"
    handoff_note = (
        resolve_under_root(Path(args.handoff_note))
        if args.handoff_note
        else prepared_dir / "player-handoff-{}.md".format(stem)
    )
    output_dir = (
        resolve_under_root(Path(args.output_dir))
        if args.output_dir
        else prepared_dir / "macos-player-packages" / stem
    )
    app_name = args.app_name.strip() or "2006Scape"
    app_path = output_dir / "{}.app".format(app_name)
    dmg_output = (
        resolve_under_root(Path(args.dmg_output))
        if args.dmg_output
        else prepared_dir / "2006scape-player-{}-mac.dmg".format(stem)
    )

    validate_public_tree(client_dist, "client distribution")
    handoff_text = validate_public_text(handoff_note, "player handoff note")
    reject_symlinked_output_path(output_dir, "macOS player package directory")
    reject_symlinked_output_path(app_path, "macOS app bundle")
    if args.dmg:
        reject_symlinked_output_path(dmg_output, "macOS DMG")

    output_dir.mkdir(parents=True, exist_ok=True)
    contents_dir = app_path / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    if app_path.exists():
        if app_path.is_symlink():
            fail("refusing to replace symlinked app bundle: {}".format(app_path))
        shutil.rmtree(str(app_path))
    macos_dir.mkdir(parents=True)
    resources_dir.mkdir(parents=True)

    copy_tree(client_dist, resources_dir / "2006scape-client")
    write_launcher(macos_dir / app_name)
    write_info_plist(contents_dir / "Info.plist", app_name, args.bundle_id)
    validate_public_tree(app_path, "macOS app bundle")

    generated_at = utc_now()
    dmg_path = ""
    dmg_sha = ""
    if args.dmg:
        if sys.platform != "darwin" or shutil.which("hdiutil") is None:
            fail("--dmg requires macOS with hdiutil on PATH")
        dmg_root = output_dir / "dmg-root"
        reject_symlinked_output_path(dmg_root, "DMG staging directory")
        if dmg_root.exists():
            if dmg_root.is_symlink():
                fail("refusing to replace symlinked DMG staging directory: {}".format(dmg_root))
            shutil.rmtree(str(dmg_root))
        dmg_root.mkdir(parents=True)
        copy_tree(app_path, dmg_root / app_path.name)
        (dmg_root / "README-FIRST.md").write_text(handoff_text, encoding="utf-8")
        (dmg_root / "OPEN-2006SCAPE.txt").write_text(
            "\n".join([
                "Open 2006Scape.app to launch the game client.",
                "Read README-FIRST.md for the account name, transport setup, and login steps.",
                "The password is not included in this DMG; the operator sends it separately.",
                "",
            ]),
            encoding="utf-8",
        )
        validate_public_tree(dmg_root, "DMG staging directory")
        if dmg_output.exists():
            if dmg_output.is_symlink():
                fail("refusing to replace symlinked DMG output: {}".format(dmg_output))
            dmg_output.unlink()
        completed = subprocess.run(
            [
                "hdiutil",
                "create",
                "-volname",
                "2006Scape",
                "-srcfolder",
                str(dmg_root),
                "-ov",
                "-format",
                "UDZO",
                str(dmg_output),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            fail("hdiutil DMG creation failed:\n{}".format((completed.stdout or "").strip()))
        dmg_path = str(dmg_output)
        dmg_sha = sha256_file(dmg_output)

    return {
        "success": True,
        "generatedAt": iso_z(generated_at),
        "username": username,
        "character": character,
        "appBundle": str(app_path),
        "dmg": dmg_path,
        "dmgSha256": dmg_sha,
        "handoffNote": str(handoff_note),
        "clientDist": str(client_dist),
        "passwordIncluded": False,
        "privateFilesIncluded": False,
        "runtimeTouched": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create a Finder-friendly macOS .app wrapper around a prepared 2006Scape "
            "client distribution, and optionally create a DMG. Passwords, account records, "
            "secrets, bridge sessions, and runtime data are never included."
        )
    )
    parser.add_argument("username", help="Player account username for the handoff note.")
    parser.add_argument("--character", default="", help="Allowed/logged-in character. Defaults to username.")
    parser.add_argument("--prepared-dir", default=str(DEFAULT_PREPARED_DIR))
    parser.add_argument("--client-dist", default="", help="Prepared client folder. Defaults to PREPARED_DIR/2006scape-client.")
    parser.add_argument("--handoff-note", default="", help="Player handoff note. Defaults to PREPARED_DIR/player-handoff-USERNAME.md.")
    parser.add_argument("--output-dir", default="", help="Output directory for the .app bundle.")
    parser.add_argument("--app-name", default="2006Scape", help="macOS app display/executable name.")
    parser.add_argument("--bundle-id", default="com.2006scape.client", help="macOS bundle identifier.")
    parser.add_argument("--dmg", action="store_true", help="Also build a compressed DMG with hdiutil.")
    parser.add_argument("--dmg-output", default="", help="DMG output path. Defaults to PREPARED_DIR/2006scape-player-USERNAME-mac.dmg.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary.")
    args = parser.parse_args()

    summary = build_app(args)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print("ok: wrote macOS app {}".format(summary["appBundle"]))
        if summary["dmg"]:
            print("ok: wrote DMG {}".format(summary["dmg"]))
            print("DMG SHA-256: {}".format(summary["dmgSha256"]))
        print("password included: no")
        print("private files included: no")
        print("runtime: not started, stopped, or restarted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
