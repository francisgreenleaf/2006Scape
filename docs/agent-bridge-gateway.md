# 2006Scape Agent Bridge Gateway

The Java `AgentBridgeServer` is a bearer-token control plane and must stay bound
to loopback, normally `127.0.0.1:43610`. Remote players and repo-side Codex
threads should reach it only through an HTTPS gateway that exposes approved
`/agent/*` endpoints.

Read `docs/config/templates/agent-bridge-gateway.nginx.conf` for the static
template, or render a filled Nginx config:

```sh
scripts/render-agent-bridge-gateway-config.py \
  --server-name agents.example.com \
  --cert-path /etc/letsencrypt/live/agents.example.com/fullchain.pem \
  --key-path /etc/letsencrypt/live/agents.example.com/privkey.pem \
  --output /etc/nginx/sites-available/2006scape-agent-bridge.conf
```

The template includes:

- explicit allow-listing for `/agent/health`, `/agent/session/claim`,
  `/agent/session/event`, `/agent/personality/*`, and `/agent/tool`;
- per-IP rate limits for claim, API, and tool traffic;
- `client_max_body_size 64k`;
- forwarded-IP headers and access logs that include forwarded IPs;
- a default 404 for unapproved `/agent/` paths;
- proxying only to the loopback upstream.

After enabling the site, run:

```sh
sudo nginx -t
sudo systemctl reload nginx
scripts/probe-agent-bridge-gateway.py --gateway-url https://agents.example.com
```

## Temporary Self-Signed Gateway

If no DNS name exists yet, a short-lived self-signed certificate on the VPS IP
is acceptable for operator testing. Keep it temporary: normal players should use
a real domain certificate from a trusted CA.

For a self-signed IP certificate, the gateway probe can skip trust validation
while still checking the endpoint allow-list and raw bridge non-exposure:

```sh
scripts/probe-agent-bridge-gateway.py \
  --gateway-url https://VPS_IP_OR_HOST \
  --allow-untrusted-tls
```

Repo-side `remote_claim.py` intentionally does not have an "allow untrusted TLS"
flag. Export the gateway certificate to an ignored local path and point Python at
it with `SSL_CERT_FILE`:

```sh
export AGENT_BRIDGE_URL=https://VPS_IP_OR_HOST
export SSL_CERT_FILE=agent-navigation/.local/certs/agent-gateway-selfsigned.crt
python3 agent-navigation/tools/remote_claim.py \
  --profile PROFILE \
  --bridge-url "$AGENT_BRIDGE_URL" \
  --verify
```

Packaged Java clients also need the certificate trusted by the OS/JVM trust
store before remote `/agent` over a self-signed gateway will behave like a normal
HTTPS endpoint. Prefer a real domain certificate before sharing the package with
non-operator users.

For client packaging, set one of:

```sh
CLIENT_AGENT_BRIDGE_URL=https://agents.example.com scripts/package-client.sh
```

or in the ignored real server config:

```json
"agent_bridge_public_url": "https://agents.example.com"
```

Do not commit private hosts, account passwords, bridge tokens, API keys, or
deployment secrets. Do not open public TCP `43610`; the gateway probe and normal
external deployment live checks should both fail if the raw bridge is reachable.
