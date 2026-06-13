#!/usr/bin/env python3
"""Summarize an existing external-deployment readiness JSON report."""

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_READINESS_JSON = ROOT_DIR / "dist" / "deployment-readiness-report.json"
PREPARED_READINESS_JSON = "deployment-readiness-report.json"

FULL_PROOF_STATUSES = {
    "LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_PROOF_RECORDED_DISCORD_NOT_REQUESTED",
    "FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED",
}
FULL_DISCORD_PROOF_STATUS = "FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED"


def fail(message, code=1):
    print("error: {}".format(message), file=sys.stderr)
    raise SystemExit(code)


def resolve_readiness_json(args):
    if args.readiness_json:
        return Path(args.readiness_json)
    if args.prepared_dir:
        return Path(args.prepared_dir) / PREPARED_READINESS_JSON
    return DEFAULT_READINESS_JSON


def load_report(path):
    if path.is_symlink():
        fail("readiness JSON must not be a symlink: {}".format(path))
    if not path.is_file():
        fail("readiness JSON is missing: {}".format(path))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("readiness JSON is invalid: {}: {}".format(path, exc))
    if not isinstance(data, dict):
        fail("readiness JSON must contain an object: {}".format(path))
    return data


def externally_ready(data, require_discord=False):
    if data.get("status") != "PASS":
        return False
    proof_status = data.get("deploymentProofStatus")
    if require_discord:
        return proof_status == FULL_DISCORD_PROOF_STATUS
    return proof_status in FULL_PROOF_STATUSES


def summarize(data, path, require_discord=False):
    coverage = data.get("proofCoverage", [])
    if not isinstance(coverage, list):
        coverage = []
    remaining = data.get("remainingLiveProof", [])
    if not isinstance(remaining, list):
        remaining = []
    return {
        "readinessJson": str(path),
        "status": data.get("status"),
        "deploymentProofStatus": data.get("deploymentProofStatus"),
        "externallyReady": externally_ready(data, require_discord),
        "requireDiscord": bool(require_discord),
        "liveChecksRequested": data.get("liveChecksRequested"),
        "liveDiscordRequested": data.get("liveDiscordRequested"),
        "markdownReport": data.get("markdownReport"),
        "remainingLiveProofCount": len(remaining),
        "remainingLiveProof": remaining,
        "proofCoverage": coverage,
    }


def print_human(summary, show_covered=False):
    print("readinessJson: {}".format(summary["readinessJson"]))
    print("status: {}".format(summary.get("status")))
    print("deploymentProofStatus: {}".format(summary.get("deploymentProofStatus")))
    print("externallyReady: {}".format("yes" if summary["externallyReady"] else "no"))
    print("liveChecksRequested: {}".format("yes" if summary.get("liveChecksRequested") else "no"))
    print("liveDiscordRequested: {}".format("yes" if summary.get("liveDiscordRequested") else "no"))
    if summary.get("markdownReport"):
        print("markdownReport: {}".format(summary["markdownReport"]))
    remaining = summary.get("remainingLiveProof", [])
    print("remainingLiveProofCount: {}".format(len(remaining)))
    if remaining:
        print("remainingLiveProof:")
        for item in remaining:
            print("- {}".format(item))
    coverage = summary.get("proofCoverage", [])
    if coverage:
        print("proofCoverage:")
        for row in coverage:
            if not isinstance(row, dict):
                continue
            status = row.get("status", "")
            if not show_covered and status in ("RECORDED", "MANUAL_PROOF_RECORDED",
                    "DELIVERY_LOG_PROOF_REQUESTED", "LOG_PROOF_REQUESTED",
                    "ABSENCE_PROOF_REQUESTED"):
                continue
            requirement = row.get("requirement", "unknown")
            detail = row.get("detail", "")
            suffix = " ({})".format(detail) if detail else ""
            print("- {}: {}{}".format(requirement, status, suffix))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read an existing deployment-readiness-report JSON and summarize whether external readiness is actually proven."
    )
    parser.add_argument("--readiness-json",
            help="Path to deployment-readiness-report JSON. Defaults to dist/deployment-readiness-report.json unless --prepared-dir is supplied.")
    parser.add_argument("--prepared-dir",
            help="Prepared deployment directory containing deployment-readiness-report.json, usually dist/external-deployment.")
    parser.add_argument("--json", action="store_true",
            help="Print a machine-readable summary.")
    parser.add_argument("--show-covered", action="store_true",
            help="Include proof-coverage rows that are already recorded, not only missing/manual/final-gate rows.")
    parser.add_argument("--require-discord", action="store_true",
            help="Treat Discord round-trip proof as required even when the readiness report says Discord proof was not requested.")
    parser.add_argument("--fail-if-not-ready", action="store_true",
            help="Exit 2 when status/deploymentProofStatus do not prove full external readiness.")
    args = parser.parse_args(argv)

    path = resolve_readiness_json(args)
    data = load_report(path)
    summary = summarize(data, path, args.require_discord)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_human(summary, args.show_covered)
    if args.fail_if_not_ready and not summary["externallyReady"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
