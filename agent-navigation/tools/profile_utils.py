#!/usr/bin/env python3
"""Shared profile resolution and profile-scoped local paths."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
NAV_ROOT = SCRIPT_DIR.parent
LOCAL_ROOT = NAV_ROOT / ".local"
DEFAULT_PROFILE = "MrFlame"


def safe_profile(value: str | None) -> str:
    text = "".join(
        ch for ch in str(value or "").strip().lower()
        if ch.isalnum() or ch in ("-", "_")
    )
    return text or "default"


def compact_profile_key(value: str | None) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def normalize_player_name(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def is_default_profile(profile: str | None) -> bool:
    value = str(profile or "").strip()
    return not value or safe_profile(value) == safe_profile(DEFAULT_PROFILE)


def profile_from_environment(trace: bool = False, default: str = "") -> str:
    if trace:
        return (
            os.environ.get("RS_TRACE_PROFILE")
            or os.environ.get("RS_PROFILE")
            or os.environ.get("RSBRIDGE_PROFILE")
            or default
        )
    return (
        os.environ.get("RS_PROFILE")
        or os.environ.get("RSBRIDGE_PROFILE")
        or os.environ.get("RS_TRACE_PROFILE")
        or default
    )


def resolve_profile(value: str | None = "", trace: bool = False, default: str = DEFAULT_PROFILE) -> str:
    return str(value or profile_from_environment(trace=trace, default=default) or default).strip()


def profile_from_argv(argv: list[str] | None = None, trace: bool = False, default: str = "") -> str:
    args = list(sys.argv[1:] if argv is None else argv)
    option_order = ("--trace-profile", "--profile") if trace else ("--profile", "--trace-profile")
    for option in option_order:
        prefix = option + "="
        for index, arg in enumerate(args):
            if arg == option and index + 1 < len(args):
                return resolve_profile(args[index + 1], trace=trace, default=default)
            if arg.startswith(prefix):
                return resolve_profile(arg[len(prefix):], trace=trace, default=default)
    return resolve_profile(trace=trace, default=default)


def profile_display_name(profile: str | None = "", default_text: str = "Mrflame") -> str:
    value = resolve_profile(profile, default=DEFAULT_PROFILE)
    if is_default_profile(value):
        return default_text
    return value


def profile_suffix(profile: str | None = "") -> str:
    if is_default_profile(profile):
        return ""
    return "-" + safe_profile(profile)


def profile_scoped_file(directory: Path, basename: str, suffix: str, profile: str | None = "") -> Path:
    if is_default_profile(profile):
        return directory / (basename + suffix)
    return directory / (basename + profile_suffix(profile) + suffix)


def profile_scoped_dir(directory: Path, profile: str | None = "") -> Path:
    if is_default_profile(profile):
        return directory
    return directory / safe_profile(profile)


def session_file_for_profile(profile: str | None = "", local_root: Path = LOCAL_ROOT) -> Path:
    override = os.environ.get("RSBRIDGE_SESSION_FILE")
    if override:
        return Path(override).expanduser()
    selected = resolve_profile(profile, trace=False, default=DEFAULT_PROFILE)
    if is_default_profile(selected):
        return local_root / "rsbridge-session.json"
    return local_root / ("rsbridge-session-{}.json".format(safe_profile(selected)))


def session_player_name(session_file: Path | None = None) -> str:
    path = session_file or session_file_for_profile("")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(data.get("playerName") or "").strip()


def run_evidence_path(profile: str | None = "", basename: str = "ml-route-executor") -> Path:
    selected = resolve_profile(profile, default="")
    directory = LOCAL_ROOT / "run-evidence"
    if is_default_profile(selected):
        return directory / (basename + ".routes.jsonl")
    return directory / safe_profile(selected) / (basename + ".routes.jsonl")


def route_definition_dir(profile: str | None = "") -> Path:
    base = LOCAL_ROOT / "ml-route-definitions"
    return profile_scoped_dir(base, resolve_profile(profile, default=""))


def canonical_map_paths(profile: str | None, variant: str) -> tuple[Path, Path]:
    topology = NAV_ROOT / "topology"
    summaries = LOCAL_ROOT / "map-summaries"
    selected = resolve_profile(profile, trace=True, default="")
    suffix = profile_suffix(selected)
    if variant == "profile":
        return (
            topology / ("movement-topology{}-v4.png".format(suffix)),
            summaries / ("movement-topology{}-v4.json".format(suffix)),
        )
    if variant == "heat":
        return (
            topology / ("movement-topology{}-v5-heatmap.png".format(suffix)),
            summaries / ("movement-topology{}-v5-heatmap.json".format(suffix)),
        )
    if variant == "fog":
        return (
            topology / ("movement-topology{}-v6.png".format(suffix)),
            summaries / ("movement-topology{}-v6.json".format(suffix)),
        )
    raise ValueError("unknown map variant: {}".format(variant))
