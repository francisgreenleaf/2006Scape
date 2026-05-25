#!/usr/bin/env python3
"""List, search, show, and run registered 2006Scape helper scripts."""

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
NAV_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
REGISTRY_PATH = NAV_ROOT / "data" / "script_registry.json"


def load_registry():
    with REGISTRY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle).get("scripts", [])


def fields(script):
    values = [
        script.get("id", ""),
        script.get("name", ""),
        script.get("kind", ""),
        script.get("description", ""),
    ]
    values.extend(script.get("aliases") or [])
    values.extend(script.get("tags") or [])
    return [str(value).lower() for value in values if value]


def script_matches(script, query, tag=None):
    if tag and tag.lower() not in [str(item).lower() for item in script.get("tags", [])]:
        return False
    if not query:
        return True
    terms = [term.lower() for term in query.split() if term.strip()]
    haystack = fields(script)
    for term in terms:
        if any(char in term for char in "*?[]"):
            if not any(fnmatch.fnmatch(value, term) for value in haystack):
                return False
        elif not any(term in value for value in haystack):
            return False
    return True


def compact(script):
    return {
        "id": script.get("id"),
        "name": script.get("name"),
        "kind": script.get("kind"),
        "path": script.get("path"),
        "description": script.get("description"),
        "aliases": script.get("aliases", []),
        "tags": script.get("tags", []),
    }


def print_scripts(scripts, as_json=False):
    if as_json:
        print(json.dumps([compact(script) for script in scripts], indent=2, sort_keys=True))
        return
    for script in scripts:
        print("{id}\t{kind}\t{path}\t{name} - {description}".format(
            id=script.get("id", ""),
            kind=script.get("kind", ""),
            path=script.get("path", ""),
            name=script.get("name", ""),
            description=script.get("description", ""),
        ))


def resolve_script(scripts, query):
    lowered = query.lower()
    exact = [
        script for script in scripts
        if script.get("id", "").lower() == lowered
        or script.get("name", "").lower() == lowered
        or lowered in [str(alias).lower() for alias in script.get("aliases", [])]
    ]
    if len(exact) == 1:
        return exact[0]
    matches = [script for script in scripts if script_matches(script, query)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit("no registered script matches: {}".format(query))
    raise SystemExit("ambiguous script '{}': {}".format(
        query, ", ".join(sorted(script.get("id", "") for script in matches))))


def command_for(script, extra_args):
    path = REPO_ROOT / script["path"]
    if path.suffix == ".py":
        return [sys.executable, str(path)] + extra_args
    return [str(path)] + extra_args


def main(argv=None):
    parser = argparse.ArgumentParser(description="Search and run registered 2006Scape scripts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List registered scripts.")
    list_parser.add_argument("--tag")
    list_parser.add_argument("--json", action="store_true")

    search_parser = subparsers.add_parser("search", help="Search scripts by id, alias, tag, wildcard, or description.")
    search_parser.add_argument("query", nargs="*")
    search_parser.add_argument("--tag")
    search_parser.add_argument("--json", action="store_true")

    show_parser = subparsers.add_parser("show", help="Show one script's metadata.")
    show_parser.add_argument("script")
    show_parser.add_argument("--json", action="store_true")

    run_parser = subparsers.add_parser("run", aliases=["use"], help="Run a registered script with optional args after --.")
    run_parser.add_argument("script")
    run_parser.add_argument("script_args", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)
    scripts = load_registry()

    if args.command == "list":
        print_scripts([script for script in scripts if script_matches(script, "", args.tag)], args.json)
        return 0
    if args.command == "search":
        print_scripts([script for script in scripts if script_matches(script, " ".join(args.query), args.tag)], args.json)
        return 0
    if args.command == "show":
        script = resolve_script(scripts, args.script)
        print(json.dumps(script if args.json else compact(script), indent=2, sort_keys=True))
        return 0

    script = resolve_script(scripts, args.script)
    extra_args = list(args.script_args)
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]
    return subprocess.call(command_for(script, extra_args), cwd=str(REPO_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
