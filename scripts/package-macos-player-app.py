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
import struct
import subprocess
import sys
import zlib
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
set -u

APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT_DIR="$APP_ROOT/Resources/2006scape-client"
LOG_DIR="${HOME:-/tmp}/Library/Logs/2006Scape"
if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
    LOG_DIR="/tmp"
fi
LOG_FILE="$LOG_DIR/2006Scape-launch.log"

show_error() {
    local message="$1"
    if command -v osascript >/dev/null 2>&1; then
        osascript \\
            -e 'on run argv' \\
            -e 'display dialog (item 1 of argv) with title "2006Scape" buttons {"OK"} default button "OK" with icon caution' \\
            -e 'end run' \\
            "$message" >/dev/null 2>&1 || true
    fi
}

{
    echo ""
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Starting 2006Scape from $APP_ROOT"
} >>"$LOG_FILE" 2>&1
exec >>"$LOG_FILE" 2>&1

export PATH="/opt/homebrew/opt/openjdk/bin:/opt/homebrew/bin:/usr/local/opt/openjdk/bin:/usr/local/bin:/Library/Java/JavaVirtualMachines/temurin-8.jdk/Contents/Home/bin:${PATH:-}"
export CLIENT_DOCK_NAME="2006Scape"
if [[ -f "$APP_ROOT/Resources/2006Scape.icns" ]]; then
    export CLIENT_DOCK_ICON="$APP_ROOT/Resources/2006Scape.icns"
fi

if [[ ! -d "$CLIENT_DIR" ]]; then
    show_error "2006Scape could not find its bundled client files. Reopen the DMG or download a fresh package. Log: $LOG_FILE"
    exit 1
fi
if [[ ! -x "$CLIENT_DIR/run-macos-linux.sh" ]]; then
    show_error "2006Scape could not find its launcher. Reopen the DMG or download a fresh package. Log: $LOG_FILE"
    exit 1
fi

cd "$CLIENT_DIR" || exit 1
set +e
"$CLIENT_DIR/run-macos-linux.sh" "$@"
status=$?
set -e
if [[ "$status" -ne 0 ]]; then
    show_error "2006Scape could not start. Install Java 8 or newer, then try again. Details were written to: $LOG_FILE"
