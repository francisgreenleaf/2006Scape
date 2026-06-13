#!/usr/bin/env python3
"""Package non-secret deployment proof artifacts for handoff."""

import argparse
import datetime as _datetime
import hashlib
import io
import json
import os
import re
import sys
import tarfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "dist" / "deployment-proof-bundles"
DEFAULT_READINESS_REPORT = ROOT_DIR / "dist" / "deployment-readiness-report.md"
DEFAULT_READINESS_JSON = ROOT_DIR / "dist" / "deployment-readiness-report.json"
DEFAULT_CLIENT_DIST = ROOT_DIR / "dist" / "2006scape-client"
DEFAULT_SERVER_DEPLOYMENT_DIR = ROOT_DIR / "dist" / "server-deployment"
PREPARED_READINESS_REPORT = "deployment-readiness-report.md"
PREPARED_READINESS_JSON = "deployment-readiness-report.json"
PREPARED_CLIENT_DIST = "2006scape-client"
PREPARED_SERVER_DEPLOYMENT_DIR = "server-deployment"
PREPARED_PROOF_MANIFEST = "deployment-proof-manifest.json"

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR / "lib") not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR / "lib"))

from deployment_proof_manifest import read_manifest_values  # noqa: E402


CLIENT_METADATA_FILES = (
    "MANIFEST.txt",
    "SHA256SUMS",
    "README.txt",
    "client.properties",
)
SERVER_METADATA_FILES = (
    "README.md",
    "ServerConfig.json",
)
RUNTIME_ARCHIVE_RE = re.compile(r"(?m)^-\s*archive:\s*(.+?)\s*$")
RUNTIME_ARCHIVE_SHA_RE = re.compile(r"(?m)^-\s*backup archive sha256:\s*([0-9a-fA-F]{64})\s*$")


def utc_now():
    return _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0)


def iso_z(value):
    return value.isoformat().replace("+00:00", "Z")


def fail(message):
    raise SystemExit(message)


def set_owner_only(path):
    if os.name == "posix":
        path.chmod(0o600)


def reject_symlinked_output_path(path, label):
    if path.is_symlink():
        fail("refusing to write {} through symlink path: {}".format(label, path))
    parent = path.parent
    while True:
        if parent.is_symlink():
            fail("refusing to write {} through symlinked parent directory: {}".format(label, parent))
        if parent.exists():
            return
        if parent == parent.parent:
            break
        parent = parent.parent


def validate_source_file(path, label, required):
    candidate = Path(path)
    if not candidate.exists():
        if required:
            fail("{} is missing: {}".format(label, candidate))
        return None
    if candidate.is_symlink():
        fail("{} must not be a symlink: {}".format(label, candidate))
    if not candidate.is_file():
        fail("{} must be a regular file: {}".format(label, candidate))
    if is_sensitive_source_path(candidate):
        fail("{} points at runtime/secret-bearing data and cannot be bundled: {}".format(label, candidate))
    return candidate.resolve()


def is_sensitive_source_path(path):
    parts = [part.lower() for part in path.parts]
    if "secrets.json" in parts:
        return True
    for index, part in enumerate(parts):
        if part in ("accounts", "characters") and index > 0 and parts[index - 1] == "data":
            return True
    name = path.name.lower()
    if name.endswith((".tgz", ".tar", ".tar.gz", ".zip", ".jar")) and "runtime-data" in name:
        return True
    return False


def safe_archive_name(value):
    path = Path(value)
    clean_parts = []
    for part in path.parts:
        if part in ("", ".", "..", os.sep) or part.endswith(":"):
            continue
        clean = re.sub(r"[^A-Za-z0-9._-]+", "-", part).strip("-")
        if clean:
            clean_parts.append(clean)
    if not clean_parts:
        return "artifact"
    return "/".join(clean_parts)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_file(plan, source, archive_name, label, required=False):
    source_path = validate_source_file(source, label, required)
    if source_path is None:
        plan["skipped"].append({
            "label": label,
            "path": str(source),
            "reason": "missing",
        })
        return
    if archive_name.startswith("/") or ".." in Path(archive_name).parts:
        fail("unsafe archive path for {}: {}".format(label, archive_name))
    plan["files"].append({
        "source": source_path,
        "archivePath": archive_name,
        "label": label,
        "sha256": sha256_file(source_path),
        "size": source_path.stat().st_size,
    })


def add_text(tar, archive_name, text):
    data = text.encode("utf-8")
    info = tarfile.TarInfo(archive_name)
    info.size = len(data)
    info.mode = 0o600
    info.mtime = 0
    tar.addfile(info, io.BytesIO(data))


def load_json(path, label):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("{} is not valid JSON: {}: {}".format(label, path, exc))


