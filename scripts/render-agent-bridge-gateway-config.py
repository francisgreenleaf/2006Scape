#!/usr/bin/env python3
"""Render an HTTPS reverse-proxy config for the 2006Scape agent bridge."""

from __future__ import annotations

import argparse
from pathlib import Path


APPROVED_ENDPOINTS = {
    "/agent/health": ("GET", "agent_bridge_status"),
    "/agent/session/claim": ("POST", "agent_bridge_claim"),
    "/agent/session/event": ("POST", "agent_bridge_api"),
    "/agent/personality/pending": ("GET", "agent_bridge_api"),
    "/agent/personality/complete": ("POST", "agent_bridge_api"),
    "/agent/personality/failed": ("POST", "agent_bridge_api"),
    "/agent/tool": ("POST", "agent_bridge_tool"),
}


def fail(message: str) -> None:
    raise SystemExit("gateway config render failed: {}".format(message))


def single_line(value: str, label: str) -> str:
    text = str(value or "").strip()
    if not text or any(ord(ch) < 32 for ch in text):
        fail("{} must be a non-empty single-line value".format(label))
    return text


def render_nginx(args: argparse.Namespace) -> str:
    server_name = single_line(args.server_name, "--server-name")
    cert_path = single_line(args.cert_path, "--cert-path")
    key_path = single_line(args.key_path, "--key-path")
    access_log = single_line(args.access_log, "--access-log")
    error_log = single_line(args.error_log, "--error-log")
    upstream = single_line(args.upstream, "--upstream").rstrip("/")
    if not upstream.startswith("http://127.0.0.1:") and not upstream.startswith("http://localhost:"):
        fail("--upstream must point to the loopback AgentBridgeServer")
    body_size = single_line(args.body_size, "--body-size")

    lines = [
        "# Generated 2006Scape agent bridge gateway for Nginx.",
        "# Public clients should reach only this HTTPS gateway.",
        "# Keep AgentBridgeServer itself bound to 127.0.0.1 and do not expose port 43610.",
        "",
        "limit_req_zone $binary_remote_addr zone=agent_bridge_claim:10m rate={};".format(args.claim_rate),
        "limit_req_zone $binary_remote_addr zone=agent_bridge_api:10m rate={};".format(args.api_rate),
        "limit_req_zone $binary_remote_addr zone=agent_bridge_tool:10m rate={};".format(args.tool_rate),
        "",
        "log_format agent_bridge '$remote_addr forwarded=$http_x_forwarded_for '",
        "                        'method=$request_method uri=$request_uri status=$status '",
        "                        'bytes=$body_bytes_sent request_time=$request_time';",
        "",
        "server {",
        "    listen 443 ssl http2;",
        "    server_name {};".format(server_name),
        "",
        "    ssl_certificate {};".format(cert_path),
        "    ssl_certificate_key {};".format(key_path),
        "",
        "    access_log {} agent_bridge;".format(access_log),
        "    error_log {};".format(error_log),
        "",
        "    client_max_body_size {};".format(body_size),
        "    client_body_timeout 10s;",
        "    keepalive_timeout 15s;",
        "",
        "    proxy_http_version 1.1;",
        "    proxy_set_header Host $host;",
        "    proxy_set_header X-Real-IP $remote_addr;",
        "    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
        "    proxy_set_header X-Forwarded-Proto $scheme;",
        "    proxy_connect_timeout 2s;",
        "    proxy_send_timeout 180s;",
        "    proxy_read_timeout 180s;",
        "",
    ]
    for path, (method, zone) in APPROVED_ENDPOINTS.items():
        lines.extend([
            "    location = {} {{".format(path),
            "        limit_except {} {{".format(method),
            "            deny all;",
            "        }",
            "        limit_req zone={} burst={} nodelay;".format(zone, args.burst),
            "        proxy_pass {}{};".format(upstream, path),
            "    }",
            "",
        ])
    lines.extend([
        "    location ^~ /agent/ {",
        "        return 404;",
        "    }",
        "}",
        "",
        "server {",
        "    listen 80;",
        "    server_name {};".format(server_name),
        "    return 301 https://$host$request_uri;",
        "}",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a public-safe Nginx gateway for approved /agent/* endpoints.")
    parser.add_argument("--server-name", required=True, help="Public HTTPS host name for the gateway.")
    parser.add_argument("--output", default="", help="Output path. Prints to stdout when omitted.")
    parser.add_argument("--cert-path", default="/etc/letsencrypt/live/AGENT_HOST/fullchain.pem")
    parser.add_argument("--key-path", default="/etc/letsencrypt/live/AGENT_HOST/privkey.pem")
    parser.add_argument("--upstream", default="http://127.0.0.1:43610")
    parser.add_argument("--body-size", default="64k")
    parser.add_argument("--claim-rate", default="10r/m")
    parser.add_argument("--api-rate", default="60r/m")
    parser.add_argument("--tool-rate", default="120r/m")
    parser.add_argument("--burst", type=int, default=20)
    parser.add_argument("--access-log", default="/var/log/nginx/2006scape-agent-bridge-access.log")
    parser.add_argument("--error-log", default="/var/log/nginx/2006scape-agent-bridge-error.log")
    args = parser.parse_args()
    if args.burst < 0:
        fail("--burst must be non-negative")
    text = render_nginx(args)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