fi
exit "$status"
""",
        encoding="utf-8",
    )
    chmod_executable(path)


def png_chunk(kind, data):
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_png_rgba(path, width, height, pixels):
    rows = []
    stride = width * 4
    for y in range(height):
        rows.append(b"\x00" + bytes(pixels[y * stride : (y + 1) * stride]))
    raw = b"".join(rows)
    payload = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            png_chunk(b"IDAT", zlib.compress(raw, 9)),
            png_chunk(b"IEND", b""),
        ]
    )
    path.write_bytes(payload)


def blend_pixel(pixels, width, x, y, color):
    if x < 0 or y < 0 or x >= width:
        return
    offset = (y * width + x) * 4
    if offset < 0 or offset + 4 > len(pixels):
        return
    sr, sg, sb, sa = color
    if sa >= 255:
        pixels[offset : offset + 4] = bytes((sr, sg, sb, 255))
        return
    if sa <= 0:
        return
    alpha = sa / 255.0
    inv = 1.0 - alpha
    dr, dg, db, da = pixels[offset : offset + 4]
    out_a = min(255, int(sa + da * inv))
    pixels[offset] = int(sr * alpha + dr * inv)
    pixels[offset + 1] = int(sg * alpha + dg * inv)
    pixels[offset + 2] = int(sb * alpha + db * inv)
    pixels[offset + 3] = out_a


def draw_rect(pixels, width, height, x0, y0, x1, y1, color):
    for y in range(max(0, y0), min(height, y1)):
        row = y * width
        for x in range(max(0, x0), min(width, x1)):
            offset = (row + x) * 4
            pixels[offset : offset + 4] = bytes(color)


def draw_circle(pixels, width, height, cx, cy, radius, color):
    r2 = radius * radius
    for y in range(max(0, cy - radius), min(height, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(width, cx + radius + 1)):
            if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= r2:
                blend_pixel(pixels, width, x, y, color)


def rounded_rect_contains(x, y, x0, y0, x1, y1, radius):
    if x < x0 or x >= x1 or y < y0 or y >= y1:
        return False
    if x0 + radius <= x < x1 - radius or y0 + radius <= y < y1 - radius:
        return True
    cx = x0 + radius if x < x0 + radius else x1 - radius - 1
    cy = y0 + radius if y < y0 + radius else y1 - radius - 1
    return (x - cx) * (x - cx) + (y - cy) * (y - cy) <= radius * radius


def draw_rounded_rect(pixels, width, height, x0, y0, x1, y1, radius, color):
    for y in range(max(0, y0), min(height, y1)):
        for x in range(max(0, x0), min(width, x1)):
            if rounded_rect_contains(x, y, x0, y0, x1, y1, radius):
                blend_pixel(pixels, width, x, y, color)


def draw_segment_digit(pixels, width, height, digit, x, y, w, h, color):
    thickness = max(1, h // 7)
    pad = max(1, thickness // 2)
    segments = {
        "a": (x + pad, y, x + w - pad, y + thickness),
        "b": (x + w - thickness, y + pad, x + w, y + h // 2 - pad),
        "c": (x + w - thickness, y + h // 2 + pad, x + w, y + h - pad),
        "d": (x + pad, y + h - thickness, x + w - pad, y + h),
        "e": (x, y + h // 2 + pad, x + thickness, y + h - pad),
        "f": (x, y + pad, x + thickness, y + h // 2 - pad),
        "g": (x + pad, y + h // 2 - thickness // 2, x + w - pad, y + h // 2 + thickness // 2),
    }
    active = {
        "0": "abcdef",
        "1": "bc",
        "2": "abged",
        "3": "abgcd",
        "4": "fgbc",
        "5": "afgcd",
        "6": "afgecd",
        "7": "abc",
        "8": "abcdefg",
        "9": "abfgcd",
    }[digit]
    shadow = (35, 34, 28, 155)
    for key in active:
        sx0, sy0, sx1, sy1 = segments[key]
        draw_rect(pixels, width, height, sx0 + max(1, thickness // 4), sy0 + max(1, thickness // 4), sx1 + max(1, thickness // 4), sy1 + max(1, thickness // 4), shadow)
    for key in active:
        draw_rect(pixels, width, height, *segments[key], color)


def write_icon_png(path, size):
    pixels = bytearray(size * size * 4)
    s = lambda value: max(1, int(round(value * size)))

    draw_rounded_rect(pixels, size, size, s(0.04), s(0.04), s(0.96), s(0.96), s(0.18), (17, 74, 50, 255))
    draw_rounded_rect(pixels, size, size, s(0.08), s(0.08), s(0.92), s(0.92), s(0.14), (35, 112, 68, 255))

    for i in range(s(0.08)):
        draw_rounded_rect(
            pixels,
            size,
            size,
            s(0.09) + i,
            s(0.09) + i,
            s(0.91) - i,
            s(0.91) - i,
            max(1, s(0.13) - i),
            (214, 170, 79, 55),
        )

    # River slash and path give the icon a tiny map feel without needing asset files.
    for offset in range(-s(0.045), s(0.045) + 1):
        for t in range(s(0.10), s(0.90)):
            x = t
            y = int(s(0.22) + (t - s(0.10)) * 0.48) + offset
            blend_pixel(pixels, size, x, y, (65, 145, 176, 210))

    draw_circle(pixels, size, size, s(0.50), s(0.50), s(0.31), (235, 201, 116, 245))
    draw_circle(pixels, size, size, s(0.50), s(0.50), s(0.26), (54, 88, 59, 255))
    draw_circle(pixels, size, size, s(0.50), s(0.50), s(0.22), (42, 128, 78, 255))

    digit_color = (251, 230, 157, 255)
    draw_segment_digit(pixels, size, size, "0", s(0.23), s(0.35), s(0.23), s(0.31), digit_color)
    draw_segment_digit(pixels, size, size, "6", s(0.54), s(0.35), s(0.23), s(0.31), digit_color)
    draw_circle(pixels, size, size, s(0.73), s(0.28), max(1, s(0.055)), (181, 59, 49, 255))
    draw_circle(pixels, size, size, s(0.73), s(0.28), max(1, s(0.026)), (255, 236, 185, 255))

    write_png_rgba(path, size, size, pixels)


def write_app_icon(resources_dir):
    if sys.platform != "darwin" or shutil.which("iconutil") is None:
        return ""
    iconset = resources_dir / "AppIcon.iconset"
    if iconset.exists():
        if iconset.is_symlink():
            fail("refusing to replace symlinked iconset: {}".format(iconset))
        shutil.rmtree(str(iconset))
    iconset.mkdir(parents=True)
    specs = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]
    for filename, size in specs:
        write_icon_png(iconset / filename, size)
    icon_path = resources_dir / "2006Scape.icns"
    completed = subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(icon_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    shutil.rmtree(str(iconset))
    if completed.returncode != 0:
        fail("iconutil icon creation failed:\n{}".format((completed.stdout or "").strip()))
    return str(icon_path)


def write_info_plist(path, app_name, bundle_id, icon_file):
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
        "LSApplicationCategoryType": "public.app-category.games",
        "LSMinimumSystemVersion": "10.13",
        "NSHighResolutionCapable": True,
    }
    if icon_file:
        payload["CFBundleIconFile"] = "2006Scape"
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
    app_icon = write_app_icon(resources_dir)
    write_launcher(macos_dir / app_name)
    write_info_plist(contents_dir / "Info.plist", app_name, args.bundle_id, app_icon)
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
                "If macOS blocks a first launch, right-click 2006Scape.app and choose Open.",
                "If Java is missing or the client cannot start, the app shows an alert and writes a log to ~/Library/Logs/2006Scape/2006Scape-launch.log.",
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
        "appIcon": app_icon,
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
