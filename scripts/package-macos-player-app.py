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
DEFAULT_ICON_PNG = ROOT_DIR / "scripts" / "assets" / "agent-scape-icon.png"
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
CLIENT_DIR="$APP_ROOT/Resources/agent-scape-client"
LOG_DIR="${HOME:-/tmp}/Library/Logs/agent-scape"
if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
    LOG_DIR="/tmp"
fi
LOG_FILE="$LOG_DIR/agent-scape-launch.log"

show_error() {
    local message="$1"
    if command -v osascript >/dev/null 2>&1; then
        osascript \\
            -e 'on run argv' \\
            -e 'display dialog (item 1 of argv) with title "agent-scape" buttons {"OK"} default button "OK" with icon caution' \\
            -e 'end run' \\
            "$message" >/dev/null 2>&1 || true
    fi
}

{
    echo ""
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Starting agent-scape from $APP_ROOT"
} >>"$LOG_FILE" 2>&1
exec >>"$LOG_FILE" 2>&1

export PATH="/opt/homebrew/opt/openjdk/bin:/opt/homebrew/bin:/usr/local/opt/openjdk/bin:/usr/local/bin:/Library/Java/JavaVirtualMachines/temurin-8.jdk/Contents/Home/bin:${PATH:-}"
export CLIENT_DOCK_NAME="agent-scape"
if [[ -f "$APP_ROOT/Resources/agent-scape.icns" ]]; then
    export CLIENT_DOCK_ICON="$APP_ROOT/Resources/agent-scape.icns"
fi

if [[ ! -d "$CLIENT_DIR" ]]; then
    show_error "agent-scape could not find its bundled client files. Reopen the DMG or download a fresh package. Log: $LOG_FILE"
    exit 1
fi
if [[ ! -x "$CLIENT_DIR/run-macos-linux.sh" ]]; then
    show_error "agent-scape could not find its launcher. Reopen the DMG or download a fresh package. Log: $LOG_FILE"
    exit 1
fi

cd "$CLIENT_DIR" || exit 1
set +e
"$CLIENT_DIR/run-macos-linux.sh" "$@"
status=$?
set -e
if [[ "$status" -ne 0 ]]; then
    show_error "agent-scape could not start. Install Java 8 or newer, then try again. Details were written to: $LOG_FILE"
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


def draw_line(pixels, width, height, x0, y0, x1, y1, radius, color):
    steps = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) * 2))
    for index in range(steps + 1):
        t = index / steps
        x = int(round(x0 + (x1 - x0) * t))
        y = int(round(y0 + (y1 - y0) * t))
        draw_circle(pixels, width, height, x, y, radius, color)