def add_readiness_summary(metadata, readiness_json_path):
    if readiness_json_path is None:
        return
    data = load_json(readiness_json_path, "readiness JSON")
    metadata["readiness"] = {
        "status": data.get("status"),
        "deploymentProofStatus": data.get("deploymentProofStatus"),
        "liveChecksRequested": data.get("liveChecksRequested"),
        "liveDiscordRequested": data.get("liveDiscordRequested"),
        "remainingLiveProof": data.get("remainingLiveProof", []),
        "proofCoverage": data.get("proofCoverage", []),
        "markdownReport": data.get("markdownReport"),
    }


def runtime_archive_details(proof_path):
    try:
        text = Path(proof_path).read_text(encoding="utf-8")
    except OSError:
        return None
    archive_match = RUNTIME_ARCHIVE_RE.search(text)
    sha_match = RUNTIME_ARCHIVE_SHA_RE.search(text)
    if not archive_match and not sha_match:
        return None
    return {
        "proof": str(proof_path),
        "archive": archive_match.group(1).strip() if archive_match else "",
        "sha256": sha_match.group(1).lower() if sha_match else "",
        "reason": "runtime backup archive contains characters, account records, and secrets.json; proof bundle includes proof note only",
    }


def build_archive_readme(metadata):
    return """# 2006Scape Deployment Proof Bundle

Generated at: {generated_at}

This archive is a non-secret handoff bundle for external deployment proof review.
It includes readiness reports, a filled proof manifest when supplied, proof notes,
and selected client/server metadata.

It deliberately does not include runtime-data backup archives, character saves,
PBKDF2 account records, `data/secrets.json`, passwords, bridge tokens, or Discord
bot tokens. Keep the runtime backup archive on the deployed host or in the
operator's secure backup location; this bundle records the archive path/checksum
from the proof note when available.

`status: PASS` in a readiness report means the requested commands passed. Check
`deploymentProofStatus` and `remainingLiveProof` before calling a deployment
externally ready.

Files in this bundle are listed in `bundle-metadata.json`.
""".format(generated_at=metadata["generatedAt"])


def apply_prepared_dir_defaults(args):
    if not args.prepared_dir:
        return None
    prepared_dir = Path(args.prepared_dir)
    if args.readiness_report == str(DEFAULT_READINESS_REPORT):
        args.readiness_report = str(prepared_dir / PREPARED_READINESS_REPORT)
    if args.readiness_json == str(DEFAULT_READINESS_JSON):
        args.readiness_json = str(prepared_dir / PREPARED_READINESS_JSON)
    if args.client_dist == str(DEFAULT_CLIENT_DIST):
        args.client_dist = str(prepared_dir / PREPARED_CLIENT_DIST)
    if args.server_deployment_dir == str(DEFAULT_SERVER_DEPLOYMENT_DIR):
        args.server_deployment_dir = str(prepared_dir / PREPARED_SERVER_DEPLOYMENT_DIR)
    if not args.proof_manifest:
        manifest = prepared_dir / PREPARED_PROOF_MANIFEST
        if manifest.exists():
            args.proof_manifest = str(manifest)
    return prepared_dir


