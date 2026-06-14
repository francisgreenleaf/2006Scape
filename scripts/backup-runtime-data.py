#!/usr/bin/env python3
"""Back up 2006Scape runtime data and write readiness proof."""

import argparse
import datetime as _datetime
import hashlib
import json
import os
import tarfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT_DIR / "2006Scape Server" / "data"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "dist" / "runtime-data-backups"
RUNTIME_ENTRIES = (
    ("characters", "character saves"),
    ("accounts", "PBKDF2 account records"),
    ("secrets.json", "Discord secrets"),
)


def utc_now():
    return _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0)


def set_owner_only(path):
    if os.name == "posix":
        path.chmod(0o600)


def fail(message):
    raise SystemExit(message)


def validate_data_paths(data_dir):
    original_data_dir = Path(data_dir)
    if original_data_dir.is_symlink():
        fail("refusing to back up symlinked data directory: {}".format(original_data_dir))
    data_dir = original_data_dir.resolve()
    if not data_dir.exists():
        fail("data directory does not exist: {}".format(data_dir))
    if not data_dir.is_dir():
        fail("data path is not a directory: {}".format(data_dir))
    if data_dir.is_symlink():
        fail("refusing to back up symlinked data directory: {}".format(data_dir))

    sources = []
    for relative, label in RUNTIME_ENTRIES:
        path = data_dir / relative
        if not path.exists():
            fail("missing {} at {}".format(label, path))
        if path.is_symlink():
            fail("refusing to back up symlinked {} path: {}".format(label, path))
        if relative.endswith(".json"):
            if not path.is_file():
                fail("{} path is not a regular file: {}".format(label, path))
        elif not path.is_dir():
            fail("{} path is not a directory: {}".format(label, path))
        sources.append((relative, label, path))
    return data_dir, sources


def iter_safe_children(root):
    if root.is_file():
        return
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            fail("refusing to include symlinked runtime-data path: {}".format(path))
        yield path


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


def add_path(archive, data_dir, path):
    archive_name = str(path.relative_to(data_dir))
    archive.add(str(path), arcname=archive_name, recursive=False)


def write_archive(data_dir, sources, archive_path):
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    file_count = 0
    directory_count = 0
    with tarfile.open(str(archive_path), "w:gz") as archive:
        for _relative, _label, source in sources:
            add_path(archive, data_dir, source)
            if source.is_dir():
                directory_count += 1
            else:
                file_count += 1
            for path in iter_safe_children(source):
                add_path(archive, data_dir, path)
                if path.is_dir():
                    directory_count += 1
                else:
                    file_count += 1
    set_owner_only(archive_path)
    return file_count, directory_count


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def proof_manifest_value(proof_path, manifest_path):
    resolved_proof = proof_path.resolve()
    manifest_parent = manifest_path.parent.resolve()
    try:
        return str(resolved_proof.relative_to(manifest_parent))
    except ValueError:
        return str(resolved_proof)


def read_proof_manifest(manifest_path):
    manifest_path = Path(manifest_path)
    reject_symlinked_output_path(manifest_path, "proof manifest")
    if not manifest_path.is_file():
        fail("proof manifest is missing or not a regular file: {}".format(manifest_path))
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("proof manifest is not valid JSON: {}: {}".format(manifest_path, exc))
    if not isinstance(data, dict):
        fail("proof manifest must contain a JSON object: {}".format(manifest_path))
    return data


def write_proof_manifest(manifest_path, proof_path):
    manifest_path = Path(manifest_path)
    data = read_proof_manifest(manifest_path)
    value = proof_manifest_value(proof_path, manifest_path)
    data["runtime_data_backup_proof_file"] = value
    manifest_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def write_proof(proof_path, data_dir, archive_path, timestamp, digest, file_count, directory_count,
        proof_manifest=""):
    manifest_arg = ""
    if proof_manifest:
        manifest_arg = " --proof-manifest {}".format(repr(str(proof_manifest)))
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    text = """# Runtime Data Backup Proof

- date: {date}
- timestamp: {timestamp}
- characters: backed up {data_dir}/characters
- accounts: backed up {data_dir}/accounts
- Discord secrets: backed up {data_dir}/secrets.json
- archive: {archive}
- backup archive sha256: {digest}
- files: {file_count}
- directories: {directory_count}
- runtime: not started, stopped, or restarted
- readiness argument: --runtime-data-backup-proof-file {proof}
- command: scripts/backup-runtime-data.py --data-dir {data_dir_q} --archive {archive_q} --proof-file {proof_q}{manifest_arg}
""".format(
        archive=archive_path,
        archive_q=repr(str(archive_path)),
        data_dir=data_dir,
        data_dir_q=repr(str(data_dir)),
        date=timestamp.date().isoformat(),
        digest=digest,
        directory_count=directory_count,
        file_count=file_count,
        manifest_arg=manifest_arg,
        proof=proof_path,
        proof_q=repr(str(proof_path)),
        timestamp=timestamp.isoformat().replace("+00:00", "Z"),
    )
    proof_path.write_text(text, encoding="utf-8")
    set_owner_only(proof_path)


def main():
    parser = argparse.ArgumentParser(
        description="Back up 2006Scape runtime data and write a readiness-compatible proof file."
    )
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR),
            help="Path to the deployed '2006Scape Server/data' directory.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
            help="Directory for generated archive/proof files when explicit paths are not supplied.")
    parser.add_argument("--archive", default="",
            help="Explicit archive path. Defaults under --output-dir with a UTC timestamp.")
    parser.add_argument("--proof-file", default="",
            help="Explicit proof-note path. Defaults under --output-dir with a UTC timestamp.")
    parser.add_argument("--proof-manifest", default="",
            help=("Optional existing deployment-proof-manifest JSON to update with the generated "
                  "runtime_data_backup_proof_file path. Other manifest fields are preserved."))
    args = parser.parse_args()

    timestamp = utc_now()
    stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir)
    archive_path = Path(args.archive) if args.archive else output_dir / "2006scape-runtime-data-{}.tgz".format(stamp)
    proof_path = Path(args.proof_file) if args.proof_file else output_dir / "runtime-data-backup-proof-{}.md".format(stamp)

    data_dir, sources = validate_data_paths(Path(args.data_dir))
    reject_symlinked_output_path(archive_path, "archive")
    reject_symlinked_output_path(proof_path, "proof")
    if archive_path.resolve() == proof_path.resolve():
        fail("--archive and --proof-file must be different paths")
    proof_manifest_path = Path(args.proof_manifest) if args.proof_manifest else None
    if proof_manifest_path:
        read_proof_manifest(proof_manifest_path)

    file_count, directory_count = write_archive(data_dir, sources, archive_path)
    digest = sha256_file(archive_path)
    write_proof(
        proof_path,
        data_dir,
        archive_path,
        timestamp,
        digest,
        file_count,
        directory_count,
        proof_manifest=args.proof_manifest,
    )
    manifest_value = ""
    if proof_manifest_path:
        manifest_value = write_proof_manifest(proof_manifest_path, proof_path)

    print("archive: {}".format(archive_path))
    print("proof: {}".format(proof_path))
    if args.proof_manifest:
        print("proof manifest: {}".format(args.proof_manifest))
        print("manifest runtime_data_backup_proof_file: {}".format(manifest_value))
    print("sha256: {}".format(digest))
    print("runtime: not started, stopped, or restarted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