def draw_triangle(pixels, width, height, points, color):
    min_x = max(0, min(x for x, _ in points))
    max_x = min(width - 1, max(x for x, _ in points))
    min_y = max(0, min(y for _, y in points))
    max_y = min(height - 1, max(y for _, y in points))
    (x1, y1), (x2, y2), (x3, y3) = points
    denom = ((y2 - y3) * (x1 - x3)) + ((x3 - x2) * (y1 - y3))
    if denom == 0:
        return
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / denom
            b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / denom
            c = 1.0 - a - b
            if a >= 0 and b >= 0 and c >= 0:
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

    draw_rounded_rect(pixels, size, size, s(0.04), s(0.04), s(0.96), s(0.96), s(0.18), (9, 21, 33, 255))
    draw_rounded_rect(pixels, size, size, s(0.08), s(0.08), s(0.92), s(0.92), s(0.14), (14, 42, 52, 255))
    draw_rounded_rect(pixels, size, size, s(0.13), s(0.13), s(0.87), s(0.87), s(0.10), (18, 58, 64, 255))

    for coord in (0.28, 0.45, 0.62, 0.78):
        draw_line(pixels, size, size, s(coord), s(0.16), s(coord), s(0.84), max(1, s(0.006)), (88, 122, 128, 90))
        draw_line(pixels, size, size, s(0.16), s(coord), s(0.84), s(coord), max(1, s(0.006)), (88, 122, 128, 90))

    route = [
        (s(0.21), s(0.70)),
        (s(0.36), s(0.55)),
        (s(0.48), s(0.64)),
        (s(0.71), s(0.33)),
    ]
    for start, end in zip(route, route[1:]):
        draw_line(pixels, size, size, start[0], start[1], end[0], end[1], max(1, s(0.020)), (28, 221, 191, 255))
        draw_line(pixels, size, size, start[0], start[1], end[0], end[1], max(1, s(0.008)), (197, 255, 244, 255))
    for index, (x, y) in enumerate(route):
        draw_circle(pixels, size, size, x, y, max(2, s(0.055)), (7, 25, 32, 245))
        draw_circle(pixels, size, size, x, y, max(1, s(0.034)), (255, 198, 92, 255) if index in (0, len(route) - 1) else (51, 226, 196, 255))

    # Abstract navigation cursor: no text mark, so it scales cleanly in Finder.
    shadow = [(s(0.53), s(0.20)), (s(0.42), s(0.79)), (s(0.61), s(0.63))]
    cursor = [(s(0.52), s(0.17)), (s(0.40), s(0.76)), (s(0.59), s(0.60))]
    cutout = [(s(0.51), s(0.36)), (s(0.46), s(0.62)), (s(0.54), s(0.56))]
    draw_triangle(pixels, size, size, shadow, (2, 8, 13, 130))
    draw_triangle(pixels, size, size, cursor, (236, 250, 247, 255))
    draw_triangle(pixels, size, size, cutout, (14, 42, 52, 255))
    draw_line(pixels, size, size, s(0.52), s(0.19), s(0.58), s(0.59), max(1, s(0.007)), (94, 234, 212, 210))

    write_png_rgba(path, size, size, pixels)


