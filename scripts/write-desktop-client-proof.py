#!/usr/bin/env python3
"""Write a readiness-compatible desktop client coexistence proof note."""

import argparse
import datetime as _datetime
import json
import os
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT_DIR / "2006Scape Server" / "ServerConfig.json"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "dist" / "deployment-proofs"
PLACEHOLDER_RE = re.compile(
    r"(?i)(REPLACE_|TODO|TBD|YYYY-MM-DD|PATH_TO_|FILL_ME|LOCAL_USERNAME|EXTERNAL_USERNAME)"
)


def utc_now():
    return _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0)


def fail(message):
    raise SystemExit(message)


def shell_quote(value):
    return repr(str(value))


def reject_placeholder(value, label):
    text = str(value or "").strip()
    if not text:
        fail("{} is required".format(label))
    if PLACEHOLDER_RE.search(text):
        fail("{} still looks like placeholder text: {}".format(label, text))
    return text


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


def validate_evidence(path):
    if path.is_symlink():
        fail("desktop client proof evidence must not be a symlink: {}".format(path))
    if not path.is_file():
        fail("desktop client proof evidence is missing or not a file: {}".format(path))
    if path.stat().st_size <= 0:
        fail("desktop client proof evidence must not be empty: {}".format(path))
    return path.resolve()


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
    data["desktop_client_proof_file"] = value
    manifest_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def read_config(path):
    config_path = Path(path)
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        fail("could not read config {}: {}".format(config_path, exc))


def default_public_host(config):
    return str(config.get("public_game_host", "") or "").strip()


def default_transport(config):
    mode = str(config.get("external_transport_mode", "") or "").strip()
    if mode == "private_network":
        return "private_network VPN"
    return mode


def write_proof(proof_path, values):
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    text = """# Desktop Client Coexistence Proof

- date: {date}
- timestamp: {timestamp}
- server config: {config}
- public host: {public_host}
- external transport path: {transport}
- same-host/local Java client: {same_host_client} connected through {local_host}
- external Java client: {external_client} connected through {transport} to {public_host}
- observed: both desktop clients remained online at the same time
- evidence: {evidence}
- readiness argument: --desktop-client-proof-file {proof}
- command: scripts/write-desktop-client-proof.py --config {config_q} --same-host-client {same_host_q} --external-client {external_q} --transport {transport_q} --public-host {public_host_q} --evidence {evidence_q} --output {proof_q}{manifest_arg}
""".format(**values)
    proof_path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Write a readiness-compatible desktop client coexistence proof note."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
            help="ServerConfig used for the desktop-client proof note.")
    parser.add_argument("--same-host-client", required=True,
            help="Name or short description of the same-host/local Java client.")
    parser.add_argument("--external-client", required=True,
            help="Name or short description of the external Java client.")
    parser.add_argument("--transport", default="",
            help="External transport path, for example direct_tcp, tailscale, wireguard, VPN, or client_tls_tunnel.")
    parser.add_argument("--public-host", default="",
            help="Public/VPN/tunnel host used by the external client.")
    parser.add_argument("--local-host", default="127.0.0.1",
            help="Same-host local client connection host.")
    parser.add_argument("--evidence", required=True,
            help="Screenshot or log file proving both desktop clients were online together.")
    parser.add_argument("--output", default="",
            help="Proof note path. Defaults under dist/deployment-proofs with a UTC timestamp.")
    parser.add_argument("--proof-manifest", default="",
            help=("Optional existing deployment-proof-manifest JSON to update with the generated "
                  "desktop_client_proof_file path. Other manifest fields are preserved."))
    parser.add_argument("--json", action="store_true",
            help="Print compact JSON instead of human lines.")
    args = parser.parse_args()

    timestamp = utc_now()
    stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    proof_path = Path(args.output) if args.output else (
        DEFAULT_OUTPUT_DIR / "desktop-client-proof-{}.md".format(stamp)
    )
    reject_symlinked_output_path(proof_path, "proof")
    proof_manifest_path = Path(args.proof_manifest) if args.proof_manifest else None
    if proof_manifest_path:
        read_proof_manifest(proof_manifest_path)

    evidence_path = validate_evidence(Path(args.evidence))
    config = read_config(args.config) if not args.public_host or not args.transport else {}
    public_host = reject_placeholder(args.public_host or default_public_host(config), "--public-host")
    transport = reject_placeholder(args.transport or default_transport(config), "--transport")
    local_host = reject_placeholder(args.local_host, "--local-host")
    same_host_client = reject_placeholder(args.same_host_client, "--same-host-client")
    external_client = reject_placeholder(args.external_client, "--external-client")

    values = {
        "config": args.config,
        "config_q": shell_quote(args.config),
        "date": timestamp.date().isoformat(),
        "evidence": evidence_path,
        "evidence_q": shell_quote(evidence_path),
        "external_client": external_client,
        "external_q": shell_quote(external_client),
        "local_host": local_host,
        "manifest_arg": (
            " --proof-manifest {}".format(shell_quote(args.proof_manifest))
            if args.proof_manifest else ""
        ),
        "proof": proof_path,
        "proof_q": shell_quote(proof_path),
        "public_host": public_host,
        "public_host_q": shell_quote(public_host),
        "same_host_client": same_host_client,
        "same_host_q": shell_quote(same_host_client),
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "transport": transport,
        "transport_q": shell_quote(transport),
    }
    write_proof(proof_path, values)
    manifest_value = ""
    if proof_manifest_path:
        manifest_value = write_proof_manifest(proof_manifest_path, proof_path)

    if args.json:
        payload = {
            "proof": str(proof_path),
            "evidence": str(evidence_path),
            "publicHost": public_host,
            "transport": transport,
            "runtimeTouched": False,
        }
        if args.proof_manifest:
            payload["proofManifest"] = args.proof_manifest
            payload["manifestDesktopClientProofFile"] = manifest_value
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("proof: {}".format(proof_path))
        print("evidence: {}".format(evidence_path))
        if args.proof_manifest:
            print("proof manifest: {}".format(args.proof_manifest))
            print("manifest desktop_client_proof_file: {}".format(manifest_value))
        print("runtime: not started, stopped, or restarted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