def main():
    parser = argparse.ArgumentParser(
        description="Package non-secret 2006Scape deployment proof artifacts into a tar.gz bundle."
    )
    parser.add_argument("--prepared-dir", default="",
            help=("Directory created by prepare-external-deployment.py. When set, default readiness, client, "
                  "server-deployment, and copied proof-manifest paths are resolved from that directory unless "
                  "the corresponding explicit flags are supplied."))
    parser.add_argument("--readiness-report", default=str(DEFAULT_READINESS_REPORT),
            help="Markdown readiness report to include when present.")
    parser.add_argument("--readiness-json", default=str(DEFAULT_READINESS_JSON),
            help="JSON readiness report to include when present.")
    parser.add_argument("--proof-manifest", default="",
            help="Filled deployment-proof-manifest JSON to validate and include.")
    parser.add_argument("--proof-file", action="append", default=[],
            help="Additional non-secret proof note to include. May be passed more than once.")
    parser.add_argument("--client-dist", default=str(DEFAULT_CLIENT_DIST),
            help="Packaged client directory whose metadata files should be included when present.")
    parser.add_argument("--server-deployment-dir", default=str(DEFAULT_SERVER_DEPLOYMENT_DIR),
            help="Rendered server-deployment directory whose metadata files should be included when present.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
            help="Directory for generated bundle when --archive is not supplied.")
    parser.add_argument("--archive", default="",
            help="Explicit output tar.gz path.")
    parser.add_argument("--include-desktop-evidence", action="store_true",
            help="Also include the desktop proof evidence file referenced by desktop proof notes.")
    parser.add_argument("--json", action="store_true",
            help="Print compact JSON instead of human lines.")
    args = parser.parse_args()
    prepared_dir = apply_prepared_dir_defaults(args)

    timestamp = utc_now()
    stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    archive_path = Path(args.archive) if args.archive else (
        Path(args.output_dir) / "2006scape-deployment-proof-{}.tgz".format(stamp)
    )
    reject_symlinked_output_path(archive_path, "archive")

    plan = {
        "files": [],
        "skipped": [],
        "excluded": [],
    }
    metadata = {
        "schemaVersion": 1,
        "generatedAt": iso_z(timestamp),
        "runtimeTouched": False,
        "sourceRoot": str(ROOT_DIR),
        "archive": str(archive_path),
        "included": [],
        "skipped": plan["skipped"],
        "excluded": plan["excluded"],
    }
    if prepared_dir is not None:
        metadata["preparedDir"] = str(prepared_dir)

    readiness_report = validate_source_file(args.readiness_report, "readiness report", False)
    if readiness_report:
        add_file(plan, readiness_report, "readiness/deployment-readiness-report.md", "readiness report")
    else:
        plan["skipped"].append({"label": "readiness report", "path": args.readiness_report, "reason": "missing"})

    readiness_json = validate_source_file(args.readiness_json, "readiness JSON", False)
    if readiness_json:
        add_file(plan, readiness_json, "readiness/deployment-readiness-report.json", "readiness JSON")
        add_readiness_summary(metadata, readiness_json)
    else:
        plan["skipped"].append({"label": "readiness JSON", "path": args.readiness_json, "reason": "missing"})

    manifest_values = {}
    if args.proof_manifest:
        proof_manifest = validate_source_file(args.proof_manifest, "deployment proof manifest", True)
        try:
            manifest_values = read_manifest_values(proof_manifest, allow_placeholders=False)
        except ValueError as exc:
            fail("deployment proof manifest is invalid: {}".format(exc))
        add_file(plan, proof_manifest, "proof/deployment-proof-manifest.json", "deployment proof manifest", True)
        metadata["proofManifest"] = {
            "path": str(proof_manifest),
            "fieldCount": len(manifest_values),
            "requireFullProof": manifest_values.get("require_full_proof") is True,
            "live": manifest_values.get("live") is True,
            "liveDiscord": manifest_values.get("live_discord") is True,
        }

    proof_files = list(args.proof_file)
    for key, label in (
        ("desktop_client_proof_file", "desktop client proof"),
        ("runtime_data_backup_proof_file", "runtime data backup proof"),
    ):
        value = manifest_values.get(key)
        if value:
            proof_files.append(str(value))
            if key == "runtime_data_backup_proof_file":
                details = runtime_archive_details(value)
                if details:
                    plan["excluded"].append(details)

    seen_proof_paths = set()
    proof_index = 0
    for proof in proof_files:
        proof_path = validate_source_file(proof, "proof file", True)
        if proof_path in seen_proof_paths:
            continue
        seen_proof_paths.add(proof_path)
        proof_index += 1
        archive_name = "proof/{:02d}-{}".format(proof_index, safe_archive_name(proof_path.name))
        add_file(plan, proof_path, archive_name, "proof file", True)
        if args.include_desktop_evidence:
            add_desktop_evidence_if_present(plan, proof_path, proof_index)

    client_dist = Path(args.client_dist)
    for relative in CLIENT_METADATA_FILES:
        add_file(
            plan,
            client_dist / relative,
            "client/{}".format(relative),
            "client metadata {}".format(relative),
            required=False,
        )

    server_deployment_dir = Path(args.server_deployment_dir)
    for relative in SERVER_METADATA_FILES:
        add_file(
            plan,
            server_deployment_dir / relative,
            "server-deployment/{}".format(relative),
            "server deployment metadata {}".format(relative),
            required=False,
        )

    if not plan["files"]:
        fail("no proof artifacts were available to bundle")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(str(archive_path), "w:gz") as archive:
        for item in plan["files"]:
            archive.add(str(item["source"]), arcname=item["archivePath"], recursive=False)
            metadata["included"].append({
                "label": item["label"],
                "source": str(item["source"]),
                "archivePath": item["archivePath"],
                "sha256": item["sha256"],
                "size": item["size"],
            })
        add_text(archive, "README.md", build_archive_readme(metadata))
        add_text(archive, "bundle-metadata.json", json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    set_owner_only(archive_path)
    digest = sha256_file(archive_path)
    metadata["archiveSha256"] = digest

    if args.json:
        print(json.dumps({
            "archive": str(archive_path),
            "sha256": digest,
            "includedCount": len(metadata["included"]),
            "excludedCount": len(metadata["excluded"]),
            "runtimeTouched": False,
        }, indent=2, sort_keys=True))
    else:
        print("archive: {}".format(archive_path))
        print("sha256: {}".format(digest))
        print("included: {}".format(len(metadata["included"])))
        print("excluded: {}".format(len(metadata["excluded"])))
        print("runtime: not started, stopped, or restarted")
    return 0


def add_desktop_evidence_if_present(plan, proof_path, proof_index):
    try:
        text = Path(proof_path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    evidence_match = re.search(r"(?m)^-\s*evidence:\s*(.+?)\s*$", text)
    if not evidence_match:
        return
    evidence = validate_source_file(evidence_match.group(1).strip(), "desktop proof evidence", True)
    add_file(
        plan,
        evidence,
        "proof/{:02d}-desktop-evidence-{}".format(proof_index, safe_archive_name(evidence.name)),
        "desktop proof evidence",
        True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
