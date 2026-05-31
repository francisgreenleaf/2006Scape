#!/usr/bin/env python3
"""Validate ML2 transition catalog and mixed route-step contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Optional


ML2_ROOT = Path(__file__).resolve().parents[1]
if str(ML2_ROOT) not in sys.path:
    sys.path.insert(0, str(ML2_ROOT))

from ml_routing.paths import ensure_tool_imports  # noqa: E402
from ml_routing.validation import validate_db  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate ML2 transition catalog data.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when warnings are present.")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    ensure_tool_imports()
    import navdb  # type: ignore  # noqa: WPS433

    _args = build_parser().parse_args(list(argv) if argv is not None else None)
    result = validate_db(navdb.load_db())
    print(json.dumps(result, indent=2, sort_keys=True))
    if _args.strict and int(result.get("routeWarningCount") or 0) > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
