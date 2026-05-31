"""Shared path helpers for the 2006Scape ML routing package."""

from pathlib import Path
import os
import sys


ML_ROOT = Path(__file__).resolve().parents[1]
NAV_ROOT = ML_ROOT.parent
REPO_ROOT = NAV_ROOT.parent
TOOLS_DIR = NAV_ROOT / "tools"
ARTIFACT_ROOT = Path(os.environ.get("ROUTE_ML_ARTIFACT_ROOT", ML_ROOT / "artifacts")).resolve()


def ensure_tool_imports():
    """Make existing navigation tools importable without packaging the repo."""
    path = str(TOOLS_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)


def ensure_artifact_dirs():
    for name in ("datasets", "models", "benchmarks", "runs"):
        (ARTIFACT_ROOT / name).mkdir(parents=True, exist_ok=True)


def timestamp_id(value):
    return value.strftime("%Y%m%dT%H%M%SZ")


def latest_json(root, pattern="*.json"):
    if not root.exists():
        return None
    files = sorted(root.glob(pattern))
    return files[-1] if files else None


def portable_artifact_path(path):
    """Return a clone-safe path for committed artifact manifests."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ML_ROOT))
    except ValueError:
        try:
            return str(resolved.relative_to(REPO_ROOT))
        except ValueError:
            return str(resolved)


def resolve_artifact_path(value):
    """Resolve manifest paths written relative to the ML folder."""
    path = Path(value)
    if path.is_absolute():
        return path
    text = str(path)
    if text.startswith("agent-navigation/"):
        return (REPO_ROOT / path).resolve()
    return (ML_ROOT / path).resolve()
