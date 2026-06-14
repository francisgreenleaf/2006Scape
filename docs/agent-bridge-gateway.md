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