def resize_icon_png(source, dest, size):
    completed = subprocess.run(
        [
            "sips",
            "-s",
            "format",
            "png",
            "-z",
            str(size),
            str(size),
            str(source),
            "--out",
            str(dest),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        fail("failed to resize app icon PNG:\n{}".format((completed.stdout or "").strip()))


def write_app_icon(resources_dir, icon_png_source=None):
    icon_path = resources_dir / "agent-scape.icns"
    iconset = resources_dir / "AppIcon.iconset"
    if iconset.exists():
        if iconset.is_symlink():
            fail("refusing to replace symlinked iconset: {}".format(iconset))
        shutil.rmtree(str(iconset))
    iconset.mkdir(parents=True)
    specs = [
        ("icp4", "icon_16x16.png", 16),
        ("icp5", "icon_32x32.png", 32),
        ("icp6", "icon_32x32@2x.png", 64),
        ("ic07", "icon_128x128.png", 128),
        ("ic08", "icon_256x256.png", 256),
        ("ic09", "icon_512x512.png", 512),
        ("ic10", "icon_512x512@2x.png", 1024),
    ]
    chunks = []
    try:
        for icon_type, filename, size in specs:
            png_path = iconset / filename
            if icon_png_source:
                resize_icon_png(icon_png_source, png_path, size)
            else:
                write_icon_png(png_path, size)
            data = png_path.read_bytes()
            chunks.append(icon_type.encode("ascii") + struct.pack(">I", len(data) + 8) + data)
        body = b"".join(chunks)
        icon_path.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)
    finally:
        shutil.rmtree(str(iconset))
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
        payload["CFBundleIconFile"] = "agent-scape"
    with path.open("wb") as handle:
        plistlib.dump(payload, handle, sort_keys=True)


def write_dmg_readme(dmg_root, username, character):
    (dmg_root / "README.md").write_text(
        "\n".join(
            [
                "# agent-scape",
                "",
                "1. Open `agent-scape.app`.",
                "2. Log in as `{}` / `{}` with the password sent separately.".format(username, character),
                "3. Play.",
                "",
                "If macOS blocks the first launch, right-click `agent-scape.app` and choose `Open`.",
                "If it still will not launch, send Kevin `~/Library/Logs/agent-scape/agent-scape-launch.log`.",
                "",
                "Agent features are available in the in-game Agent Terminal or with `/agent ...`.",
                "",
                "Project: https://github.com/francisgreenleaf/2006Scape",
                "Mac package PR: https://github.com/francisgreenleaf/2006Scape/pull/37",
                "",
                "Use only the password made for this server. Do not reuse a RuneScape.com password.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def build_app(args):
    username = normalize_player_name(args.username, "username")
    character = normalize_player_name(args.character or args.username, "character")
    stem = safe_stem(username)
    prepared_dir = resolve_under_root(Path(args.prepared_dir))
    reject_symlink(prepared_dir, "prepared deployment directory")
    if not prepared_dir.is_dir():
        fail("prepared deployment directory is missing: {}".format(prepared_dir))

    client_dist = resolve_under_root(Path(args.client_dist)) if args.client_dist else prepared_dir / "agent-scape-client"
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
    app_name = args.app_name.strip() or "agent-scape"
    app_path = output_dir / "{}.app".format(app_name)
    icon_png = resolve_under_root(Path(args.icon_png)) if args.icon_png else DEFAULT_ICON_PNG
    dmg_output = (
        resolve_under_root(Path(args.dmg_output))
        if args.dmg_output
        else prepared_dir / "agent-scape-player-{}-mac.dmg".format(stem)
    )

    validate_public_tree(client_dist, "client distribution")
    handoff_text = validate_public_text(handoff_note, "player handoff note")
    if icon_png.exists():
        reject_symlink(icon_png, "macOS app icon PNG")
        if not icon_png.is_file():
            fail("macOS app icon PNG must be a file: {}".format(icon_png))
        if shutil.which("sips") is None:
            if args.icon_png:
                fail("custom macOS app icon PNG requires sips on PATH to resize: {}".format(icon_png))
            icon_png = None
    elif args.icon_png:
        fail("macOS app icon PNG is missing: {}".format(icon_png))
    else:
        icon_png = None
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

    copy_tree(client_dist, resources_dir / "agent-scape-client")
    app_icon = write_app_icon(resources_dir, icon_png)
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
        write_dmg_readme(dmg_root, username, character)
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
                "agent-scape",
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
        "appIconSource": str(icon_png) if icon_png else "",
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
            "Create a Finder-friendly macOS .app wrapper around a prepared agent-scape "
            "client distribution, and optionally create a DMG. Passwords, account records, "
            "secrets, bridge sessions, and runtime data are never included."
        )
    )
    parser.add_argument("username", help="Player account username for the handoff note.")
    parser.add_argument("--character", default="", help="Allowed/logged-in character. Defaults to username.")
    parser.add_argument("--prepared-dir", default=str(DEFAULT_PREPARED_DIR))
    parser.add_argument("--client-dist", default="", help="Prepared client folder. Defaults to PREPARED_DIR/agent-scape-client.")
    parser.add_argument("--handoff-note", default="", help="Player handoff note. Defaults to PREPARED_DIR/player-handoff-USERNAME.md.")
    parser.add_argument("--output-dir", default="", help="Output directory for the .app bundle.")
    parser.add_argument("--app-name", default="agent-scape", help="macOS app display/executable name.")
    parser.add_argument("--bundle-id", default="com.agentscape.client", help="macOS bundle identifier.")
    parser.add_argument(
        "--icon-png",
        default="",
        help="Source PNG for the app icon. Defaults to scripts/assets/agent-scape-icon.png when present.",
    )
    parser.add_argument("--dmg", action="store_true", help="Also build a compressed DMG with hdiutil.")
    parser.add_argument("--dmg-output", default="", help="DMG output path. Defaults to PREPARED_DIR/agent-scape-player-USERNAME-mac.dmg.")
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
