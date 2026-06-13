#!/usr/bin/env python3
"""Focused live network proof for external 2006Scape deployments."""

import argparse
import importlib.util
import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT_DIR / "2006Scape Server" / "ServerConfig.json"


def fail(message):
    raise SystemExit("deployment network probe failed: {}".format(message))


def load_verifier():
    path = ROOT_DIR / "scripts" / "verify-external-deployment.py"
    spec = importlib.util.spec_from_file_location("verify_external_deployment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.fail = fail
    return module


verifier = load_verifier()


def probe_network(config_path, timeout=2.0, allow_wildcard_bind=False,
        allow_placeholder_network_config=False, allow_untrusted_client_tls=False,
        tls_sni_host=""):
    config_path = Path(config_path)
    warnings = []
    config = verifier.load_json(config_path)
    if not bool(config.get("external_players_enabled", False)):
        fail("external_players_enabled is false in {}".format(config_path))
    tls_sni_host = verifier.validate_tls_sni_host(tls_sni_host, allow_placeholder_network_config)
    verifier.run_preflight(config_path, allow_wildcard_bind)
    verifier.verify_network_placeholders(config, allow_placeholder_network_config)
    checks = verifier.verify_live_ports(
        config,
        timeout,
        warnings,
        allow_untrusted_client_tls=allow_untrusted_client_tls,
        tls_sni_host=tls_sni_host,
    )
    return {
        "success": True,
        "config": str(config_path),
        "checks": checks,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Probe live public game/cache reachability and confirm the agent bridge "
            "is not reachable externally. Does not package, build, log in, start, stop, or restart runtime."
        )
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
            help="ServerConfig.json to inspect for public host, ports, file_server, and transport mode.")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--tls-sni-host", default="",
            help="SNI/hostname for client_tls_tunnel TLS checks. Defaults to public_game_host.")
    parser.add_argument("--allow-untrusted-client-tls", action="store_true",
            help="Allow self-signed or otherwise untrusted TLS certs for private tunnel tests.")
    parser.add_argument("--allow-placeholder-network-config", action="store_true",
            help="Allow tracked sample public_game_host/bind host placeholders. Source validation only.")
    parser.add_argument("--allow-wildcard-bind", action="store_true",
            help="Allow deliberate wildcard binds when the config confirms them.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.timeout <= 0:
        fail("--timeout must be positive")

    result = probe_network(
        args.config,
        timeout=args.timeout,
        allow_wildcard_bind=args.allow_wildcard_bind,
        allow_placeholder_network_config=args.allow_placeholder_network_config,
        allow_untrusted_client_tls=args.allow_untrusted_client_tls,
        tls_sni_host=args.tls_sni_host,
    )
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        for warning in result["warnings"]:
            print("warning: {}".format(warning))
        for check in result["checks"]:
            print("live-check: {}".format(check))
        print("ok: deployment network probe passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
