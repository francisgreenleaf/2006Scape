#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/launcher-common.sh"

ROOT_DIR="$(launcher_repo_root)"
MAVEN_BIN="$(launcher_maven)"
ACCOUNT_TMP_DIR=""
TMP_DIR=""

cleanup() {
    rm -rf "$ACCOUNT_TMP_DIR" "$TMP_DIR"
}
trap cleanup EXIT

cd "$ROOT_DIR"

assert_archive_launcher_executable() {
    python3 - "$1" "$2" <<'PY'
import sys
import zipfile

archive_path = sys.argv[1]
entry = sys.argv[2]
with zipfile.ZipFile(archive_path, "r") as archive:
    mode = (archive.getinfo(entry).external_attr >> 16) & 0o777
if not mode & 0o111:
    raise SystemExit("{} is not executable in archive; mode={:03o}".format(entry, mode))
PY
}

assert_windows_launcher_crlf() {
    python3 - "$1" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = path.read_bytes()
if b"\r\n" not in data or b"\n" in data.replace(b"\r\n", b""):
    raise SystemExit("{} does not use CRLF line endings".format(path))
PY
}

assert_repo_visible_sample_config() {
    local path="$1"
    if [[ ! -f "$path" ]]; then
        echo "tracked sample config is missing: $path" >&2
        exit 1
    fi
    if git check-ignore -q -- "$path"; then
        echo "sample config is still ignored by git and will not be tracked: $path" >&2
        exit 1
    fi
}

echo "Checking whitespace in changed files..."
git diff --check

echo "Preflighting tracked external-player configs..."
assert_repo_visible_sample_config "2006Scape Server/ServerConfig.External.Sample.json"
assert_repo_visible_sample_config "2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json"
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.External.Sample.json"
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json" | grep -q "ok: external-player config passed preflight"

echo "Checking local Docker Compose server ports stay loopback-only..."
if grep -q '^version:' docker-compose.yml; then
    echo "docker-compose.yml should not use the obsolete top-level version key." >&2
    exit 1
fi
grep -q "127.0.0.1:43594:43594" docker-compose.yml
grep -q "127.0.0.1:43595:43595" docker-compose.yml
grep -q "127.0.0.1:8080:8080" docker-compose.yml

echo "Running focused server tests for network/auth/chat/Discord..."
"$MAVEN_BIN" -q -pl "2006Scape Server" clean \
    -Dtest=AccountAuthServiceTest,LoginSessionPasswordHandlingTest,CommandsPasswordPolicyTest,AgentChatServiceTest,AgentActionServiceTest,AgentBridgeServerTest,AgentToolServiceTest,AgentSessionManagerTest,ConfigLoaderNetworkTest,ConfigLoaderSecretsTest,FileServerNetworkConfigTest,DiscordAgentTransportTest \
    test

echo "Running focused client config tests..."
"$MAVEN_BIN" -q -pl "2006Scape Client" -Dtest=MainClientConfigTest test

echo "Checking Python helper syntax..."
python3 -m py_compile scripts/account-admin.py scripts/backup-runtime-data.py scripts/check-deployment-proof-manifest.py scripts/create-account.py scripts/deployment-readiness-report.py scripts/deployment-readiness-status.py scripts/package-deployment-proof.py scripts/prepare-external-deployment.py scripts/preflight-external-config.py scripts/probe-agent-bridge-gateway.py scripts/probe-concurrent-logins.py scripts/probe-deployment-network.py scripts/probe-game-login.py scripts/probe-discord-agent-bots.py scripts/render-agent-bridge-gateway-config.py scripts/render-client-tls-tunnel-config.py scripts/render-server-deployment-files.py scripts/verify-agent-chat-log.py scripts/verify-discord-channel-message.py scripts/verify-external-deployment.py scripts/write-desktop-client-proof.py scripts/smoke-network-auth-chat-runtime.py scripts/lib/deployment_proof_manifest.py scripts/lib/game_login_probe.py scripts/lib/discord_bot_probe.py agent-navigation/tools/agent_chat_XS.py agent-navigation/tools/remote_claim.py agent-navigation/tools/rs-tool_XS.py

echo "Checking remote agent bridge claim and gateway helpers..."
python3 - <<'PY'
import importlib.util
import json
import shutil
import socket
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

remote_claim = load("remote_claim", "agent-navigation/tools/remote_claim.py")
gateway = load("probe_agent_bridge_gateway", "scripts/probe-agent-bridge-gateway.py")
renderer = load("render_agent_bridge_gateway_config", "scripts/render-agent-bridge-gateway-config.py")

assert remote_claim.normalize_bridge_url("https://agent.example.net/") == "https://agent.example.net"
assert remote_claim.normalize_bridge_url("http://127.0.0.1:9999") == "http://127.0.0.1:9999"
for bad in ("http://agent.example.net", "ftp://agent.example.net", "https://u:p@agent.example.net", "https://agent.example.net?token=x"):
    try:
        remote_claim.normalize_bridge_url(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("accepted unsafe bridge URL {}".format(bad))

rendered = renderer.render_nginx(type("Args", (), {
    "server_name": "agents.example.net",
    "cert_path": "/etc/letsencrypt/live/agents.example.net/fullchain.pem",
    "key_path": "/etc/letsencrypt/live/agents.example.net/privkey.pem",
    "access_log": "/var/log/nginx/access.log",
    "error_log": "/var/log/nginx/error.log",
    "upstream": "http://127.0.0.1:43610",
    "body_size": "64k",
    "claim_rate": "10r/m",
    "api_rate": "60r/m",
    "tool_rate": "120r/m",
    "burst": 20,
})())
for expected in (
    "client_max_body_size 64k;",
    "X-Forwarded-For",
    "location = /agent/tool",
    "location ^~ /agent/",
    "proxy_pass http://127.0.0.1:43610/agent/session/claim;",
):
    assert expected in rendered, expected

claim_nonce = "TEST-CLAIM"
observed_tools = []

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _json(self, status, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/agent/health":
            self._json(200, {"ok": True, "service": "2006scape-agent"})
        elif self.path.startswith("/agent/"):
            self._json(404, {"success": False, "message": "not found"})
        else:
            self._json(404, {})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or "0")
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if self.path == "/agent/session/claim" and payload.get("nonce") == claim_nonce:
            self._json(200, {
                "success": True,
                "token": "token-for-test",
                "sessionId": "session-for-test",
                "playerId": 7,
                "playerName": "MrRemote",
            })
        elif self.path == "/agent/session/claim":
            self._json(404, {"success": False, "message": "No pending agent bridge claim was found."})
        elif self.path == "/agent/tool" and self.headers.get("X-Agent-Token") == "token-for-test":
            observed_tools.append(payload.get("tool"))
            self._json(200, {"success": True, "player": {"name": "MrRemote", "x": 1, "y": 2, "height": 0}})
        else:
            self._json(401, {"success": False, "message": "invalid"})

server = HTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever)
thread.daemon = True
thread.start()
base = "http://127.0.0.1:{}".format(server.server_port)
tmp = Path(tempfile.mkdtemp(prefix="remote-claim-test-"))
try:
    session_file = tmp / "rsbridge-session-mrremote.json"
    rc = remote_claim.main([
        "--profile", "MrRemote",
        "--bridge-url", base,
        "--nonce", claim_nonce,
        "--session-file", str(session_file),
        "--allow-http-for-test",
        "--verify",
        "--json",
    ])
    assert rc == 0
    session = json.loads(session_file.read_text(encoding="utf-8"))
    assert session["bridgeUrl"] == base, session
    assert session["playerName"] == "MrRemote", session
    assert session["token"] == "token-for-test", session
    assert observed_tools == ["observe_state_XXS"], observed_tools

    free = socket.socket()
    free.bind(("127.0.0.1", 0))
    raw_port = free.getsockname()[1]
    free.close()
    result = gateway.probe_gateway(
        base,
        raw_host="127.0.0.1",
        raw_port=raw_port,
        timeout=1.0,
        allow_http_for_test=True,
    )
    assert result["success"] is True, result
    assert result["checks"][-1] == "raw bridge TCP not reachable 127.0.0.1:{}".format(raw_port), result
finally:
    server.shutdown()
    thread.join(timeout=3)
    shutil.rmtree(str(tmp))
PY

echo "Checking client_tls_tunnel live verification requires TLS..."
python3 - <<'PY'
import importlib.util
import ssl
from pathlib import Path

path = Path("scripts/verify-external-deployment.py")
spec = importlib.util.spec_from_file_location("verify_external_deployment", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if hasattr(ssl, "TLSVersion") and hasattr(module.create_tls_client_context(False), "minimum_version"):
    assert module.create_tls_client_context(False).minimum_version == ssl.TLSVersion.TLSv1_2
    assert module.create_tls_client_context(True).minimum_version == ssl.TLSVersion.TLSv1_2

tls_config = {
    "external_transport_mode": "client_tls_tunnel",
    "public_game_host": "tls.example.net",
    "game_port": 43594,
    "http_port": 8080,
    "jaggrab_port": 43595,
    "file_server": True,
}
warnings = []
tls_calls = []
old_tls_connect_error = module.tls_connect_error
old_can_connect = module.can_connect
old_probe_login = module.probe_login
old_login_socket = module.login_socket

def fake_tls_connect_error(host, port, timeout, server_hostname, allow_untrusted):
    tls_calls.append((host, port, server_hostname, allow_untrusted))
    return ""

def fake_can_connect(host, port, timeout):
    return False

module.tls_connect_error = fake_tls_connect_error
module.can_connect = fake_can_connect
try:
    checked = module.verify_live_ports(
        tls_config,
        1.0,
        warnings,
        allow_untrusted_client_tls=True,
        tls_sni_host="play.example.net",
    )
    assert [call[1] for call in tls_calls] == [43594, 8080, 43595], tls_calls
    assert all(call[2] == "play.example.net" for call in tls_calls), tls_calls
    assert all(call[3] is True for call in tls_calls), tls_calls
    assert checked[:3] == [
        "game TLS handshake tls.example.net:43594 sni=play.example.net",
        "http cache TLS handshake tls.example.net:8080 sni=play.example.net",
        "jaggrab cache TLS handshake tls.example.net:43595 sni=play.example.net",
    ], checked
    assert checked[-1] == "agent bridge TCP not reachable tls.example.net:43610", checked
    assert any("allowed untrusted certificates" in warning for warning in warnings), warnings

    module.tls_connect_error = lambda *args, **kwargs: "plain TCP endpoint"
    try:
        module.verify_live_ports(tls_config, 1.0, [], allow_untrusted_client_tls=False)
    except SystemExit as exc:
        assert "could not complete TLS handshake" in str(exc), exc
    else:
        raise AssertionError("client_tls_tunnel live verification accepted a non-TLS endpoint")

    tcp_config = dict(tls_config)
    tcp_config["external_transport_mode"] = "tailscale"
    tcp_calls = []
    module.tls_connect_error = fake_tls_connect_error
    module.can_connect = lambda host, port, timeout: tcp_calls.append(port) or port != module.AGENT_BRIDGE_PORT
    tls_calls[:] = []
    checked = module.verify_live_ports(tcp_config, 1.0, [])
    assert tls_calls == [], tls_calls
    assert tcp_calls == [43594, 8080, 43595, module.AGENT_BRIDGE_PORT], tcp_calls
    assert checked == [
        "game TCP connect tls.example.net:43594",
        "http cache TCP connect tls.example.net:8080",
        "jaggrab cache TCP connect tls.example.net:43595",
        "agent bridge TCP not reachable tls.example.net:43610",
    ], checked

    custom_bridge_config = dict(tcp_config)
    custom_bridge_config["agent_bridge_port"] = 44610
    tcp_calls[:] = []
    module.can_connect = lambda host, port, timeout: tcp_calls.append(port) or port != 44610
    checked = module.verify_live_ports(custom_bridge_config, 1.0, [])
    assert tcp_calls == [43594, 8080, 43595, 44610], tcp_calls
    assert checked[-1] == "agent bridge TCP not reachable tls.example.net:44610", checked

    tcp_calls[:] = []
    module.can_connect = lambda host, port, timeout: tcp_calls.append(port) or True
    try:
        module.verify_live_ports(custom_bridge_config, 1.0, [])
    except SystemExit as exc:
        assert "do not expose it externally" in str(exc), exc
    else:
        raise AssertionError("live verification accepted a reachable agent bridge")

    assert module.validate_live_local_host("127.0.0.1") == "127.0.0.1"
    assert module.validate_live_local_host("127.99.1.2") == "127.99.1.2"
    assert module.validate_live_local_host("::1") == "::1"
    assert module.validate_live_local_host("localhost") == "localhost"
    for bad_host in ("10.0.0.5", "192.168.1.10", "0.0.0.0", "example.com", "127.0.0.1\nx", " 127.0.0.1"):
        try:
            module.validate_live_local_host(bad_host)
        except SystemExit as exc:
            assert "--live-local-host" in str(exc), exc
        else:
            raise AssertionError("validate_live_local_host accepted {}".format(bad_host))

    login_calls = []
    def fake_probe_login(host, port, username, password, timeout, use_tls, tls_sni_host,
            allow_untrusted_tls, hold_seconds):
        login_calls.append((host, port, username, password, use_tls, tls_sni_host,
            allow_untrusted_tls, hold_seconds))
        return {"status": 2, "statusName": "ok"}

    module.probe_login = fake_probe_login
    checked_login = module.verify_live_login(
        tcp_config,
        "smoketest",
        "secret",
        1.0,
        hold_seconds=0.25,
    )
    assert checked_login == "game login accepted smoketest at tls.example.net:43594 tls=no", checked_login
    assert login_calls[-1] == ("tls.example.net", 43594, "smoketest", "secret", False, "", False, 0.25), login_calls

    checked_login = module.verify_live_login(
        tls_config,
        "smoketls",
        "secret",
        1.0,
        allow_untrusted_client_tls=True,
        tls_sni_host="play.example.net",
    )
    assert checked_login == "game login accepted smoketls at tls.example.net:43594 tls=yes", checked_login
    assert login_calls[-1] == ("tls.example.net", 43594, "smoketls", "secret", True, "play.example.net", True, 0.0), login_calls

    module.probe_login = lambda *args, **kwargs: {"status": 3, "statusName": "invalid_credentials"}
    try:
        module.verify_live_login(tcp_config, "badlogin", "wrong", 1.0)
    except SystemExit as exc:
        assert "live login probe rejected" in str(exc), exc
    else:
        raise AssertionError("live login verification accepted invalid credentials")
    checked_reject = module.verify_live_rejected_login(
        tcp_config,
        "badlogin",
        "wrong",
        1.0,
        expected_statuses="3",
    )
    assert checked_reject == (
        "game login rejected badlogin at tls.example.net:43594 tls=no "
        "status=3 (invalid_credentials) expected=3"
    ), checked_reject
    try:
        module.verify_live_rejected_login(tcp_config, "badlogin", "wrong", 1.0, expected_statuses="4")
    except SystemExit as exc:
        assert "expected one of 4" in str(exc), exc
    else:
        raise AssertionError("rejected login verification ignored expected status mismatch")
    module.probe_login = lambda *args, **kwargs: {"status": 2, "statusName": "ok"}
    try:
        module.verify_live_rejected_login(tcp_config, "accepted", "secret", 1.0)
    except SystemExit as exc:
        assert "auth did not fail closed" in str(exc), exc
    else:
        raise AssertionError("rejected login verification accepted a successful login")

    class FakeSocket:
        def __init__(self, label):
            self.label = label
            self.closed = False

        def close(self):
            self.closed = True

    socket_calls = []
    sockets = []

    def fake_login_socket(host, port, username, password, timeout=4.0, use_tls=False,
            tls_sni_host="", allow_untrusted_tls=False):
        socket_calls.append((host, port, username, password, timeout, use_tls,
            tls_sni_host, allow_untrusted_tls))
        status = 5 if username == "badlocal" else 2
        status_name = "account_online" if status == 5 else "ok"
        sock = FakeSocket(username)
        if status == 2:
            sockets.append(sock)
            return sock, {"status": status, "statusName": status_name}
        return None, {"status": status, "statusName": status_name}

    module.login_socket = fake_login_socket
    checked_concurrent = module.verify_live_concurrent_logins(
        tls_config,
        "externalone",
        "secret-a",
        "localone",
        "secret-b",
        1.0,
        allow_untrusted_client_tls=True,
        tls_sni_host="play.example.net",
        local_port=43595,
    )
    assert checked_concurrent == (
        "concurrent game logins accepted external externalone at tls.example.net:43594 tls=yes "
        "and local localone at 127.0.0.1:43595 tls=no"
    ), checked_concurrent
    assert socket_calls[-2] == (
        "tls.example.net", 43594, "externalone", "secret-a", 1.0, True,
        "play.example.net", True,
    ), socket_calls
    assert socket_calls[-1] == (
        "127.0.0.1", 43595, "localone", "secret-b", 1.0, False, "", False,
    ), socket_calls
    assert all(sock.closed for sock in sockets[-2:]), [sock.closed for sock in sockets]

    sockets[:] = []
    socket_calls[:] = []
    try:
        module.verify_live_concurrent_logins(
            tcp_config,
            "externalbadhost",
            "secret-a",
            "localbadhost",
            "secret-b",
            1.0,
            local_host="10.0.0.5",
        )
    except SystemExit as exc:
        assert "--live-local-host must be localhost or a loopback IP address" in str(exc), exc
    else:
        raise AssertionError("concurrent live login verification accepted a non-loopback local host")
    assert socket_calls == [], socket_calls

    sockets[:] = []
    socket_calls[:] = []
    try:
        module.verify_live_concurrent_logins(
            tcp_config,
            "externalbadcase",
            "secret-a",
            "badlocal",
            "secret-b",
            1.0,
        )
    except SystemExit as exc:
        assert "local live login probe rejected badlocal" in str(exc), exc
    else:
        raise AssertionError("concurrent live login verification accepted a failed local login")
    assert socket_calls[-2][5] is False and socket_calls[-1][5] is False, socket_calls
    assert sockets and sockets[0].closed, [sock.closed for sock in sockets]
finally:
    module.tls_connect_error = old_tls_connect_error
    module.can_connect = old_can_connect
    module.probe_login = old_probe_login
    module.login_socket = old_login_socket
PY

echo "Checking focused game login probe rejection status handling..."
python3 - <<'PY'
import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path

path = Path("scripts/probe-game-login.py")
spec = importlib.util.spec_from_file_location("probe_game_login", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

old_argv = sys.argv[:]
old_probe_login = module.probe_login
old_password_from_args = module.password_from_args

def run_probe(argv, status, status_name):
    module.probe_login = lambda *args, **kwargs: {
        "host": "example.test",
        "port": 43594,
        "status": status,
        "statusName": status_name,
        "tls": False,
        "username": "probeuser",
    }
    module.password_from_args = lambda args: "redacted"
    sys.argv = ["probe-game-login.py"] + argv
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = module.main()
    return code, output.getvalue()

try:
    code, output = run_probe([
        "--host", "example.test",
        "--username", "probeuser",
        "--expect-failure",
        "--expect-statuses", "3,4",
        "--json",
    ], 3, "invalid_credentials")
    assert code == 0, code
    parsed = json.loads(output)
    assert parsed["status"] == 3, parsed

    code, output = run_probe([
        "--host", "example.test",
        "--username", "probeuser",
        "--expect-failure",
        "--expect-statuses", "3,4",
    ], 4, "account_disabled_or_invalid")
    assert code == 0, code
    assert "expected=3,4" in output, output

    try:
        run_probe([
            "--host", "example.test",
            "--username", "probeuser",
            "--expect-failure",
            "--expect-statuses", "4",
        ], 3, "invalid_credentials")
    except SystemExit as exc:
        assert "expected one of 4" in str(exc), exc
    else:
        raise AssertionError("probe-game-login accepted an unexpected rejection status")

    try:
        run_probe([
            "--host", "example.test",
            "--username", "probeuser",
            "--expect-statuses", "3",
        ], 3, "invalid_credentials")
    except SystemExit as exc:
        assert "--expect-statuses requires --expect-failure" in str(exc), exc
    else:
        raise AssertionError("probe-game-login accepted --expect-statuses without --expect-failure")

    try:
        run_probe([
            "--host", "example.test",
            "--username", "probeuser",
            "--expect-failure",
            "--expect-statuses", "3",
        ], 2, "ok")
    except SystemExit as exc:
        assert "login unexpectedly succeeded" in str(exc), exc
    else:
        raise AssertionError("probe-game-login accepted a successful login as rejection proof")
finally:
    sys.argv = old_argv
    module.probe_login = old_probe_login
    module.password_from_args = old_password_from_args
PY

echo "Checking focused concurrent login probe handling..."
python3 - <<'PY'
import contextlib
import importlib.util
import io
import json
import os
import sys
from pathlib import Path

path = Path("scripts/probe-concurrent-logins.py")
spec = importlib.util.spec_from_file_location("probe_concurrent_logins", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class FakeSocket:
    def __init__(self, label):
        self.label = label
        self.closed = False

    def close(self):
        self.closed = True

old_argv = sys.argv[:]
old_login_socket = module.login_socket
old_environ = dict(os.environ)

socket_calls = []
sockets = []

def fake_login_socket(host, port, username, password, timeout=4.0, use_tls=False,
        tls_sni_host="", allow_untrusted_tls=False):
    socket_calls.append((host, port, username, password, timeout, use_tls, tls_sni_host, allow_untrusted_tls))
    status = 5 if username == "badlocal" else 2
    status_name = "account_online" if status == 5 else "ok"
    if status != 2:
        return None, {
            "username": username,
            "host": host,
            "port": port,
            "status": status,
            "statusName": status_name,
            "tls": use_tls,
        }
    sock = FakeSocket(username)
    sockets.append(sock)
    return sock, {
        "username": username,
        "host": host,
        "port": port,
        "status": status,
        "statusName": status_name,
        "tls": use_tls,
        "rights": 0,
        "flagged": False,
    }

try:
    module.login_socket = fake_login_socket
    result = module.probe_concurrent_logins(
        "tls.example.net",
        43594,
        "externalone",
        "secret-a",
        "127.0.0.1",
        43595,
        "localone",
        "secret-b",
        timeout=1.0,
        external_tls=True,
        tls_sni_host="play.example.net",
        allow_untrusted_tls=True,
    )
    assert result["success"] is True, result
    assert result["summary"] == (
        "concurrent game logins accepted external externalone at tls.example.net:43594 tls=yes "
        "and local localone at 127.0.0.1:43595 tls=no"
    ), result
    assert socket_calls[-2] == ("tls.example.net", 43594, "externalone", "secret-a", 1.0, True, "play.example.net", True), socket_calls
    assert socket_calls[-1] == ("127.0.0.1", 43595, "localone", "secret-b", 1.0, False, "", False), socket_calls
    assert all(sock.closed for sock in sockets[-2:]), [sock.closed for sock in sockets]

    socket_calls[:] = []
    try:
        module.probe_concurrent_logins(
            "example.test",
            43594,
            "externalbadhost",
            "secret-a",
            "10.0.0.5",
            43594,
            "localbadhost",
            "secret-b",
        )
    except SystemExit as exc:
        assert "--local-host must be localhost or a loopback IP address" in str(exc), exc
    else:
        raise AssertionError("probe-concurrent-logins accepted a non-loopback local host")
    assert socket_calls == [], socket_calls

    sockets[:] = []
    socket_calls[:] = []
    try:
        module.probe_concurrent_logins(
            "example.test",
            43594,
            "externalcase",
            "secret-a",
            "127.0.0.1",
            43594,
            "badlocal",
            "secret-b",
        )
    except SystemExit as exc:
        assert "local login rejected badlocal" in str(exc), exc
    else:
        raise AssertionError("probe-concurrent-logins accepted a failed local login")
    assert socket_calls[-2][2] == "externalcase" and socket_calls[-1][2] == "badlocal", socket_calls
    assert sockets and sockets[0].closed, [sock.closed for sock in sockets]

    os.environ["EXTERNAL_PASSWORD"] = "secret-a"
    os.environ["LOCAL_PASSWORD"] = "secret-b"
    sys.argv = [
        "probe-concurrent-logins.py",
        "--external-host", "example.test",
        "--external-username", "externaljson",
        "--external-password-env", "EXTERNAL_PASSWORD",
        "--local-username", "localjson",
        "--local-password-env", "LOCAL_PASSWORD",
        "--json",
    ]
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = module.main()
    assert code == 0, code
    parsed = json.loads(output.getvalue())
    assert parsed["success"] is True, parsed
    assert "secret" not in output.getvalue(), output.getvalue()
finally:
    sys.argv = old_argv
    module.login_socket = old_login_socket
    os.environ.clear()
    os.environ.update(old_environ)
PY

echo "Checking focused deployment network probe handling..."
python3 - <<'PY'
import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path

path = Path("scripts/probe-deployment-network.py")
spec = importlib.util.spec_from_file_location("probe_deployment_network", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

old_argv = sys.argv[:]
old_load_json = module.verifier.load_json
old_validate_tls_sni_host = module.verifier.validate_tls_sni_host
old_run_preflight = module.verifier.run_preflight
old_verify_network_placeholders = module.verifier.verify_network_placeholders
old_verify_live_ports = module.verifier.verify_live_ports

calls = []

def fake_load_json(config_path):
    calls.append(("load_json", str(config_path)))
    return {
        "external_players_enabled": True,
        "public_game_host": "play.example.net",
        "external_transport_mode": "client_tls_tunnel",
    }

def fake_validate_tls_sni_host(tls_sni_host, allow_placeholder_network_config):
    calls.append(("validate_tls_sni_host", tls_sni_host, allow_placeholder_network_config))
    return tls_sni_host or "play.example.net"

def fake_run_preflight(config_path, allow_wildcard_bind):
    calls.append(("run_preflight", str(config_path), allow_wildcard_bind))

def fake_verify_network_placeholders(config, allow_placeholder_network_config):
    calls.append(("verify_network_placeholders", config["public_game_host"], allow_placeholder_network_config))

def fake_verify_live_ports(config, timeout, warnings, allow_untrusted_client_tls=False, tls_sni_host=""):
    calls.append((
        "verify_live_ports",
        config["public_game_host"],
        timeout,
        allow_untrusted_client_tls,
        tls_sni_host,
    ))
    warnings.append("sample live network warning")
    return [
        "game endpoint play.example.net:43594 reachable via TLS",
        "agent bridge 43610 not reachable externally",
    ]

try:
    module.verifier.load_json = fake_load_json
    module.verifier.validate_tls_sni_host = fake_validate_tls_sni_host
    module.verifier.run_preflight = fake_run_preflight
    module.verifier.verify_network_placeholders = fake_verify_network_placeholders
    module.verifier.verify_live_ports = fake_verify_live_ports

    result = module.probe_network(
        "ServerConfig.json",
        timeout=1.5,
        allow_wildcard_bind=True,
        allow_placeholder_network_config=True,
        allow_untrusted_client_tls=True,
        tls_sni_host="cert.example.net",
    )
    assert result["success"] is True, result
    assert result["warnings"] == ["sample live network warning"], result
    assert result["checks"][-1] == "agent bridge 43610 not reachable externally", result
    assert calls == [
        ("load_json", "ServerConfig.json"),
        ("validate_tls_sni_host", "cert.example.net", True),
        ("run_preflight", "ServerConfig.json", True),
        ("verify_network_placeholders", "play.example.net", True),
        ("verify_live_ports", "play.example.net", 1.5, True, "cert.example.net"),
    ], calls

    calls[:] = []
    sys.argv = [
        "probe-deployment-network.py",
        "--config", "ServerConfig.json",
        "--timeout", "2.5",
        "--tls-sni-host", "cert.example.net",
        "--allow-untrusted-client-tls",
        "--json",
    ]
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = module.main()
    assert code == 0, code
    parsed = json.loads(output.getvalue())
    assert parsed["success"] is True, parsed
    assert parsed["checks"][0].startswith("game endpoint"), parsed
    assert "live-check:" not in output.getvalue(), output.getvalue()
    assert calls[-1] == ("verify_live_ports", "play.example.net", 2.5, True, "cert.example.net"), calls

    sys.argv = [
        "probe-deployment-network.py",
        "--config", "ServerConfig.json",
    ]
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = module.main()
    assert code == 0, code
    text = output.getvalue()
    assert "warning: sample live network warning" in text, text
    assert "live-check: agent bridge 43610 not reachable externally" in text, text
    assert "ok: deployment network probe passed" in text, text

    sys.argv = ["probe-deployment-network.py", "--timeout", "0"]
    try:
        module.main()
    except SystemExit as exc:
        assert "--timeout must be positive" in str(exc), exc
    else:
        raise AssertionError("probe-deployment-network accepted a nonpositive timeout")

    def fake_load_json_disabled(config_path):
        return {"external_players_enabled": False}

    module.verifier.load_json = fake_load_json_disabled
    try:
        module.probe_network("ServerConfig.json")
    except SystemExit as exc:
        assert "external_players_enabled is false" in str(exc), exc
    else:
        raise AssertionError("probe-deployment-network accepted a config with external_players_enabled=false")
finally:
    sys.argv = old_argv
    module.verifier.load_json = old_load_json
    module.verifier.validate_tls_sni_host = old_validate_tls_sni_host
    module.verifier.run_preflight = old_run_preflight
    module.verifier.verify_network_placeholders = old_verify_network_placeholders
    module.verifier.verify_live_ports = old_verify_live_ports
PY

echo "Checking script registry metadata..."
python3 -m json.tool agent-navigation/data/script_registry.json > /dev/null
python3 agent-navigation/tools/script_registry.py search "agent chat" --json | grep -q '"id": "agent_chat_xs"'
python3 agent-navigation/tools/script_registry.py show agent_chat_xs --json | grep -q '"path": "agent-navigation/tools/agent_chat_XS.py"'
python3 agent-navigation/tools/script_registry.py search "runtime backup" --json | grep -q '"id": "runtime_data_backup"'
python3 agent-navigation/tools/script_registry.py show runtime_data_backup --json | grep -q '"path": "scripts/backup-runtime-data.py"'
python3 agent-navigation/tools/script_registry.py show runtime_data_backup --json | grep -q -- "--proof-manifest"
python3 agent-navigation/tools/script_registry.py search "desktop proof" --json | grep -q '"id": "desktop_client_proof"'
python3 agent-navigation/tools/script_registry.py show desktop_client_proof --json | grep -q '"path": "scripts/write-desktop-client-proof.py"'
python3 agent-navigation/tools/script_registry.py show desktop_client_proof --json | grep -q -- "--proof-manifest"
python3 agent-navigation/tools/script_registry.py search "deployment" --json | grep -q '"id": "external_deployment_prepare"'
python3 agent-navigation/tools/script_registry.py search "deployment" --json | grep -q '"id": "external_deployment_verify"'
python3 agent-navigation/tools/script_registry.py search "proof manifest" --json | grep -q '"id": "deployment_proof_manifest_check"'
python3 agent-navigation/tools/script_registry.py search "proof bundle" --json | grep -q '"id": "deployment_proof_bundle"'
python3 agent-navigation/tools/script_registry.py search "readiness status" --json | grep -q '"id": "deployment_readiness_status"'
python3 agent-navigation/tools/script_registry.py search "client package" --json | grep -q '"id": "standalone_client_package"'
python3 agent-navigation/tools/script_registry.py search "tls tunnel" --json | grep -q '"id": "client_tls_tunnel_config"'
python3 agent-navigation/tools/script_registry.py search "server deployment templates" --json | grep -q '"id": "server_deployment_files"'
python3 agent-navigation/tools/script_registry.py search "account audit" --json | grep -q '"id": "external_account_admin"'
python3 agent-navigation/tools/script_registry.py search "login proof" --json | grep -q '"id": "game_login_probe"'
python3 agent-navigation/tools/script_registry.py search "network proof" --json | grep -q '"id": "deployment_network_probe"'
python3 agent-navigation/tools/script_registry.py search "concurrent login proof" --json | grep -q '"id": "concurrent_login_probe"'
python3 agent-navigation/tools/script_registry.py search "discord ingestion proof" --json | grep -q '"id": "agent_chat_log_verify"'
python3 agent-navigation/tools/script_registry.py search "server to discord proof" --json | grep -q '"id": "discord_channel_message_verify"'
python3 agent-navigation/tools/script_registry.py search "discord proof" --json | grep -q '"id": "discord_agent_probe"'
python3 agent-navigation/tools/script_registry.py show external_config_preflight --json | grep -q '"path": "scripts/preflight-external-config.py"'
python3 agent-navigation/tools/script_registry.py show external_deployment_prepare --json | grep -q '"path": "scripts/prepare-external-deployment.py"'
python3 agent-navigation/tools/script_registry.py show standalone_client_package --json | grep -q '"path": "scripts/package-client.sh"'
python3 agent-navigation/tools/script_registry.py show client_tls_tunnel_config --json | grep -q '"path": "scripts/render-client-tls-tunnel-config.py"'
python3 agent-navigation/tools/script_registry.py show server_deployment_files --json | grep -q '"path": "scripts/render-server-deployment-files.py"'
python3 agent-navigation/tools/script_registry.py show external_deployment_verify --json | grep -q '"path": "scripts/verify-external-deployment.py"'
python3 agent-navigation/tools/script_registry.py show deployment_readiness_report --json | grep -q '"path": "scripts/deployment-readiness-report.py"'
python3 agent-navigation/tools/script_registry.py show deployment_readiness_report --json | grep -q -- "--update-proof-manifest"
python3 agent-navigation/tools/script_registry.py show deployment_readiness_status --json | grep -q '"path": "scripts/deployment-readiness-status.py"'
python3 agent-navigation/tools/script_registry.py show deployment_proof_manifest_check --json | grep -q '"path": "scripts/check-deployment-proof-manifest.py"'
python3 agent-navigation/tools/script_registry.py show deployment_proof_bundle --json | grep -q '"path": "scripts/package-deployment-proof.py"'
python3 agent-navigation/tools/script_registry.py show deployment_proof_bundle --json | grep -q -- "--require-full-proof"
python3 agent-navigation/tools/script_registry.py show external_account_create --json | grep -q '"path": "scripts/create-account.py"'
python3 agent-navigation/tools/script_registry.py show external_account_create --json | grep -q -- "read -s ACCOUNT_PASSWORD"
python3 agent-navigation/tools/script_registry.py show external_account_create --json | grep -q -- "--password-env ACCOUNT_PASSWORD"
python3 agent-navigation/tools/script_registry.py show external_account_create --json | grep -q -- "--overwrite --preserve-metadata"
python3 agent-navigation/tools/script_registry.py show external_account_admin --json | grep -q '"path": "scripts/account-admin.py"'
python3 agent-navigation/tools/script_registry.py show external_account_admin --json | grep -q -- "--require-password-policy audit"
python3 agent-navigation/tools/script_registry.py show game_login_probe --json | grep -q '"path": "scripts/probe-game-login.py"'
python3 agent-navigation/tools/script_registry.py show deployment_network_probe --json | grep -q '"path": "scripts/probe-deployment-network.py"'
python3 agent-navigation/tools/script_registry.py show concurrent_login_probe --json | grep -q '"path": "scripts/probe-concurrent-logins.py"'
python3 agent-navigation/tools/script_registry.py show agent_chat_log_verify --json | grep -q '"path": "scripts/verify-agent-chat-log.py"'
python3 agent-navigation/tools/script_registry.py show agent_chat_log_verify --json | grep -q -- "--proof-manifest"
python3 agent-navigation/tools/script_registry.py show discord_channel_message_verify --json | grep -q '"path": "scripts/verify-discord-channel-message.py"'
python3 agent-navigation/tools/script_registry.py show discord_channel_message_verify --json | grep -q -- "--proof-manifest"
python3 agent-navigation/tools/script_registry.py show discord_agent_probe --json | grep -q '"path": "scripts/probe-discord-agent-bots.py"'

echo "Checking external-player documentation coverage..."
grep -q "direct_tcp" README.md
grep -q "direct_tcp" AGENTS.md
grep -q "direct_tcp" docs/external-deployment-quickstart.md
grep -q "direct_tcp" docs/deployment-networking.md
grep -q "direct_tcp" docs/network-auth-agent-chat-design.md
grep -q "direct_tcp" .codex/skills/2006scape/SKILL.md
grep -q "direct_tcp" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "direct_tcp" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "ServerConfig.ClientTlsTunnel.Sample.json" README.md
grep -q "ServerConfig.ClientTlsTunnel.Sample.json" AGENTS.md
grep -q "ServerConfig.ClientTlsTunnel.Sample.json" docs/external-deployment-quickstart.md
grep -q "ServerConfig.ClientTlsTunnel.Sample.json" docs/deployment-networking.md
grep -q "ServerConfig.ClientTlsTunnel.Sample.json" docs/network-auth-agent-chat-design.md
grep -q "ServerConfig.ClientTlsTunnel.Sample.json" .codex/skills/2006scape/SKILL.md
grep -q "ServerConfig.ClientTlsTunnel.Sample.json" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q 'Recommended MVP: use `direct_tcp`' docs/network-auth-agent-chat-design.md
grep -q '`direct_tcp` account-auth external defaults' docs/network-auth-agent-chat-design.md
grep -q "direct_tcp_external_transport_confirmed" README.md
grep -q "direct_tcp_external_transport_confirmed" AGENTS.md
grep -q "direct_tcp_external_transport_confirmed" docs/external-deployment-quickstart.md
grep -q "direct_tcp_external_transport_confirmed" docs/deployment-networking.md
grep -q "direct_tcp_external_transport_confirmed" docs/network-auth-agent-chat-design.md
grep -q "plaintext TCP" README.md
grep -q "plaintext TCP" docs/external-deployment-quickstart.md
grep -q "plaintext TCP" docs/deployment-networking.md
grep -q "REPLACE_WITH_PUBLIC_INTERFACE_IP" README.md
grep -q "REPLACE_WITH_PUBLIC_INTERFACE_IP" AGENTS.md
grep -q "REPLACE_WITH_PUBLIC_INTERFACE_IP" docs/external-deployment-quickstart.md
grep -q "REPLACE_WITH_PUBLIC_INTERFACE_IP" docs/deployment-networking.md
grep -q "server.example.com" README.md
grep -q "server.example.com" docs/external-deployment-quickstart.md
grep -q "server.example.com" docs/deployment-networking.md
grep -q "Java client connects directly" docs/deployment-networking.md
grep -q "Standalone Client And Browser Feasibility" docs/deployment-networking.md
grep -q "old browser/applet path is not viable" docs/deployment-networking.md
grep -q "account_auth_legacy_fallback" docs/external-deployment-quickstart.md
grep -q "account_auth_auto_create" docs/external-deployment-quickstart.md
if grep -Eq "legacy_character_auth_enabled|account_auto_create_enabled" docs/external-deployment-quickstart.md docs/network-auth-agent-chat-design.md; then
    echo "external deployment docs still mention stale account-auth config keys." >&2
    exit 1
fi
if grep -Eq "quickest private external-player|first private external-player test|Recommended MVP: Tailscale|Recommended MVP: use a standard TCP security boundary|Secure Transport Strategy|require_secure_external_transport\`: true for external configs|Tailscale/account-auth external defaults|placeholder Tailscale/private|private-interface IP|requires an external secure transport boundary|secure external transport required|external sample binds both .*Tailscale/private|external VPN/tunnel Java client|secure transport path|real VPN/tunnel path" README.md AGENTS.md docs/deployment-networking.md docs/external-deployment-quickstart.md docs/network-auth-agent-chat-design.md .codex/skills/2006scape/SKILL.md .codex/skills/2006scape-agent-bridge-dev/SKILL.md .codex/skills/2006scape-external-deployment/SKILL.md; then
    echo "external deployment docs/skills still contain stale Tailscale-only or secure-transport-only wording." >&2
    exit 1
fi
if grep -Eq "selected secure transport|secure transport, and concurrency" scripts/preflight-external-config.py scripts/prepare-external-deployment.py; then
    echo "external deployment helper text still assumes only secure transports." >&2
    exit 1
fi
grep -q "Never expose:" docs/deployment-networking.md
grep -q "Google Cloud Compute Engine" docs/deployment-networking.md
grep -q "Public VPS With Client TLS Tunnel" docs/deployment-networking.md
grep -q "Cloud Run/serverless" docs/deployment-networking.md
grep -q "two concurrent PBKDF2 protocol logins plus wrong-password, disabled-account, and missing-account rejection" docs/network-auth-agent-chat-design.md
grep -q "missing account record, disabled account" docs/deployment-networking.md
grep -q -- "--live-local-host.*loopback" README.md
grep -q -- "--live-local-host.*loopback" docs/deployment-networking.md
grep -q -- "--live-local-host.*loopback" docs/network-auth-agent-chat-design.md
grep -q -- "--live-local-host.*loopback" AGENTS.md
grep -q -- "--live-login-username" README.md
grep -q -- "--live-local-login-username" README.md
grep -q -- "--live-reject-login-username" README.md
grep -q -- "--live-reject-login-expected-statuses 3,4" README.md
grep -q "final readiness so the accepted rejection codes are pinned" README.md
grep -q -- "--expect-statuses" README.md
grep -q "scripts/probe-deployment-network.py" README.md
grep -q "scripts/probe-concurrent-logins.py" README.md
grep -q -- "--local-host.*loopback" docs/deployment-networking.md
grep -q -- "--live-reject-login-username" docs/deployment-networking.md
grep -q -- "--live-reject-login-expected-statuses 3,4" docs/deployment-networking.md
grep -q "final readiness so the allowed rejection codes are pinned" docs/deployment-networking.md
grep -q "scripts/probe-deployment-network.py" docs/deployment-networking.md
grep -q "scripts/probe-game-login.py" docs/deployment-networking.md
grep -q "scripts/probe-concurrent-logins.py" docs/deployment-networking.md
grep -q "scripts/probe-deployment-network.py" docs/external-deployment-quickstart.md
grep -q "scripts/probe-concurrent-logins.py" docs/external-deployment-quickstart.md
grep -q -- "--live-reject-login-expected-statuses 3,4" docs/external-deployment-quickstart.md
grep -q "scripts/probe-deployment-network.py" docs/network-auth-agent-chat-design.md
grep -q "scripts/probe-concurrent-logins.py" docs/network-auth-agent-chat-design.md
grep -q "scripts/probe-deployment-network.py" AGENTS.md
grep -q "scripts/probe-concurrent-logins.py" AGENTS.md
grep -q -- "--live-reject-login-expected-statuses 3,4" AGENTS.md
grep -q "scripts/probe-deployment-network.py" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "scripts/probe-concurrent-logins.py" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "scripts/probe-deployment-network.py" .codex/skills/2006scape/SKILL.md
grep -q "scripts/probe-concurrent-logins.py" .codex/skills/2006scape/SKILL.md
grep -q -- "--expect-statuses" docs/deployment-networking.md
grep -q -- "--expect-statuses" docs/network-auth-agent-chat-design.md
grep -q -- "--expect-statuses" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q -- "--live-reject-login-expected-statuses 3,4" .codex/skills/2006scape/SKILL.md
grep -q -- "--live-reject-login-expected-statuses 3,4" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q -- "--live-reject-login-expected-statuses 3,4" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q -- "--live-discord" README.md
grep -q "scripts/probe-discord-agent-bots.py" docs/deployment-networking.md
grep -q "scripts/probe-discord-agent-bots.py" docs/network-auth-agent-chat-design.md
grep -q "scripts/verify-agent-chat-log.py" docs/deployment-networking.md
grep -q "scripts/verify-discord-channel-message.py" docs/deployment-networking.md
grep -q "macOS double-click .command wrappers" README.md
grep -q "Run-2006Scape.command" docs/external-deployment-quickstart.md
grep -q "Check-Setup.command" docs/external-deployment-quickstart.md
grep -q "macOS .command wrappers plus" docs/network-auth-agent-chat-design.md
grep -q "macOS double-click wrappers" docs/network-auth-agent-chat-design.md
grep -q "refuses symlinked output directories" README.md
grep -q "refuses symlinked output directories" docs/deployment-networking.md
grep -q "refuses symlinked output directories" docs/network-auth-agent-chat-design.md
grep -q "refuses symlinked output directories" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "refuses symlinked output directories" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "symlinked package output paths are rejected" .codex/skills/2006scape/SKILL.md
python3 agent-navigation/tools/script_registry.py show standalone_client_package --json | grep -q "symlinked output path rejection"
grep -q "macOS double-click \`.command\` wrappers" .codex/skills/2006scape/SKILL.md
grep -q "Run-2006Scape.command" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "Check-Setup.command" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "Run-2006Scape.command" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "macOS double-click .command wrappers" agent-navigation/data/script_registry.json
grep -q "non-symlink screenshot/log evidence file" README.md
grep -q "scripts/write-desktop-client-proof.py" README.md
grep -q "scripts/write-desktop-client-proof.py" AGENTS.md
grep -q "scripts/write-desktop-client-proof.py" docs/deployment-networking.md
grep -q "scripts/write-desktop-client-proof.py" docs/external-deployment-quickstart.md
grep -q "scripts/write-desktop-client-proof.py" docs/network-auth-agent-chat-design.md
grep -q "scripts/write-desktop-client-proof.py" .codex/skills/2006scape/SKILL.md
grep -q "scripts/write-desktop-client-proof.py" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "scripts/write-desktop-client-proof.py" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "missing/symlinked/empty evidence files are rejected" docs/deployment-networking.md
grep -q "non-symlink non-empty screenshot/log file" docs/network-auth-agent-chat-design.md
grep -q "non-symlink screenshot/log evidence file" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q -- "--agent-chat-log-text" docs/network-auth-agent-chat-design.md
grep -q -- "--discord-channel-message-text" docs/network-auth-agent-chat-design.md
grep -q "direct agent/player delivery, real Discord-to-server ingress, or blocked-routing absence proof" docs/network-auth-agent-chat-design.md
grep -q "updates only the \`discord_channel_message_\*\` fields" docs/network-auth-agent-chat-design.md
grep -q "verify-agent-chat-log.py --proof-manifest PATH" docs/network-auth-agent-chat-design.md
grep -q "verify-discord-channel-message.py --proof-manifest PATH" docs/network-auth-agent-chat-design.md
grep -q -- "--desktop-client-proof-file" docs/deployment-networking.md
grep -q -- "--runtime-data-backup-proof-file" docs/deployment-networking.md
grep -q -- "--runtime-data-backup-proof-file" docs/network-auth-agent-chat-design.md
grep -q -- "--proof-manifest" README.md
grep -q -- "--proof-manifest" docs/deployment-networking.md
grep -q -- "--proof-manifest" docs/external-deployment-quickstart.md
grep -q -- "--proof-manifest" docs/network-auth-agent-chat-design.md
grep -q -- "--proof-manifest" .codex/skills/2006scape/SKILL.md
grep -q -- "--proof-manifest" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q -- "--proof-manifest" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q -- "--update-proof-manifest" README.md
grep -q -- "--update-proof-manifest" AGENTS.md
grep -q -- "--update-proof-manifest" docs/deployment-networking.md
grep -q -- "--update-proof-manifest" docs/external-deployment-quickstart.md
grep -q -- "--update-proof-manifest" docs/network-auth-agent-chat-design.md
grep -q -- "--update-proof-manifest" .codex/skills/2006scape/SKILL.md
grep -q -- "--update-proof-manifest" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q -- "--update-proof-manifest" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q -- "--update-proof-manifest" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "scripts/check-deployment-proof-manifest.py" README.md
grep -q "scripts/check-deployment-proof-manifest.py" AGENTS.md
grep -q "scripts/check-deployment-proof-manifest.py" docs/deployment-networking.md
grep -q "scripts/check-deployment-proof-manifest.py" docs/external-deployment-quickstart.md
grep -q "scripts/check-deployment-proof-manifest.py" docs/network-auth-agent-chat-design.md
grep -q "scripts/check-deployment-proof-manifest.py" .codex/skills/2006scape/SKILL.md
grep -q "scripts/check-deployment-proof-manifest.py" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "scripts/check-deployment-proof-manifest.py" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "scripts/package-deployment-proof.py" README.md
grep -q "scripts/package-deployment-proof.py" AGENTS.md
grep -q "scripts/package-deployment-proof.py" docs/deployment-networking.md
grep -q "scripts/package-deployment-proof.py" docs/external-deployment-quickstart.md
grep -q "scripts/package-deployment-proof.py" docs/network-auth-agent-chat-design.md
grep -q "scripts/package-deployment-proof.py" .codex/skills/2006scape/SKILL.md
grep -q "scripts/package-deployment-proof.py" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "final external-ready handoff" README.md
grep -q "final external-ready handoff" AGENTS.md
grep -q "final external-ready handoff" docs/deployment-networking.md
grep -q "final external-ready handoff" docs/external-deployment-quickstart.md
grep -q "final external-ready handoff" docs/network-auth-agent-chat-design.md
grep -q "final external-ready handoff" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "final external-ready bundle" .codex/skills/2006scape/SKILL.md
grep -q -- "--require-full-proof" .codex/skills/2006scape-script-registry/SKILL.md
grep -q -- "--prepared-dir dist/external-deployment" README.md
grep -q -- "--prepared-dir dist/external-deployment" AGENTS.md
grep -q -- "--prepared-dir dist/external-deployment" docs/deployment-networking.md
grep -q -- "--prepared-dir dist/external-deployment" docs/external-deployment-quickstart.md
grep -q -- "--prepared-dir dist/external-deployment" docs/network-auth-agent-chat-design.md
grep -q -- "--prepared-dir dist/external-deployment" .codex/skills/2006scape/SKILL.md
grep -q -- "--prepared-dir dist/external-deployment" .codex/skills/2006scape-script-registry/SKILL.md
grep -q -- "--prepared-dir dist/external-deployment" .codex/skills/2006scape-external-deployment/SKILL.md
python3 agent-navigation/tools/script_registry.py show deployment_proof_bundle --json | grep -q -- "--prepared-dir dist/external-deployment"
grep -q "Final-gate manifests must keep \`require_full_proof:true\`" README.md
grep -q "Final-gate manifests must keep \`require_full_proof:true\`" AGENTS.md
grep -q "Final-gate manifests must keep \`require_full_proof:true\`" docs/deployment-networking.md
grep -q "manifest itself must keep \`require_full_proof:true\`" docs/network-auth-agent-chat-design.md
grep -q "Final-gate manifests must keep \`require_full_proof:true\`" .codex/skills/2006scape/SKILL.md
grep -q "Final-gate manifests must keep \`require_full_proof:true\`" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "manifest itself must keep \`require_full_proof:true\`" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "merged manifest plus CLI values" README.md
grep -q "merged manifest plus CLI values" AGENTS.md
grep -q "merged manifest plus CLI values" docs/deployment-networking.md
grep -q "merged manifest plus CLI values" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "merged manifest plus CLI values" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "merged proof check before packaging" .codex/skills/2006scape/SKILL.md
grep -q "before package/build work begins" docs/network-auth-agent-chat-design.md
grep -q -- "--json-output" README.md
grep -q -- "--json-output" AGENTS.md
grep -q -- "--json-output" docs/deployment-networking.md
grep -q -- "--json-output" docs/external-deployment-quickstart.md
grep -q -- "--json-output" docs/network-auth-agent-chat-design.md
grep -q -- "--json-output" .codex/skills/2006scape/SKILL.md
grep -q -- "--json-output" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q -- "--json-output" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q -- "--json-output" agent-navigation/data/script_registry.json
grep -q "deployment-proof-manifest.json" AGENTS.md
grep -q "deployment-proof-manifest.json" README.md
grep -q "deployment-proof-manifest.json" docs/deployment-networking.md
grep -q "deployment-proof-manifest.json" docs/external-deployment-quickstart.md
grep -q "source_server_config_sha256" README.md
grep -q "source_server_config_sha256" docs/deployment-networking.md
grep -q "source_server_config_sha256" docs/network-auth-agent-chat-design.md
grep -q "source_server_config_sha256" .codex/skills/2006scape/SKILL.md
grep -q "source_server_config_sha256" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "::agentchat @agent:Name message" README.md
grep -q "agent-navigation/tools/agent_chat_XS.py --profile" README.md
grep -q "Use these for coordination, not as a public chat replacement or a hot-loop polling primitive" README.md
grep -q "Target shortcuts are mutually exclusive" README.md
grep -q "Target shortcuts are mutually exclusive" AGENTS.md
grep -q "Target shortcuts are mutually exclusive" agent-navigation/scripting-primitives.md
grep -q "Target shortcuts are mutually exclusive" .codex/skills/2006scape/SKILL.md
grep -q "Target shortcuts are mutually exclusive" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "Target shortcuts are mutually exclusive" docs/network-auth-agent-chat-design.md
grep -q "Target shortcuts are mutually exclusive" "2006Scape Client/src/main/java/CodexAppServerClient.java"
grep -q "scripts/backup-runtime-data.py" README.md
grep -q "scripts/backup-runtime-data.py" AGENTS.md
grep -q "scripts/backup-runtime-data.py" docs/deployment-networking.md
grep -q "scripts/backup-runtime-data.py" docs/network-auth-agent-chat-design.md
grep -q "scripts/backup-runtime-data.py" .codex/skills/2006scape/SKILL.md
grep -q "scripts/backup-runtime-data.py" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "scripts/deployment-readiness-status.py" README.md
grep -q "scripts/deployment-readiness-status.py" AGENTS.md
grep -q "scripts/deployment-readiness-status.py" docs/deployment-networking.md
grep -q "scripts/deployment-readiness-status.py" docs/external-deployment-quickstart.md
grep -q "scripts/deployment-readiness-status.py" docs/network-auth-agent-chat-design.md
grep -q "scripts/deployment-readiness-status.py" .codex/skills/2006scape/SKILL.md
grep -q "scripts/deployment-readiness-status.py" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q -- "--show-next-commands" README.md
grep -q -- "--show-next-commands" AGENTS.md
grep -q -- "--show-next-commands" docs/deployment-networking.md
grep -q -- "--show-next-commands" docs/external-deployment-quickstart.md
grep -q -- "--show-next-commands" docs/network-auth-agent-chat-design.md
grep -q -- "--show-next-commands" .codex/skills/2006scape/SKILL.md
grep -q -- "--show-next-commands" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q -- "--show-next-commands" .codex/skills/2006scape-script-registry/SKILL.md
python3 agent-navigation/tools/script_registry.py show deployment_readiness_status --json | grep -q -- "--show-next-commands"
grep -q -- "--proof-manifest" agent-navigation/data/script_registry.json
grep -q "operator-provided-login guidance" .codex/skills/2006scape/SKILL.md
grep -q "operator-provided username/password guidance" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "operator-provided login guidance" AGENTS.md
grep -q "operator-provided login guidance" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "login guidance to use the server operator's supplied account" README.md
grep -q "login guidance to use the server operator's supplied account" docs/deployment-networking.md
grep -q "login guidance to use the server operator's supplied account" docs/network-auth-agent-chat-design.md
grep -q "macOS/Linux setup checker can start the bundled stunnel config temporarily" README.md
grep -q "macOS/Linux setup checker can start the bundled stunnel config temporarily" AGENTS.md
grep -q "macOS/Linux setup checker can start the bundled stunnel config temporarily" docs/external-deployment-quickstart.md
grep -q "macOS/Linux setup checker starts the bundled stunnel config temporarily" docs/deployment-networking.md
grep -q "macOS/Linux setup checker can start the bundled stunnel config temporarily" docs/network-auth-agent-chat-design.md
grep -q "macOS/Linux setup checker can start stunnel temporarily" .codex/skills/2006scape/SKILL.md
grep -q "macOS/Linux setup checker can start it temporarily" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "macOS/Linux setup checker may also start the bundled stunnel config temporarily" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q 'CLIENT_SECURE_TRANSPORT` must be one of `direct_tcp`, `tailscale`, `wireguard`, `vpn`, or `client_tls_tunnel`' docs/network-auth-agent-chat-design.md
grep -q "not to reuse RuneScape.com or other service passwords" docs/external-deployment-quickstart.md
if grep -q 'CLIENT_SECURE_TRANSPORT` must be `tailscale`, `wireguard`, or `vpn`' docs/network-auth-agent-chat-design.md; then
    echo "network-auth design doc still has stale manual override transport guidance." >&2
    exit 1
fi
grep -q "owner-only archive" README.md
grep -q "owner-only archive/proof files" docs/deployment-networking.md
grep -q "owner-only archive/proof files" docs/network-auth-agent-chat-design.md
grep -q "owner-only archive/proof files" .codex/skills/2006scape/SKILL.md
grep -q "owner-only archive/proof files" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "owner-only archive/proof files" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "rejects symlinked proof notes" README.md
grep -q "rejects symlinked proof notes" docs/deployment-networking.md
grep -q "rejects symlinked proof notes" docs/network-auth-agent-chat-design.md
grep -q "rejects symlinked proof notes" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "backup archive sha256" README.md
grep -q "backup archive sha256" docs/deployment-networking.md
grep -q "backup archive sha256" docs/network-auth-agent-chat-design.md
grep -q "backup archive sha256" .codex/skills/2006scape/SKILL.md
grep -q "backup archive sha256" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "backup archive sha256" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "Back up deployed runtime data" docs/external-deployment-quickstart.md
grep -q "create the manifest parent directory and copy the manifest from the template if it is missing" docs/external-deployment-quickstart.md
grep -q "updates \`runtime_data_backup_proof_file\` automatically" docs/external-deployment-quickstart.md
grep -q "create the proof manifest parent directory" README.md
grep -q "create the proof manifest parent directory" AGENTS.md
grep -q "create the proof manifest parent directory" docs/deployment-networking.md
grep -q "creates the proof manifest parent directory" docs/network-auth-agent-chat-design.md
grep -q "create the proof manifest parent directory" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "live network/login/client/chat/backup/Discord evidence" AGENTS.md
grep -q "live network/login/client/chat/backup/Discord evidence" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "live network/login/client/chat/backup/Discord evidence" docs/deployment-networking.md
grep -q "Direct player chatbox delivery proof is required" AGENTS.md
grep -q "Direct player chatbox delivery proof is required" README.md
grep -q -- "--agent-chat-delivery-log-text MARKER --agent-chat-delivery-log-to-name PLAYER" AGENTS.md
grep -q -- "--agent-chat-delivery-log-text MARKER --agent-chat-delivery-log-to-name PLAYER" README.md
grep -q -- "--agent-chat-delivery-log-text MARKER --agent-chat-delivery-log-to-name PLAYER" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q -- "--agent-chat-delivery-log-text MARKER" docs/network-auth-agent-chat-design.md
grep -q -- "--agent-chat-delivery-log-to-name PLAYER" docs/network-auth-agent-chat-design.md
grep -q "no runtime start/stop/restart" README.md
grep -q "no runtime start/stop/restart" docs/deployment-networking.md
grep -q "no runtime start/stop/restart" docs/network-auth-agent-chat-design.md
grep -q "no runtime start/stop/restart" .codex/skills/2006scape/SKILL.md
grep -q "no runtime start/stop/restart" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "no runtime start/stop/restart" .codex/skills/2006scape-external-deployment/SKILL.md
test -f .codex/skills/2006scape-external-deployment/SKILL.md
test -f .codex/skills/2006scape-external-deployment/agents/openai.yaml
grep -q "name: 2006scape-external-deployment" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "2006scape-external-deployment" .codex/skills/2006scape/SKILL.md
grep -q "scripts/backup-runtime-data.py" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "deployment_readiness_status" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "run deployment_readiness_status" .codex/skills/2006scape-script-registry/SKILL.md
grep -q -- "--require-full-proof" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "AgentBridgeServer" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q 'display_name: "2006Scape External Deployment"' .codex/skills/2006scape-external-deployment/agents/openai.yaml
grep -q 'default_prompt: "Use $2006scape-external-deployment' .codex/skills/2006scape-external-deployment/agents/openai.yaml
grep -q "runtime_data_backup" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "run runtime_data_backup" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "run runtime_data_backup -- --data-dir \"2006Scape Server/data\" --proof-manifest" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "desktop_client_proof" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "run desktop_client_proof" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "run desktop_client_proof -- --same-host-client LocalTest --external-client ExternalTest --transport tailscale --public-host HOST --evidence /path/to/evidence.png --proof-manifest" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "deployment_proof_manifest_check" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "deployment_proof_bundle" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "run deployment_proof_bundle" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "external_deployment_prepare" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "standalone_client_package" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "client_tls_tunnel_config" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "server_deployment_files" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "deployment_readiness_report" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "deployment_network_probe" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "run network proof" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "external_account_create" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "external_account_admin" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "run external_account_create -- ExternalTest --password-env ACCOUNT_PASSWORD" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "run external_account_create -- ExternalTest --password-env ACCOUNT_PASSWORD --overwrite --preserve-metadata" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "run external_account_admin -- --require-password-policy audit" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "game_login_probe" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "agent_chat_log_verify" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "agent_chat_player_delivery" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "agent chat log proof -- --text-contains MARKER --from-type discord --from-bot false --channel agent --proof-manifest" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "discord channel proof -- --text-contains MARKER --agent PROFILE --proof-manifest" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "discord_channel_message_verify" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "discord_agent_probe" .codex/skills/2006scape-script-registry/SKILL.md
grep -q '"id": "runtime_data_backup"' agent-navigation/data/script_registry.json
grep -q '"id": "desktop_client_proof"' agent-navigation/data/script_registry.json
grep -q '"id": "deployment_proof_manifest_check"' agent-navigation/data/script_registry.json
grep -q '"id": "deployment_proof_bundle"' agent-navigation/data/script_registry.json
grep -q '"id": "external_deployment_prepare"' agent-navigation/data/script_registry.json
grep -q '"id": "standalone_client_package"' agent-navigation/data/script_registry.json
grep -q '"id": "client_tls_tunnel_config"' agent-navigation/data/script_registry.json
grep -q '"id": "server_deployment_files"' agent-navigation/data/script_registry.json
grep -q '"id": "deployment_readiness_report"' agent-navigation/data/script_registry.json
grep -q '"id": "deployment_network_probe"' agent-navigation/data/script_registry.json
grep -q '"id": "agent_chat_log_verify"' agent-navigation/data/script_registry.json
grep -q '"id": "discord_channel_message_verify"' agent-navigation/data/script_registry.json
grep -q -- "--require-full-proof" README.md
grep -q -- "--require-full-proof" docs/deployment-networking.md
grep -q -- "--require-full-proof" docs/network-auth-agent-chat-design.md
grep -q "agent_chat_player_delivery" README.md
grep -q "agent_chat_player_delivery" docs/deployment-networking.md
grep -q "agent_chat_player_delivery" docs/network-auth-agent-chat-design.md
grep -q "agent_chat_player_delivery" docs/external-deployment-quickstart.md
grep -q -- "--agent-chat-delivery-log-text" docs/deployment-networking.md
grep -q -- "--agent-chat-delivery-log-to-name" docs/deployment-networking.md
grep -q "Direct agent/player chat delivery proof is required" docs/deployment-networking.md
grep -q -- "--agent-chat-delivery-log-text" docs/external-deployment-quickstart.md
grep -q -- "--agent-chat-delivery-log-to-name" docs/external-deployment-quickstart.md
grep -q "direct chat delivery proof" docs/external-deployment-quickstart.md
grep -q "agent_chat_player_delivery" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "proof-templates/desktop-client-proof.md" docs/deployment-networking.md
grep -q "proof-templates/runtime-data-backup-proof.md" README.md
grep -q "FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED" README.md
grep -q "LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_PROOF_RECORDED_DISCORD_NOT_REQUESTED" README.md
grep -q "LIVE_PROOF_PARTIAL_NEEDS_" docs/deployment-networking.md
grep -q "scripts/render-client-tls-tunnel-config.py" docs/deployment-networking.md
grep -q "scripts/render-server-deployment-files.py" docs/deployment-networking.md
grep -q "scripts/prepare-external-deployment.py" docs/deployment-networking.md
grep -q -- "--client-tls-tunnel-dir" README.md
grep -q -- "--client-tls-tunnel-dir" docs/deployment-networking.md
grep -q -- "--client-tls-tunnel-dir" docs/network-auth-agent-chat-design.md
grep -q -- "--client-tls-tunnel-dir" .codex/skills/2006scape/SKILL.md
grep -q -- "--client-tls-tunnel-dir" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q -- "--client-tls-tunnel-dir" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q -- "--client-tls-tunnel-dir" .codex/skills/2006scape-script-registry/SKILL.md
grep -q "client_tls_tunnel_server_accept_host" README.md
grep -q "client_tls_tunnel_server_accept_host" docs/deployment-networking.md
grep -q "client_tls_tunnel_server_accept_host" docs/network-auth-agent-chat-design.md
grep -q "client_tls_tunnel_server_accept_host" .codex/skills/2006scape-agent-bridge-dev/SKILL.md
grep -q "client_tls_tunnel_server_accept_host" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "non-placeholder" README.md
grep -q "non-placeholder" docs/deployment-networking.md
grep -q "placeholder.*--tls-sni-host" docs/network-auth-agent-chat-design.md
grep -q "real certificate hostname" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "client_tls_tunnel operator" agent-navigation/data/script_registry.json
grep -q "client-tls-tunnel/stunnel-client.conf" README.md
grep -q "TLS 1.2 or newer" docs/deployment-networking.md
grep -q "scripts/account-admin.py --require-password-policy audit" README.md
grep -q "rejects passwords shorter than 12 characters" README.md
grep -q "passwordPolicy" README.md
grep -q -- "--require-password-policy audit" README.md
grep -q "rejects passwords shorter than 12 characters" docs/deployment-networking.md
grep -q "missing or weak-override password policy metadata" docs/deployment-networking.md
grep -q "passwordPolicy" docs/network-auth-agent-chat-design.md
grep -q "rejects passwords shorter than 12 characters" scripts/render-server-deployment-files.py
grep -q "Java applet mode is not viable in modern browsers" docs/network-auth-agent-chat-design.md
grep -q "Browser play is documented as future research, not the external-player MVP" README.md
grep -q "The browser-client investigation is settled for this MVP" .codex/skills/2006scape-external-deployment/SKILL.md
grep -q "AWT/Swing frame and input handling" docs/deployment-networking.md
grep -q "raw Java sockets for the game, JAGGRAB, and on-demand cache protocols" docs/deployment-networking.md
grep -q "WebSocket/WebTransport protocol adapter" docs/network-auth-agent-chat-design.md
grep -q "do not pursue browser play for the external-player MVP" docs/network-auth-agent-chat-design.md
grep -q "## Future Decisions" docs/network-auth-agent-chat-design.md
grep -q "not blockers for the external-player MVP" docs/network-auth-agent-chat-design.md
grep -q "current regular-player MVP uses \`direct_tcp\`" docs/network-auth-agent-chat-design.md
grep -q "Tailscale, WireGuard, VPN, and the packaged \`client_tls_tunnel\` path remain supported alternatives" docs/network-auth-agent-chat-design.md
grep -q "## Completion And Proof Status" docs/network-auth-agent-chat-design.md
grep -q "### Requirement Evidence Matrix" docs/network-auth-agent-chat-design.md
grep -q "Multiple local and external players" docs/network-auth-agent-chat-design.md
grep -q "External transport" docs/network-auth-agent-chat-design.md
grep -q "Discord transport" docs/network-auth-agent-chat-design.md
grep -q "Minimal local disruption" docs/network-auth-agent-chat-design.md
if grep -q "## Open Decisions" docs/network-auth-agent-chat-design.md; then
    echo "network-auth-agent-chat-design.md still marks settled MVP decisions as open." >&2
    exit 1
fi
if grep -q "current MVP uses .*encrypted external access" docs/network-auth-agent-chat-design.md; then
    echo "network-auth-agent-chat-design.md still describes the MVP as encrypted-only." >&2
    exit 1
fi
grep -q "Server startup rejects external-player configs unless PBKDF2 account auth" README.md

echo "Smoke-testing account record creation..."
ACCOUNT_TMP_DIR="$(mktemp -d)"
if ACCOUNT_PASSWORD="short" \
    scripts/create-account.py WeakPassword --password-env ACCOUNT_PASSWORD --accounts-dir "$ACCOUNT_TMP_DIR/weak-accounts" \
    > "$ACCOUNT_TMP_DIR/weak-password-create.out" 2>&1; then
    echo "create-account.py unexpectedly accepted a short password." >&2
    cat "$ACCOUNT_TMP_DIR/weak-password-create.out" >&2
    exit 1
fi
grep -q "password must be at least 12 characters" "$ACCOUNT_TMP_DIR/weak-password-create.out"
ACCOUNT_PASSWORD="short" \
    scripts/create-account.py WeakPassword --password-env ACCOUNT_PASSWORD --accounts-dir "$ACCOUNT_TMP_DIR/weak-accounts" \
    --allow-weak-password
grep -q '"algorithm": "PBKDF2WithHmacSHA256"' "$ACCOUNT_TMP_DIR/weak-accounts/weakpassword.json"
grep -q '"allowWeakPassword": true' "$ACCOUNT_TMP_DIR/weak-accounts/weakpassword.json"
if scripts/account-admin.py --accounts-dir "$ACCOUNT_TMP_DIR/weak-accounts" \
    --require-password-policy audit > "$ACCOUNT_TMP_DIR/weak-policy-audit.out" 2>&1; then
    echo "account-admin.py unexpectedly accepted a weak-password policy record." >&2
    cat "$ACCOUNT_TMP_DIR/weak-policy-audit.out" >&2
    exit 1
fi
grep -q "passwordPolicy must not allow weak passwords" "$ACCOUNT_TMP_DIR/weak-policy-audit.out"
ACCOUNT_PASSWORD="temporary validation password" \
    scripts/create-account.py TestUser --password-env ACCOUNT_PASSWORD --accounts-dir "$ACCOUNT_TMP_DIR/accounts"
grep -q '"algorithm": "PBKDF2WithHmacSHA256"' "$ACCOUNT_TMP_DIR/accounts/testuser.json"
grep -q '"passwordIterations": 120000' "$ACCOUNT_TMP_DIR/accounts/testuser.json"
grep -q '"passwordPolicy": {' "$ACCOUNT_TMP_DIR/accounts/testuser.json"
grep -q '"allowWeakPassword": false' "$ACCOUNT_TMP_DIR/accounts/testuser.json"
grep -q '"minLength": 12' "$ACCOUNT_TMP_DIR/accounts/testuser.json"
ACCOUNT_PASSWORD="temporary validation password" \
    scripts/create-account.py TestShaOne --password-env ACCOUNT_PASSWORD --accounts-dir "$ACCOUNT_TMP_DIR/accounts" --algorithm sha1
grep -q '"algorithm": "PBKDF2WithHmacSHA1"' "$ACCOUNT_TMP_DIR/accounts/testshaone.json"
ACCOUNT_PASSWORD="temporary validation password" \
    scripts/create-account.py TestMeta --password-env ACCOUNT_PASSWORD --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --role admin --role agent:runner --allowed-character TestMeta --allowed-character MrFlame \
    --discord-user-id 123456789012345678
scripts/account-admin.py --accounts-dir "$ACCOUNT_TMP_DIR/accounts" --require-password-policy audit > "$ACCOUNT_TMP_DIR/account-audit.out"
grep -q "summary: total=3 enabled=3 disabled=0 invalid=0" "$ACCOUNT_TMP_DIR/account-audit.out"
scripts/account-admin.py --accounts-dir "$ACCOUNT_TMP_DIR/accounts" --require-password-policy list --json > "$ACCOUNT_TMP_DIR/account-list.json"
python3 - "$ACCOUNT_TMP_DIR/account-list.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as source:
    report = json.load(source)
assert report["total"] == 3, report
assert report["enabled"] == 3, report
assert report["invalid"] == 0, report
testmeta = next(account for account in report["accounts"] if account["username"] == "testmeta")
assert testmeta["passwordPolicy"]["present"] is True, testmeta
assert testmeta["passwordPolicy"]["allowWeakPassword"] is False, testmeta
assert testmeta["passwordPolicy"]["minLength"] == 12, testmeta
PY
scripts/account-admin.py --accounts-dir "$ACCOUNT_TMP_DIR/accounts" --require-password-policy show TestMeta --json > "$ACCOUNT_TMP_DIR/account-show-testmeta.json"
python3 - "$ACCOUNT_TMP_DIR/accounts/testmeta.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as source:
    record = json.load(source)
assert record["roles"] == ["admin", "agent:runner"], record
assert record["allowedCharacters"] == ["testmeta", "mrflame"], record
assert record["discordUserId"] == "123456789012345678", record
PY
python3 - "$ACCOUNT_TMP_DIR/account-show-testmeta.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as source:
    account = json.load(source)
assert account["username"] == "testmeta", account
assert account["roles"] == ["admin", "agent:runner"], account
assert account["allowedCharacters"] == ["testmeta", "mrflame"], account
assert account["discordUserId"] == "123456789012345678", account
assert account["passwordPolicy"]["present"] is True, account
assert account["passwordPolicy"]["allowWeakPassword"] is False, account
assert account["valid"] is True, account
PY
scripts/account-admin.py --accounts-dir "$ACCOUNT_TMP_DIR/accounts" disable TestMeta
grep -q '"disabled": true' "$ACCOUNT_TMP_DIR/accounts/testmeta.json"
scripts/account-admin.py --accounts-dir "$ACCOUNT_TMP_DIR/accounts" enable TestMeta
grep -q '"disabled": false' "$ACCOUNT_TMP_DIR/accounts/testmeta.json"
OLD_TESTMETA_HASH="$(python3 - "$ACCOUNT_TMP_DIR/accounts/testmeta.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as source:
    print(json.load(source)["passwordHash"])
PY
)"
ACCOUNT_PASSWORD="rotated validation password" \
    scripts/create-account.py TestMeta --password-env ACCOUNT_PASSWORD --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --overwrite --preserve-metadata
python3 - "$ACCOUNT_TMP_DIR/accounts/testmeta.json" "$OLD_TESTMETA_HASH" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as source:
    record = json.load(source)
assert record["roles"] == ["admin", "agent:runner"], record
assert record["allowedCharacters"] == ["testmeta", "mrflame"], record
assert record["discordUserId"] == "123456789012345678", record
assert record["disabled"] is False, record
assert record["passwordHash"] != sys.argv[2], record
assert record["passwordPolicy"]["allowWeakPassword"] is False, record
assert record["passwordPolicy"]["minLength"] == 12, record
PY
ACCOUNT_PASSWORD="temporary validation password" \
    scripts/create-account.py TestDisabled --password-env ACCOUNT_PASSWORD --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --disabled --role held
ACCOUNT_PASSWORD="rotated validation password" \
    scripts/create-account.py TestDisabled --password-env ACCOUNT_PASSWORD --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --overwrite --preserve-metadata --enabled
python3 - "$ACCOUNT_TMP_DIR/accounts/testdisabled.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as source:
    record = json.load(source)
assert record["roles"] == ["held"], record
assert record["disabled"] is False, record
PY
if ACCOUNT_PASSWORD="temporary validation password" \
    scripts/create-account.py BadDiscord --password-env ACCOUNT_PASSWORD --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --discord-user-id abc > "$ACCOUNT_TMP_DIR/bad-discord-create.out" 2>&1; then
    echo "create-account.py unexpectedly accepted a malformed Discord user id." >&2
    cat "$ACCOUNT_TMP_DIR/bad-discord-create.out" >&2
    exit 1
fi
grep -q "discord user id must be a numeric Discord snowflake string" "$ACCOUNT_TMP_DIR/bad-discord-create.out"
cp "$ACCOUNT_TMP_DIR/accounts/testuser.json" "$ACCOUNT_TMP_DIR/accounts/brokenuser.json"
python3 - "$ACCOUNT_TMP_DIR/accounts/brokenuser.json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as source:
    record = json.load(source)
record["username"] = "brokenuser"
record["passwordIterations"] = 1
with open(path, "w", encoding="utf-8") as target:
    json.dump(record, target, indent=2, sort_keys=True)
    target.write("\n")
PY
if scripts/account-admin.py --accounts-dir "$ACCOUNT_TMP_DIR/accounts" audit > "$ACCOUNT_TMP_DIR/bad-account-audit.out" 2>&1; then
    echo "account-admin.py unexpectedly accepted a weak account record." >&2
    cat "$ACCOUNT_TMP_DIR/bad-account-audit.out" >&2
    exit 1
fi
grep -q "passwordIterations must be at least 120000" "$ACCOUNT_TMP_DIR/bad-account-audit.out"
rm -f "$ACCOUNT_TMP_DIR/accounts/brokenuser.json"
if ln -s "$ACCOUNT_TMP_DIR/accounts/testuser.json" "$ACCOUNT_TMP_DIR/accounts/symlinkuser.json" 2>/dev/null; then
    if ACCOUNT_PASSWORD="temporary validation password" \
        scripts/create-account.py SymlinkUser --password-env ACCOUNT_PASSWORD --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
        --overwrite > "$ACCOUNT_TMP_DIR/symlink-create.out" 2>&1; then
        echo "create-account.py unexpectedly wrote through a symlinked account record." >&2
        cat "$ACCOUNT_TMP_DIR/symlink-create.out" >&2
        exit 1
    fi
    grep -q "refusing to write symlinked account record" "$ACCOUNT_TMP_DIR/symlink-create.out"
    rm -f "$ACCOUNT_TMP_DIR/accounts/symlinkuser.json"
fi

echo "Running full Maven test suite..."
"$MAVEN_BIN" -q clean test

echo "Packaging server and client artifacts from a clean target directory..."
"$MAVEN_BIN" -q clean -DskipTests package

echo "Smoke-testing isolated alternate-port runtime startup..."
python3 scripts/smoke-network-auth-chat-runtime.py

echo "Smoke-testing standalone client packaging in a temporary dist directory..."
TMP_DIR="$(mktemp -d)"
TMP_DIR="$(cd "$TMP_DIR" && pwd -P)"
cat > "$TMP_DIR/wildcard-public-host-config.json" <<'JSON'
{
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "external_transport_mode": "tailscale",
  "game_bind_hosts": ["127.0.0.1", "100.64.0.10"],
  "public_game_host": "0.0.0.0",
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
if scripts/preflight-external-config.py "$TMP_DIR/wildcard-public-host-config.json" > "$TMP_DIR/wildcard-public-host-preflight.out" 2>&1; then
    echo "preflight-external-config.py unexpectedly accepted a wildcard public_game_host." >&2
    cat "$TMP_DIR/wildcard-public-host-preflight.out" >&2
    exit 1
fi
grep -q "public_game_host must not be localhost, loopback, or wildcard" "$TMP_DIR/wildcard-public-host-preflight.out"

cat > "$TMP_DIR/malformed-bind-host-config.json" <<'JSON'
{
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "external_transport_mode": "tailscale",
  "game_bind_hosts": ["127.0.0.1", 100],
  "http_bind_hosts": ["127.0.0.1", "100.64.0.10"],
  "jaggrab_bind_hosts": ["127.0.0.1", "100.64.0.10"],
  "public_game_host": "example-tailnet-host",
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
if scripts/preflight-external-config.py "$TMP_DIR/malformed-bind-host-config.json" > "$TMP_DIR/malformed-bind-host-preflight.out" 2>&1; then
    echo "preflight-external-config.py unexpectedly accepted a non-string bind host value." >&2
    cat "$TMP_DIR/malformed-bind-host-preflight.out" >&2
    exit 1
fi
grep -q "game_bind_hosts\\[1\\] must be a string" "$TMP_DIR/malformed-bind-host-preflight.out"

cat > "$TMP_DIR/control-character-host-config.json" <<'JSON'
{
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "external_transport_mode": "tailscale",
  "game_bind_hosts": ["127.0.0.1", "100.64.0.10"],
  "http_bind_hosts": ["127.0.0.1", "100.64.0.10"],
  "jaggrab_bind_hosts": ["127.0.0.1", "100.64.0.10"],
  "public_game_host": "example-tailnet-host\nserver.port=1",
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
if scripts/preflight-external-config.py "$TMP_DIR/control-character-host-config.json" > "$TMP_DIR/control-character-host-preflight.out" 2>&1; then
    echo "preflight-external-config.py unexpectedly accepted a control character in public_game_host." >&2
    cat "$TMP_DIR/control-character-host-preflight.out" >&2
    exit 1
fi
grep -q "public_game_host must be a single-line value without control characters" "$TMP_DIR/control-character-host-preflight.out"

cat > "$TMP_DIR/mixed-wildcard-bind-config.json" <<'JSON'
{
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "external_transport_mode": "tailscale",
  "wildcard_bind_confirmed": true,
  "game_bind_hosts": ["0.0.0.0", "127.0.0.1"],
  "http_bind_hosts": ["0.0.0.0"],
  "jaggrab_bind_hosts": ["0.0.0.0"],
  "public_game_host": "example-tailnet-host",
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
if scripts/preflight-external-config.py "$TMP_DIR/mixed-wildcard-bind-config.json" --allow-wildcard-bind > "$TMP_DIR/mixed-wildcard-bind-preflight.out" 2>&1; then
    echo "preflight-external-config.py unexpectedly accepted wildcard and specific bind hosts in one listener set." >&2
    cat "$TMP_DIR/mixed-wildcard-bind-preflight.out" >&2
    exit 1
fi
grep -q "game_bind_hosts must not mix wildcard bind hosts with specific hosts" "$TMP_DIR/mixed-wildcard-bind-preflight.out"

cat > "$TMP_DIR/file-server-disabled-overlap-config.json" <<'JSON'
{
  "file_server": false,
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "external_transport_mode": "tailscale",
  "game_bind_hosts": ["127.0.0.1", "100.64.0.10"],
  "public_game_host": "example-tailnet-host",
  "game_port": 43594,
  "http_port": 43594,
  "jaggrab_port": 43594,
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
scripts/preflight-external-config.py "$TMP_DIR/file-server-disabled-overlap-config.json" > "$TMP_DIR/file-server-disabled-overlap-preflight.out"
grep -q "ok: external-player config passed preflight" "$TMP_DIR/file-server-disabled-overlap-preflight.out"

cat > "$TMP_DIR/private-network-transport-config.json" <<'JSON'
{
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "external_transport_mode": "private_network",
  "game_bind_hosts": ["127.0.0.1", "100.64.0.10"],
  "public_game_host": "example-tailnet-host",
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
if scripts/preflight-external-config.py "$TMP_DIR/private-network-transport-config.json" > "$TMP_DIR/private-network-transport-preflight.out" 2>&1; then
    echo "preflight-external-config.py unexpectedly accepted private_network as an encrypted external transport." >&2
    cat "$TMP_DIR/private-network-transport-preflight.out" >&2
    exit 1
fi
grep -q "external_transport_mode must be one of" "$TMP_DIR/private-network-transport-preflight.out"

cat > "$TMP_DIR/loopback-cache-bind-config.json" <<'JSON'
{
  "file_server": true,
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "external_transport_mode": "tailscale",
  "game_bind_hosts": ["127.0.0.1", "100.64.0.10"],
  "http_bind_hosts": ["127.0.0.1"],
  "jaggrab_bind_hosts": ["127.0.0.1", "100.64.0.10"],
  "public_game_host": "example-tailnet-host",
  "game_port": 43594,
  "http_port": 8080,
  "jaggrab_port": 43595,
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
if scripts/preflight-external-config.py "$TMP_DIR/loopback-cache-bind-config.json" > "$TMP_DIR/loopback-cache-bind.out" 2>&1; then
    echo "preflight-external-config.py unexpectedly accepted loopback-only cache binds for external file_server=true." >&2
    cat "$TMP_DIR/loopback-cache-bind.out" >&2
    exit 1
fi
grep -q "http_bind_hosts are loopback only while file_server=true" "$TMP_DIR/loopback-cache-bind.out"

if scripts/preflight-external-config.py "$TMP_DIR/loopback-cache-bind-config.json" --allow-legacy-auth > "$TMP_DIR/legacy-auth-flag.out" 2>&1; then
    echo "preflight-external-config.py unexpectedly accepted the removed --allow-legacy-auth flag." >&2
    cat "$TMP_DIR/legacy-auth-flag.out" >&2
    exit 1
fi
grep -q "unrecognized arguments: --allow-legacy-auth" "$TMP_DIR/legacy-auth-flag.out"

cat > "$TMP_DIR/client-tls-tunnel-config.json" <<'JSON'
{
  "file_server": true,
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "external_transport_mode": "client_tls_tunnel",
  "game_bind_hosts": ["127.0.0.1"],
  "http_bind_hosts": ["127.0.0.1"],
  "jaggrab_bind_hosts": ["127.0.0.1"],
  "public_game_host": "tls.example.net",
  "game_port": 43594,
  "http_port": 8080,
  "jaggrab_port": 43595,
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
scripts/preflight-external-config.py "$TMP_DIR/client-tls-tunnel-config.json" > "$TMP_DIR/client-tls-tunnel-preflight.out"
grep -q "ok: external-player config passed preflight" "$TMP_DIR/client-tls-tunnel-preflight.out"
grep -q "client_tls_tunnel packages default client_connect_host to 127.0.0.1" "$TMP_DIR/client-tls-tunnel-preflight.out"
python3 - "$TMP_DIR/client-tls-tunnel-config.json" "$TMP_DIR/client-tls-tunnel-wildcard-accept-config.json" <<'PY'
import json
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
config = json.loads(source.read_text(encoding="utf-8"))
config["client_tls_tunnel_server_accept_host"] = "0.0.0.0"
target.write_text(json.dumps(config), encoding="utf-8")
PY
if scripts/preflight-external-config.py "$TMP_DIR/client-tls-tunnel-wildcard-accept-config.json" > "$TMP_DIR/client-tls-tunnel-wildcard-accept.out" 2>&1; then
    echo "preflight-external-config.py unexpectedly accepted a wildcard client_tls_tunnel server accept host." >&2
    cat "$TMP_DIR/client-tls-tunnel-wildcard-accept.out" >&2
    exit 1
fi
grep -q "client_tls_tunnel_server_accept_host must not be wildcard" "$TMP_DIR/client-tls-tunnel-wildcard-accept.out"
python3 - "$TMP_DIR/client-tls-tunnel-config.json" "$TMP_DIR/client-tls-tunnel-placeholder-accept-config.json" <<'PY'
import json
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
config = json.loads(source.read_text(encoding="utf-8"))
config["client_tls_tunnel_server_accept_host"] = "REPLACE_WITH_PUBLIC_GAME_HOST"
target.write_text(json.dumps(config), encoding="utf-8")
PY
if scripts/render-client-tls-tunnel-config.py \
    --config "$TMP_DIR/client-tls-tunnel-placeholder-accept-config.json" \
    --output-dir "$TMP_DIR/client-tls-tunnel-placeholder-accept" > "$TMP_DIR/client-tls-tunnel-placeholder-accept.out" 2>&1; then
    echo "render-client-tls-tunnel-config.py unexpectedly accepted a placeholder client_tls_tunnel_server_accept_host." >&2
    cat "$TMP_DIR/client-tls-tunnel-placeholder-accept.out" >&2
    exit 1
fi
grep -q "client_tls_tunnel_server_accept_host still contains a placeholder network value" "$TMP_DIR/client-tls-tunnel-placeholder-accept.out"
scripts/render-client-tls-tunnel-config.py \
    --config "$TMP_DIR/client-tls-tunnel-config.json" \
    --output-dir "$TMP_DIR/client-tls-tunnel-templates"
grep -q "stunnel stunnel-client.conf" "$TMP_DIR/client-tls-tunnel-templates/README.txt"
grep -q "server-side tunnel accept host: tls.example.net" "$TMP_DIR/client-tls-tunnel-templates/README.txt"
grep -q "verifyChain = yes" "$TMP_DIR/client-tls-tunnel-templates/stunnel-client.conf"
grep -q "sslVersionMin = TLSv1.2" "$TMP_DIR/client-tls-tunnel-templates/stunnel-client.conf"
grep -q "checkHost = tls.example.net" "$TMP_DIR/client-tls-tunnel-templates/stunnel-client.conf"
grep -q "accept = 127.0.0.1:43594" "$TMP_DIR/client-tls-tunnel-templates/stunnel-client.conf"
grep -q "connect = tls.example.net:43594" "$TMP_DIR/client-tls-tunnel-templates/stunnel-client.conf"
grep -q "sslVersionMin = TLSv1.2" "$TMP_DIR/client-tls-tunnel-templates/stunnel-server.conf"
grep -q "cert = /etc/letsencrypt/live/tls.example.net/fullchain.pem" "$TMP_DIR/client-tls-tunnel-templates/stunnel-server.conf"
grep -q "accept = tls.example.net:43594" "$TMP_DIR/client-tls-tunnel-templates/stunnel-server.conf"
grep -q "connect = 127.0.0.1:43594" "$TMP_DIR/client-tls-tunnel-templates/stunnel-server.conf"
scripts/render-client-tls-tunnel-config.py \
    --config "$TMP_DIR/client-tls-tunnel-config.json" \
    --output-dir "$TMP_DIR/client-tls-tunnel-cert-host-templates" \
    --tls-cert-host cert.example.net
grep -q "checkHost = cert.example.net" "$TMP_DIR/client-tls-tunnel-cert-host-templates/stunnel-client.conf"
grep -q "cert = /etc/letsencrypt/live/cert.example.net/fullchain.pem" "$TMP_DIR/client-tls-tunnel-cert-host-templates/stunnel-server.conf"
grep -q "accept = tls.example.net:43594" "$TMP_DIR/client-tls-tunnel-cert-host-templates/stunnel-server.conf"
if scripts/render-client-tls-tunnel-config.py \
    --config "$TMP_DIR/client-tls-tunnel-config.json" \
    --output-dir "$TMP_DIR/client-tls-tunnel-placeholder-cert-host-templates" \
    --tls-cert-host REPLACE_WITH_PUBLIC_GAME_HOST > "$TMP_DIR/client-tls-tunnel-placeholder-cert-host.out" 2>&1; then
    echo "render-client-tls-tunnel-config.py unexpectedly accepted a placeholder --tls-cert-host." >&2
    cat "$TMP_DIR/client-tls-tunnel-placeholder-cert-host.out" >&2
    exit 1
fi
grep -q -- "--tls-cert-host still contains a placeholder network value" "$TMP_DIR/client-tls-tunnel-placeholder-cert-host.out"
CLIENT_SERVER_CONFIG="$TMP_DIR/client-tls-tunnel-config.json" \
CLIENT_DIST_DIR="$TMP_DIR/client-tls-tunnel-client" \
CLIENT_ARCHIVE_PATH="$TMP_DIR/client-tls-tunnel-client.zip" \
SKIP_BUILD=1 \
    scripts/package-client.sh
grep -q "server.host=127.0.0.1" "$TMP_DIR/client-tls-tunnel-client/client.properties"
grep -q "server_host=127.0.0.1" "$TMP_DIR/client-tls-tunnel-client/MANIFEST.txt"
grep -q "public_game_host=tls.example.net" "$TMP_DIR/client-tls-tunnel-client/MANIFEST.txt"
grep -Eq '^source_server_config_sha256=[0-9a-f]{64}$' "$TMP_DIR/client-tls-tunnel-client/MANIFEST.txt"
grep -q "secure.transport=client_tls_tunnel" "$TMP_DIR/client-tls-tunnel-client/client.properties"
grep -q "Transport setup:" "$TMP_DIR/client-tls-tunnel-client/README.txt"
grep -q "launchers try to start the bundled" "$TMP_DIR/client-tls-tunnel-client/README.txt"
grep -q "stunnel client-tls-tunnel/stunnel-client.conf" "$TMP_DIR/client-tls-tunnel-client/README.txt"
grep -q "stunnel carries that" "$TMP_DIR/client-tls-tunnel-client/README.txt"
grep -q "macOS/Linux setup checker: can start stunnel temporarily for TCP checks" "$TMP_DIR/client-tls-tunnel-client/README.txt"
grep -q "Windows setup checker: expects the local tunnel endpoint" "$TMP_DIR/client-tls-tunnel-client/README.txt"
grep -q "traffic over TLS to tls.example.net" "$TMP_DIR/client-tls-tunnel-client/README.txt"
grep -q "Use the username and password provided by the server operator" "$TMP_DIR/client-tls-tunnel-client/README.txt"
grep -q "Do not use a RuneScape.com password or reuse passwords from other services" "$TMP_DIR/client-tls-tunnel-client/README.txt"
grep -q "Starting stunnel for encrypted 2006Scape transport" "$TMP_DIR/client-tls-tunnel-client/run-macos-linux.sh"
grep -q "Starting stunnel for encrypted 2006Scape transport" "$TMP_DIR/client-tls-tunnel-client/run-windows.bat"
grep -q "Starting stunnel temporarily for setup checks" "$TMP_DIR/client-tls-tunnel-client/check-setup-macos-linux.sh"
grep -q "start_client_tls_tunnel_for_setup" "$TMP_DIR/client-tls-tunnel-client/check-setup-macos-linux.sh"
grep -q "expects the local tunnel endpoint to be reachable first" "$TMP_DIR/client-tls-tunnel-client/check-setup-windows.bat"
test -f "$TMP_DIR/client-tls-tunnel-client/client-tls-tunnel/README.txt"
test -f "$TMP_DIR/client-tls-tunnel-client/client-tls-tunnel/stunnel-client.conf"
grep -q "it starts this stunnel config" "$TMP_DIR/client-tls-tunnel-client/client-tls-tunnel/README.txt"
grep -q "The Java client still speaks plaintext to 127.0.0.1" "$TMP_DIR/client-tls-tunnel-client/client-tls-tunnel/README.txt"
grep -q "TLS 1.2 or newer" "$TMP_DIR/client-tls-tunnel-client/client-tls-tunnel/README.txt"
grep -q "sslVersionMin = TLSv1.2" "$TMP_DIR/client-tls-tunnel-client/client-tls-tunnel/stunnel-client.conf"
grep -q "connect = tls.example.net:43594" "$TMP_DIR/client-tls-tunnel-client/client-tls-tunnel/stunnel-client.conf"
(cd "$TMP_DIR/client-tls-tunnel-client" && shasum -a 256 -c SHA256SUMS >/dev/null)
scripts/render-server-deployment-files.py \
    --config "$TMP_DIR/client-tls-tunnel-config.json" \
    --output-dir "$TMP_DIR/client-tls-tunnel-server-deployment" > "$TMP_DIR/client-tls-tunnel-server-deployment.out"
grep -q "ok: rendered server deployment files" "$TMP_DIR/client-tls-tunnel-server-deployment.out"
scripts/verify-external-deployment.py \
    --config "$TMP_DIR/client-tls-tunnel-config.json" \
    --client-dist "$TMP_DIR/client-tls-tunnel-client" \
    --server-deployment-dir "$TMP_DIR/client-tls-tunnel-server-deployment" \
    --client-tls-tunnel-dir "$TMP_DIR/client-tls-tunnel-templates" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" > "$TMP_DIR/client-tls-tunnel-verify.out"
grep -q "ok: external deployment artifacts verified" "$TMP_DIR/client-tls-tunnel-verify.out"
grep -q "server_deployment: $TMP_DIR/client-tls-tunnel-server-deployment" "$TMP_DIR/client-tls-tunnel-verify.out"
grep -q "client_tls_tunnel: $TMP_DIR/client-tls-tunnel-templates" "$TMP_DIR/client-tls-tunnel-verify.out"
if scripts/verify-external-deployment.py \
    --config "$TMP_DIR/client-tls-tunnel-config.json" \
    --client-dist "$TMP_DIR/client-tls-tunnel-client" \
    --server-deployment-dir "$TMP_DIR/client-tls-tunnel-server-deployment" \
    --client-tls-tunnel-dir "$TMP_DIR/client-tls-tunnel-templates" \
    --tls-sni-host REPLACE_WITH_PUBLIC_GAME_HOST \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" > "$TMP_DIR/client-tls-tunnel-placeholder-sni-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a placeholder --tls-sni-host." >&2
    cat "$TMP_DIR/client-tls-tunnel-placeholder-sni-verify.out" >&2
    exit 1
fi
grep -q -- "--tls-sni-host still contains a placeholder network value" "$TMP_DIR/client-tls-tunnel-placeholder-sni-verify.out"
python3 - <<'PY'
import importlib.util
from pathlib import Path

module_path = Path("scripts/verify-external-deployment.py")
spec = importlib.util.spec_from_file_location("verify_external_deployment", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
config = {
    "public_game_host": "tls.example.net",
    "client_tls_tunnel_server_accept_host": "REPLACE_WITH_PUBLIC_GAME_HOST",
}
try:
    module.verify_network_placeholders(config, False)
except SystemExit as exc:
    assert "client_tls_tunnel_server_accept_host still contains a placeholder network value" in str(exc), exc
else:
    raise AssertionError("verify_network_placeholders accepted placeholder client_tls_tunnel_server_accept_host")
PY
CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json" \
CLIENT_DIST_DIR="$TMP_DIR/tracked-client-tls-tunnel-client" \
CLIENT_ARCHIVE_PATH="$TMP_DIR/tracked-client-tls-tunnel-client.zip" \
CLIENT_ALLOW_PLACEHOLDER_NETWORK_CONFIG=1 \
SKIP_BUILD=1 \
    scripts/package-client.sh
grep -q "server.host=127.0.0.1" "$TMP_DIR/tracked-client-tls-tunnel-client/client.properties"
grep -q "public_game_host=REPLACE_WITH_PUBLIC_TLS_HOST" "$TMP_DIR/tracked-client-tls-tunnel-client/MANIFEST.txt"
grep -q "expected_external_transport=client_tls_tunnel" "$TMP_DIR/tracked-client-tls-tunnel-client/MANIFEST.txt"
grep -q "checkHost = REPLACE_WITH_PUBLIC_TLS_HOST" "$TMP_DIR/tracked-client-tls-tunnel-client/client-tls-tunnel/stunnel-client.conf"
if CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json" \
    CLIENT_DIST_DIR="$TMP_DIR/tracked-client-tls-tunnel-strict" \
    CLIENT_ARCHIVE_PATH="$TMP_DIR/tracked-client-tls-tunnel-strict.zip" \
    SKIP_BUILD=1 \
    scripts/package-client.sh > "$TMP_DIR/tracked-client-tls-tunnel-strict.out" 2>&1; then
    echo "package-client.sh unexpectedly accepted placeholder client_tls_tunnel sample without source-validation allowance." >&2
    cat "$TMP_DIR/tracked-client-tls-tunnel-strict.out" >&2
    exit 1
fi
grep -q "public_game_host still contains a placeholder network value" "$TMP_DIR/tracked-client-tls-tunnel-strict.out"
cp -R "$TMP_DIR/client-tls-tunnel-templates" "$TMP_DIR/broken-client-tls-tunnel-templates"
printf 'broken\n' > "$TMP_DIR/broken-client-tls-tunnel-templates/stunnel-server.conf"
if scripts/verify-external-deployment.py \
    --config "$TMP_DIR/client-tls-tunnel-config.json" \
    --client-dist "$TMP_DIR/client-tls-tunnel-client" \
    --server-deployment-dir "$TMP_DIR/client-tls-tunnel-server-deployment" \
    --client-tls-tunnel-dir "$TMP_DIR/broken-client-tls-tunnel-templates" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" > "$TMP_DIR/broken-client-tls-tunnel-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a broken operator stunnel server config." >&2
    cat "$TMP_DIR/broken-client-tls-tunnel-verify.out" >&2
    exit 1
fi
grep -q "client TLS tunnel server config is missing required text" "$TMP_DIR/broken-client-tls-tunnel-verify.out"
scripts/prepare-external-deployment.py \
    --config "$TMP_DIR/client-tls-tunnel-config.json" \
    --output-dir "$TMP_DIR/prepared-client-tls-tunnel" \
    --json-output "$TMP_DIR/prepared-client-tls-tunnel/deployment-readiness-report.json" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --skip-build > "$TMP_DIR/prepare-client-tls-tunnel.out"
grep -q "prepared external deployment artifacts" "$TMP_DIR/prepare-client-tls-tunnel.out"
grep -q "readiness_json: $TMP_DIR/prepared-client-tls-tunnel/deployment-readiness-report.json" "$TMP_DIR/prepare-client-tls-tunnel.out"
grep -q "runtime: not started, stopped, or restarted" "$TMP_DIR/prepare-client-tls-tunnel.out"
test -f "$TMP_DIR/prepared-client-tls-tunnel/2006scape-client/client.properties"
test -f "$TMP_DIR/prepared-client-tls-tunnel/2006scape-client.zip"
test -f "$TMP_DIR/prepared-client-tls-tunnel/deployment-readiness-report.md"
test -f "$TMP_DIR/prepared-client-tls-tunnel/deployment-readiness-report.json"
test -f "$TMP_DIR/prepared-client-tls-tunnel/client-tls-tunnel-operator/stunnel-server.conf"
test -f "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/2006scape-server.service"
test -f "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/2006scape-server.env"
test -f "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/firewall-ufw-example.sh"
test -f "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/ServerConfig.json"
test -f "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/desktop-client-proof.md"
test -f "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/runtime-data-backup-proof.md"
grep -q 'status: `PASS`' "$TMP_DIR/prepared-client-tls-tunnel/deployment-readiness-report.md"
grep -q 'deploymentProofStatus: `STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF`' "$TMP_DIR/prepared-client-tls-tunnel/deployment-readiness-report.md"
grep -q "Proof Coverage" "$TMP_DIR/prepared-client-tls-tunnel/deployment-readiness-report.md"
grep -q "serverDeploymentDir: " "$TMP_DIR/prepared-client-tls-tunnel/deployment-readiness-report.md"
grep -q "clientTlsTunnelDir: " "$TMP_DIR/prepared-client-tls-tunnel/deployment-readiness-report.md"
test "$(grep -c "^- clientTlsTunnelDir:" "$TMP_DIR/prepared-client-tls-tunnel/deployment-readiness-report.md")" = "1"
python3 - "$TMP_DIR/prepared-client-tls-tunnel/deployment-readiness-report.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["schemaVersion"] == 1, data
assert data["status"] == "PASS", data
assert data["deploymentProofStatus"] == "STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF", data
assert data["liveChecksRequested"] is False, data
assert data["inputs"]["clientTlsTunnelDir"], data
assert data["inputs"]["serverDeploymentDir"], data
coverage = {item["requirement"]: item for item in data["proofCoverage"]}
assert coverage["Public reachability and bridge non-exposure"]["status"] == "MISSING", coverage
assert any(check["label"] == "deployment verification" and check["status"] == "PASS" for check in data["checks"]), data["checks"]
assert data["markdownReport"].endswith("deployment-readiness-report.md"), data
PY
grep -q "accept = tls.example.net:43594" "$TMP_DIR/prepared-client-tls-tunnel/client-tls-tunnel-operator/stunnel-server.conf"
grep -q "connect = 127.0.0.1:43594" "$TMP_DIR/prepared-client-tls-tunnel/client-tls-tunnel-operator/stunnel-server.conf"
grep -q "sslVersionMin = TLSv1.2" "$TMP_DIR/prepared-client-tls-tunnel/client-tls-tunnel-operator/stunnel-server.conf"
grep -q "ExecStart=/opt/2006scape/scripts/start-server.sh" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/2006scape-server.service"
grep -q "CapabilityBoundingSet=" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/2006scape-server.service"
grep -q "PrivateDevices=true" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/2006scape-server.service"
grep -q "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/2006scape-server.service"
grep -q "SystemCallArchitectures=native" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/2006scape-server.service"
grep -q "SERVER_CONFIG=/etc/2006scape/ServerConfig.json" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/2006scape-server.env"
grep -q "Do not expose 2006Scape AgentBridgeServer" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/firewall-ufw-example.sh"
grep -q 'This bundle does not include real `data/secrets.json`' "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "## Account And Secret Files" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "2006Scape Server/data/accounts" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "2006Scape Server/data/secrets.json" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "scripts/account-admin.py --accounts-dir" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q -- "--require-password-policy audit" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "scripts/create-account.py --overwrite --preserve-metadata" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "reject missing or weak-override password policy metadata" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q 'Do not symlink `data/secrets.json` or `data/accounts`' "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "## Runtime Data Safety" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "2006Scape Server/data/characters" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "Back up those paths before an intentional remote restart or migration" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q 'Do not overwrite `data/characters`, `data/accounts`, or `data/secrets.json`' "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "scripts/backup-runtime-data.py" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "owner-only archive/proof files" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "rejects symlinked proof notes" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "Desktop client proof must include an \`evidence\` path to a real non-symlink screenshot/log file" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "scripts/write-desktop-client-proof.py" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "backup archive sha256" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q -- "--runtime-data-backup-proof-file" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "## Proof Note Templates" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "proof-templates/deployment-proof-manifest.json" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "proof-templates/desktop-client-proof.md" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "proof-templates/runtime-data-backup-proof.md" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q -- "--proof-manifest" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "scripts/check-deployment-proof-manifest.py deployment-proof-manifest.json --config ServerConfig.json --secrets '/opt/2006scape/2006Scape Server/data/secrets.json' --require-full-proof --check-files --check-env" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "validates desktop proof evidence and runtime-backup archive/checksum details" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "Final-gate manifests must keep \`require_full_proof:true\`" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "Relative proof-note paths in the manifest are resolved from the manifest file's directory" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "scripts/package-deployment-proof.py" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "## Live Chat Proof" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "agent_chat_player_delivery" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q -- "--agent-chat-delivery-log-text" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/README.md"
grep -q "live_login_password_env" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/deployment-proof-manifest.json"
grep -q "live_reject_login_expected_statuses" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/deployment-proof-manifest.json"
grep -q "runtime_data_backup_proof_file" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/deployment-proof-manifest.json"
grep -q "agent_chat_delivery_log_text" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/deployment-proof-manifest.json"
grep -q "discord_channel_message_text" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/deployment-proof-manifest.json"
grep -q '"require_full_proof": true' "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/deployment-proof-manifest.json"
grep -q "LOCAL_USERNAME" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/desktop-client-proof.md"
grep -q "EXTERNAL_USERNAME" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/desktop-client-proof.md"
grep -q "SCREENSHOT_PATH_OR_LOG_PATH" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/desktop-client-proof.md"
grep -q "scripts/write-desktop-client-proof.py" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/desktop-client-proof.md"
grep -q -- "--desktop-client-proof-file" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/desktop-client-proof.md"
grep -q "BACKUP_ARCHIVE" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/runtime-data-backup-proof.md"
grep -q "BACKUP_ARCHIVE_SHA256" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/runtime-data-backup-proof.md"
grep -q "runtime: not started, stopped, or restarted" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/runtime-data-backup-proof.md"
grep -q "scripts/backup-runtime-data.py" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/runtime-data-backup-proof.md"
grep -q "2006Scape Server/data/characters" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/runtime-data-backup-proof.md"
grep -q "readiness argument: --runtime-data-backup-proof-file" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/runtime-data-backup-proof.md"
grep -q -- "--runtime-data-backup-proof-file" "$TMP_DIR/prepared-client-tls-tunnel/server-deployment/proof-templates/runtime-data-backup-proof.md"

cat > "$TMP_DIR/client-tls-tunnel-nonlocal-connect-config.json" <<'JSON'
{
  "file_server": true,
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "external_transport_mode": "client_tls_tunnel",
  "game_bind_hosts": ["127.0.0.1"],
  "http_bind_hosts": ["127.0.0.1"],
  "jaggrab_bind_hosts": ["127.0.0.1"],
  "public_game_host": "tls.example.net",
  "client_connect_host": "tls.example.net",
  "game_port": 43594,
  "http_port": 8080,
  "jaggrab_port": 43595,
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
if scripts/preflight-external-config.py "$TMP_DIR/client-tls-tunnel-nonlocal-connect-config.json" > "$TMP_DIR/client-tls-tunnel-nonlocal-connect.out" 2>&1; then
    echo "preflight-external-config.py unexpectedly accepted non-loopback client_tls_tunnel client_connect_host." >&2
    cat "$TMP_DIR/client-tls-tunnel-nonlocal-connect.out" >&2
    exit 1
fi
grep -q "client_tls_tunnel client_connect_host must be localhost or another loopback address" "$TMP_DIR/client-tls-tunnel-nonlocal-connect.out"
if scripts/render-client-tls-tunnel-config.py \
    --config "$TMP_DIR/client-tls-tunnel-nonlocal-connect-config.json" \
    --output-dir "$TMP_DIR/client-tls-tunnel-nonlocal-connect-render" > "$TMP_DIR/client-tls-tunnel-nonlocal-connect-render.out" 2>&1; then
    echo "render-client-tls-tunnel-config.py unexpectedly accepted non-loopback client_connect_host." >&2
    cat "$TMP_DIR/client-tls-tunnel-nonlocal-connect-render.out" >&2
    exit 1
fi
grep -q "client_connect_host must be localhost or another loopback address" "$TMP_DIR/client-tls-tunnel-nonlocal-connect-render.out"

cat > "$TMP_DIR/client-tls-tunnel-control-host-config.json" <<'JSON'
{
  "file_server": true,
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "external_transport_mode": "client_tls_tunnel",
  "game_bind_hosts": ["127.0.0.1"],
  "http_bind_hosts": ["127.0.0.1"],
  "jaggrab_bind_hosts": ["127.0.0.1"],
  "public_game_host": "tls.example.net\nconnect = attacker.example.net:43594",
  "game_port": 43594,
  "http_port": 8080,
  "jaggrab_port": 43595,
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
if scripts/render-client-tls-tunnel-config.py \
    --config "$TMP_DIR/client-tls-tunnel-control-host-config.json" \
    --output-dir "$TMP_DIR/client-tls-tunnel-control-host" > "$TMP_DIR/client-tls-tunnel-control-host.out" 2>&1; then
    echo "render-client-tls-tunnel-config.py unexpectedly accepted a control character in public_game_host." >&2
    cat "$TMP_DIR/client-tls-tunnel-control-host.out" >&2
    exit 1
fi
grep -q "public_game_host must be a single-line value without control characters" "$TMP_DIR/client-tls-tunnel-control-host.out"

if CLIENT_SERVER_HOST="tls.example.net" \
    CLIENT_SECURE_TRANSPORT="client_tls_tunnel" \
    CLIENT_DIST_DIR="$TMP_DIR/client-tls-tunnel-bad-manual-client" \
    CLIENT_ARCHIVE_PATH="$TMP_DIR/client-tls-tunnel-bad-manual-client.zip" \
    SKIP_BUILD=1 \
    scripts/package-client.sh > "$TMP_DIR/client-tls-tunnel-bad-manual-package.out" 2>&1; then
    echo "package-client.sh unexpectedly accepted non-loopback client_tls_tunnel server.host." >&2
    cat "$TMP_DIR/client-tls-tunnel-bad-manual-package.out" >&2
    exit 1
fi
grep -q "Refusing to package client_tls_tunnel with non-loopback server.host" "$TMP_DIR/client-tls-tunnel-bad-manual-package.out"

cat > "$TMP_DIR/wildcard-bind-config.json" <<'JSON'
{
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "wildcard_bind_confirmed": true,
  "external_transport_mode": "tailscale",
  "game_bind_hosts": ["0.0.0.0"],
  "http_bind_hosts": ["0.0.0.0"],
  "jaggrab_bind_hosts": ["0.0.0.0"],
  "public_game_host": "example-tailnet-host",
  "game_port": 43594,
  "http_port": 8080,
  "jaggrab_port": 43595,
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
cat > "$TMP_DIR/wildcard-bind-unconfirmed-config.json" <<'JSON'
{
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "external_transport_mode": "tailscale",
  "game_bind_hosts": ["0.0.0.0"],
  "public_game_host": "example-tailnet-host",
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
if scripts/preflight-external-config.py "$TMP_DIR/wildcard-bind-unconfirmed-config.json" --allow-wildcard-bind > "$TMP_DIR/wildcard-bind-unconfirmed.out" 2>&1; then
    echo "preflight-external-config.py unexpectedly accepted a wildcard bind without wildcard_bind_confirmed=true." >&2
    cat "$TMP_DIR/wildcard-bind-unconfirmed.out" >&2
    exit 1
fi
grep -q "wildcard game bind host requires wildcard_bind_confirmed=true" "$TMP_DIR/wildcard-bind-unconfirmed.out"

if CLIENT_SERVER_CONFIG="$TMP_DIR/wildcard-bind-config.json" \
    CLIENT_DIST_DIR="$TMP_DIR/wildcard-client-no-ack" \
    CLIENT_ARCHIVE_PATH="$TMP_DIR/wildcard-client-no-ack.zip" \
    SKIP_BUILD=1 \
    scripts/package-client.sh > "$TMP_DIR/wildcard-client-no-ack.out" 2>&1; then
    echo "package-client.sh unexpectedly accepted a wildcard bind without CLIENT_ALLOW_WILDCARD_BIND=1." >&2
    cat "$TMP_DIR/wildcard-client-no-ack.out" >&2
    exit 1
fi
grep -q "wildcard game bind host requires --allow-wildcard-bind" "$TMP_DIR/wildcard-client-no-ack.out"

cat > "$TMP_DIR/bad-external-config.json" <<'JSON'
{
  "external_players_enabled": true,
  "require_secure_external_transport": false,
  "secure_external_transport_confirmed": false,
  "external_transport_mode": "plain_public_tcp",
  "game_bind_hosts": ["127.0.0.1"],
  "public_game_host": "localhost",
  "account_auth_enabled": false
}
JSON
if CLIENT_SERVER_CONFIG="$TMP_DIR/bad-external-config.json" \
    CLIENT_DIST_DIR="$TMP_DIR/bad-client" \
    CLIENT_ARCHIVE_PATH="$TMP_DIR/bad-client.zip" \
    SKIP_BUILD=1 \
    scripts/package-client.sh > "$TMP_DIR/bad-client-package.out" 2>&1; then
    echo "package-client.sh unexpectedly accepted an unsafe external config." >&2
    cat "$TMP_DIR/bad-client-package.out" >&2
    exit 1
fi

if CLIENT_DIST_DIR="$TMP_DIR/insecure-env-client" \
    CLIENT_ARCHIVE_PATH="$TMP_DIR/insecure-env-client.zip" \
    SKIP_BUILD=1 \
    CLIENT_SERVER_HOST=example-tailnet-host \
    CLIENT_SERVER_PORT=43594 \
    scripts/package-client.sh > "$TMP_DIR/insecure-env-client.out" 2>&1; then
    echo "package-client.sh unexpectedly accepted a non-local env-targeted client without secure transport metadata." >&2
    cat "$TMP_DIR/insecure-env-client.out" >&2
    exit 1
fi
grep -q "without external transport metadata" "$TMP_DIR/insecure-env-client.out"
grep -q "Set CLIENT_SECURE_TRANSPORT to direct_tcp, tailscale, wireguard, vpn, or client_tls_tunnel" "$TMP_DIR/insecure-env-client.out"
if ! grep -q "or use CLIENT_SERVER_CONFIG with a preflighted external-player config" "$TMP_DIR/insecure-env-client.out"; then
    echo "package-client.sh no longer points non-local clients at config-backed packaging." >&2
    cat "$TMP_DIR/insecure-env-client.out" >&2
    exit 1
fi

if CLIENT_DIST_DIR="$TMP_DIR/insecure-override-client" \
    CLIENT_ARCHIVE_PATH="$TMP_DIR/insecure-override-client.zip" \
    SKIP_BUILD=1 \
    CLIENT_ALLOW_INSECURE_EXTERNAL=1 \
    CLIENT_SERVER_HOST=example-tailnet-host \
    CLIENT_SERVER_PORT=43594 \
    scripts/package-client.sh > "$TMP_DIR/insecure-override-client.out" 2>&1; then
    echo "package-client.sh unexpectedly accepted CLIENT_ALLOW_INSECURE_EXTERNAL for a non-local client." >&2
    cat "$TMP_DIR/insecure-override-client.out" >&2
    exit 1
fi
grep -q "without external transport metadata" "$TMP_DIR/insecure-override-client.out"
grep -q "Set CLIENT_SECURE_TRANSPORT to direct_tcp, tailscale, wireguard, vpn, or client_tls_tunnel" "$TMP_DIR/insecure-override-client.out"

if CLIENT_DIST_DIR="$TMP_DIR/wildcard-host-client" \
    CLIENT_ARCHIVE_PATH="$TMP_DIR/wildcard-host-client.zip" \
    SKIP_BUILD=1 \
    CLIENT_SERVER_HOST=0.0.0.0 \
    CLIENT_SECURE_TRANSPORT=tailscale \
    scripts/package-client.sh > "$TMP_DIR/wildcard-host-client.out" 2>&1; then
    echo "package-client.sh unexpectedly accepted a wildcard client server host." >&2
    cat "$TMP_DIR/wildcard-host-client.out" >&2
    exit 1
fi
grep -q "wildcard server.host" "$TMP_DIR/wildcard-host-client.out"

if CLIENT_DIST_DIR="$TMP_DIR/bad-transport-client" \
    CLIENT_ARCHIVE_PATH="$TMP_DIR/bad-transport-client.zip" \
    SKIP_BUILD=1 \
    CLIENT_SERVER_HOST=example-tailnet-host \
    CLIENT_SECURE_TRANSPORT=plain_public_tcp \
    scripts/package-client.sh > "$TMP_DIR/bad-transport-client.out" 2>&1; then
    echo "package-client.sh unexpectedly accepted an unsupported secure.transport value." >&2
    cat "$TMP_DIR/bad-transport-client.out" >&2
    exit 1
fi
grep -q "unsupported secure.transport" "$TMP_DIR/bad-transport-client.out"

if CLIENT_DIST_DIR="$TMP_DIR/control-character-env-client" \
    CLIENT_ARCHIVE_PATH="$TMP_DIR/control-character-env-client.zip" \
    SKIP_BUILD=1 \
    CLIENT_SERVER_HOST=$'example-tailnet-host\nserver.port=1' \
    CLIENT_SECURE_TRANSPORT=tailscale \
    scripts/package-client.sh > "$TMP_DIR/control-character-env-client.out" 2>&1; then
    echo "package-client.sh unexpectedly accepted a control character in CLIENT_SERVER_HOST." >&2
    cat "$TMP_DIR/control-character-env-client.out" >&2
    exit 1
fi
grep -q "client server.host must be a single-line value without control characters" "$TMP_DIR/control-character-env-client.out"

mkdir -p "$TMP_DIR/package-output-target"
ln -s "$TMP_DIR/package-output-target" "$TMP_DIR/package-output-link"
if CLIENT_DIST_DIR="$TMP_DIR/package-output-link" \
    CLIENT_ARCHIVE_PATH="$TMP_DIR/symlink-dist-client.zip" \
    SKIP_BUILD=1 \
    CLIENT_SERVER_HOST=localhost \
    scripts/package-client.sh > "$TMP_DIR/symlink-dist-client.out" 2>&1; then
    echo "package-client.sh unexpectedly accepted a symlinked client distribution directory." >&2
    cat "$TMP_DIR/symlink-dist-client.out" >&2
    exit 1
fi
grep -q "refusing to write client distribution directory through symlink path" "$TMP_DIR/symlink-dist-client.out"

touch "$TMP_DIR/archive-target.zip"
ln -s "$TMP_DIR/archive-target.zip" "$TMP_DIR/archive-link.zip"
if CLIENT_DIST_DIR="$TMP_DIR/symlink-archive-client" \
    CLIENT_ARCHIVE_PATH="$TMP_DIR/archive-link.zip" \
    SKIP_BUILD=1 \
    CLIENT_SERVER_HOST=localhost \
    scripts/package-client.sh > "$TMP_DIR/symlink-archive-client.out" 2>&1; then
    echo "package-client.sh unexpectedly accepted a symlinked client archive path." >&2
    cat "$TMP_DIR/symlink-archive-client.out" >&2
    exit 1
fi
grep -q "refusing to write client archive through symlink path" "$TMP_DIR/symlink-archive-client.out"

mkdir -p "$TMP_DIR/package-parent-target"
ln -s "$TMP_DIR/package-parent-target" "$TMP_DIR/package-parent-link"
if CLIENT_DIST_DIR="$TMP_DIR/package-parent-link/client" \
    CLIENT_ARCHIVE_PATH="$TMP_DIR/package-parent-client.zip" \
    SKIP_BUILD=1 \
    CLIENT_SERVER_HOST=localhost \
    scripts/package-client.sh > "$TMP_DIR/symlink-parent-client.out" 2>&1; then
    echo "package-client.sh unexpectedly accepted a symlinked client distribution parent directory." >&2
    cat "$TMP_DIR/symlink-parent-client.out" >&2
    exit 1
fi
grep -q "refusing to write client distribution directory through symlinked parent directory" "$TMP_DIR/symlink-parent-client.out"

CLIENT_DIST_DIR="$TMP_DIR/2006scape-client" \
CLIENT_ARCHIVE_PATH="$TMP_DIR/2006scape-client.zip" \
SKIP_BUILD=1 \
CLIENT_SERVER_HOST=example-tailnet-host \
CLIENT_SERVER_PORT=43594 \
CLIENT_HTTP_PORT=8080 \
CLIENT_JAGGRAB_PORT=43595 \
CLIENT_WORLD=1 \
CLIENT_CHECK_CRC=false \
CLIENT_SINGLE_ONDEMAND=true \
CLIENT_SCALE=1 \
CLIENT_SHOW_NAVBAR=true \
CLIENT_SECURE_TRANSPORT=tailscale \
    scripts/package-client.sh

test -f "$TMP_DIR/2006scape-client/2006scape-client.jar"
test -f "$TMP_DIR/2006scape-client/client.properties"
test -f "$TMP_DIR/2006scape-client/MANIFEST.txt"
test -f "$TMP_DIR/2006scape-client/SHA256SUMS"
test -x "$TMP_DIR/2006scape-client/Check-Setup.command"
test -x "$TMP_DIR/2006scape-client/Run-2006Scape.command"
test -x "$TMP_DIR/2006scape-client/check-setup-macos-linux.sh"
test -f "$TMP_DIR/2006scape-client/check-setup-windows.bat"
test -x "$TMP_DIR/2006scape-client/run-macos-linux.sh"
test -f "$TMP_DIR/2006scape-client/run-windows.bat"
test -f "$TMP_DIR/2006scape-client.zip"
assert_archive_launcher_executable "$TMP_DIR/2006scape-client.zip" "2006scape-client/Check-Setup.command"
assert_archive_launcher_executable "$TMP_DIR/2006scape-client.zip" "2006scape-client/Run-2006Scape.command"
assert_archive_launcher_executable "$TMP_DIR/2006scape-client.zip" "2006scape-client/check-setup-macos-linux.sh"
assert_archive_launcher_executable "$TMP_DIR/2006scape-client.zip" "2006scape-client/run-macos-linux.sh"
assert_windows_launcher_crlf "$TMP_DIR/2006scape-client/check-setup-windows.bat"
assert_windows_launcher_crlf "$TMP_DIR/2006scape-client/run-windows.bat"
grep -q "check-setup-macos-linux.sh" "$TMP_DIR/2006scape-client/Check-Setup.command"
grep -q "run-macos-linux.sh" "$TMP_DIR/2006scape-client/Run-2006Scape.command"
grep -q "Java is required to run 2006Scape" "$TMP_DIR/2006scape-client/check-setup-macos-linux.sh"
grep -q "Java is required to run 2006Scape" "$TMP_DIR/2006scape-client/check-setup-windows.bat"
grep -q "Game TCP check" "$TMP_DIR/2006scape-client/check-setup-macos-linux.sh"
grep -q "PowerShell is required for TCP checks" "$TMP_DIR/2006scape-client/check-setup-windows.bat"
grep -q "agent.bridge.url" "$TMP_DIR/2006scape-client/check-setup-macos-linux.sh"
grep -q "agent.bridge.url" "$TMP_DIR/2006scape-client/check-setup-windows.bat"
grep -q "Java is required to run 2006Scape" "$TMP_DIR/2006scape-client/run-macos-linux.sh"
grep -q "Java is required to run 2006Scape" "$TMP_DIR/2006scape-client/run-windows.bat"
grep -q -- "-no-java-warnings" "$TMP_DIR/2006scape-client/run-macos-linux.sh"
grep -q -- "-no-java-warnings" "$TMP_DIR/2006scape-client/run-windows.bat"
grep -q "Check setup:" "$TMP_DIR/2006scape-client/README.txt"
grep -q "without logging in" "$TMP_DIR/2006scape-client/README.txt"
grep -q "Install Java 8 or newer" "$TMP_DIR/2006scape-client/README.txt"
grep -q "double-click Check-Setup.command" "$TMP_DIR/2006scape-client/README.txt"
grep -q "double-click Run-2006Scape.command" "$TMP_DIR/2006scape-client/README.txt"
grep -q "suppress the legacy Parabot-focused Java-version warning" "$TMP_DIR/2006scape-client/README.txt"
grep -q "Transport setup:" "$TMP_DIR/2006scape-client/README.txt"
grep -q "Connect Tailscale before launching the client" "$TMP_DIR/2006scape-client/README.txt"
grep -q "public game host: example-tailnet-host" "$TMP_DIR/2006scape-client/README.txt"
grep -q "agent bridge URL: http://127.0.0.1:43610" "$TMP_DIR/2006scape-client/README.txt"
grep -q "operator's HTTPS /agent gateway" "$TMP_DIR/2006scape-client/README.txt"
grep -q "Use the username and password provided by the server operator" "$TMP_DIR/2006scape-client/README.txt"
grep -q "Do not use a RuneScape.com password or reuse passwords from other services" "$TMP_DIR/2006scape-client/README.txt"
grep -q "server.host=example-tailnet-host" "$TMP_DIR/2006scape-client/client.properties"
grep -q "http.port=8080" "$TMP_DIR/2006scape-client/client.properties"
grep -q "secure.transport=tailscale" "$TMP_DIR/2006scape-client/client.properties"
grep -q "agent.bridge.url=http://127.0.0.1:43610" "$TMP_DIR/2006scape-client/client.properties"
grep -q "http_port=8080" "$TMP_DIR/2006scape-client/MANIFEST.txt"
grep -q "public_game_host=example-tailnet-host" "$TMP_DIR/2006scape-client/MANIFEST.txt"
grep -q "expected_external_transport=tailscale" "$TMP_DIR/2006scape-client/MANIFEST.txt"
grep -q "agent_bridge_url=http://127.0.0.1:43610" "$TMP_DIR/2006scape-client/MANIFEST.txt"
(cd "$TMP_DIR/2006scape-client" && shasum -a 256 -c SHA256SUMS >/dev/null)

echo "Smoke-testing standalone client packaging from server config..."
CLIENT_DIST_DIR="$TMP_DIR/2006scape-client-from-config" \
CLIENT_ARCHIVE_PATH="$TMP_DIR/2006scape-client-from-config.zip" \
SKIP_BUILD=1 \
CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.External.Sample.json" \
CLIENT_CHECK_CRC=false \
CLIENT_SINGLE_ONDEMAND=true \
CLIENT_SCALE=1 \
CLIENT_SHOW_NAVBAR=true \
    scripts/package-client.sh

test -f "$TMP_DIR/2006scape-client-from-config/client.properties"
test -f "$TMP_DIR/2006scape-client-from-config/2006scape-client.jar"
test -f "$TMP_DIR/2006scape-client-from-config/MANIFEST.txt"
test -f "$TMP_DIR/2006scape-client-from-config/SHA256SUMS"
test -x "$TMP_DIR/2006scape-client-from-config/Check-Setup.command"
test -x "$TMP_DIR/2006scape-client-from-config/Run-2006Scape.command"
test -x "$TMP_DIR/2006scape-client-from-config/check-setup-macos-linux.sh"
test -f "$TMP_DIR/2006scape-client-from-config/check-setup-windows.bat"
test -x "$TMP_DIR/2006scape-client-from-config/run-macos-linux.sh"
test -f "$TMP_DIR/2006scape-client-from-config/run-windows.bat"
test -f "$TMP_DIR/2006scape-client-from-config.zip"
assert_archive_launcher_executable "$TMP_DIR/2006scape-client-from-config.zip" "2006scape-client-from-config/Check-Setup.command"
assert_archive_launcher_executable "$TMP_DIR/2006scape-client-from-config.zip" "2006scape-client-from-config/Run-2006Scape.command"
assert_archive_launcher_executable "$TMP_DIR/2006scape-client-from-config.zip" "2006scape-client-from-config/check-setup-macos-linux.sh"
assert_archive_launcher_executable "$TMP_DIR/2006scape-client-from-config.zip" "2006scape-client-from-config/run-macos-linux.sh"
assert_windows_launcher_crlf "$TMP_DIR/2006scape-client-from-config/check-setup-windows.bat"
assert_windows_launcher_crlf "$TMP_DIR/2006scape-client-from-config/run-windows.bat"
grep -q "check-setup-macos-linux.sh" "$TMP_DIR/2006scape-client-from-config/Check-Setup.command"
grep -q "run-macos-linux.sh" "$TMP_DIR/2006scape-client-from-config/Run-2006Scape.command"
grep -q "Java is required to run 2006Scape" "$TMP_DIR/2006scape-client-from-config/check-setup-macos-linux.sh"
grep -q "Java is required to run 2006Scape" "$TMP_DIR/2006scape-client-from-config/check-setup-windows.bat"
grep -q "Game TCP check" "$TMP_DIR/2006scape-client-from-config/check-setup-macos-linux.sh"
grep -q "PowerShell is required for TCP checks" "$TMP_DIR/2006scape-client-from-config/check-setup-windows.bat"
grep -q "agent.bridge.url" "$TMP_DIR/2006scape-client-from-config/check-setup-macos-linux.sh"
grep -q "agent.bridge.url" "$TMP_DIR/2006scape-client-from-config/check-setup-windows.bat"
grep -q "Java is required to run 2006Scape" "$TMP_DIR/2006scape-client-from-config/run-macos-linux.sh"
grep -q "Java is required to run 2006Scape" "$TMP_DIR/2006scape-client-from-config/run-windows.bat"
grep -q -- "-no-java-warnings" "$TMP_DIR/2006scape-client-from-config/run-macos-linux.sh"
grep -q -- "-no-java-warnings" "$TMP_DIR/2006scape-client-from-config/run-windows.bat"
grep -q "Check setup:" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "without logging in" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "Install Java 8 or newer" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "double-click Check-Setup.command" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "double-click Run-2006Scape.command" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "suppress the legacy Parabot-focused Java-version warning" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "No VPN or client-side tunnel is required for this package" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "connects directly to server.example.com over plaintext TCP" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "public game host: server.example.com" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "agent bridge URL: http://127.0.0.1:43610" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "raw server-side bridge port 43610 must stay private" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "Use the username and password provided by the server operator" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "Do not use a RuneScape.com password or reuse passwords from other services" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "use a password unique to this 2006Scape server" "$TMP_DIR/2006scape-client-from-config/README.txt"
grep -q "server.host=server.example.com" "$TMP_DIR/2006scape-client-from-config/client.properties"
grep -q "server.port=43594" "$TMP_DIR/2006scape-client-from-config/client.properties"
grep -q "http.port=8080" "$TMP_DIR/2006scape-client-from-config/client.properties"
grep -q "jaggrab.port=43595" "$TMP_DIR/2006scape-client-from-config/client.properties"
grep -q "secure.transport=direct_tcp" "$TMP_DIR/2006scape-client-from-config/client.properties"
grep -q "agent.bridge.url=http://127.0.0.1:43610" "$TMP_DIR/2006scape-client-from-config/client.properties"
grep -q "source_server_config=2006Scape Server/ServerConfig.External.Sample.json" "$TMP_DIR/2006scape-client-from-config/MANIFEST.txt"
grep -Eq '^source_server_config_sha256=[0-9a-f]{64}$' "$TMP_DIR/2006scape-client-from-config/MANIFEST.txt"
grep -q "public_game_host=server.example.com" "$TMP_DIR/2006scape-client-from-config/MANIFEST.txt"
grep -q "expected_external_transport=direct_tcp" "$TMP_DIR/2006scape-client-from-config/MANIFEST.txt"
grep -q "agent_bridge_url=http://127.0.0.1:43610" "$TMP_DIR/2006scape-client-from-config/MANIFEST.txt"
grep -q "direct_tcp intentionally connects directly over plaintext TCP" "$TMP_DIR/2006scape-client-from-config/MANIFEST.txt"
(cd "$TMP_DIR/2006scape-client-from-config" && shasum -a 256 -c SHA256SUMS >/dev/null)

echo "Smoke-testing wildcard-bind packaging requires explicit acknowledgement..."
CLIENT_DIST_DIR="$TMP_DIR/wildcard-client" \
CLIENT_ARCHIVE_PATH="$TMP_DIR/wildcard-client.zip" \
SKIP_BUILD=1 \
CLIENT_ALLOW_WILDCARD_BIND=1 \
CLIENT_SERVER_CONFIG="$TMP_DIR/wildcard-bind-config.json" \
CLIENT_CHECK_CRC=false \
CLIENT_SINGLE_ONDEMAND=true \
CLIENT_SCALE=1 \
CLIENT_SHOW_NAVBAR=true \
    scripts/package-client.sh

test -f "$TMP_DIR/wildcard-client/client.properties"
grep -q "server.host=example-tailnet-host" "$TMP_DIR/wildcard-client/client.properties"
scripts/verify-external-deployment.py \
    --config "$TMP_DIR/wildcard-bind-config.json" \
    --client-dist "$TMP_DIR/wildcard-client" \
    --archive "$TMP_DIR/wildcard-client.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config \
    --allow-wildcard-bind
if scripts/render-server-deployment-files.py \
    --config "$TMP_DIR/wildcard-bind-config.json" \
    --output-dir "$TMP_DIR/wildcard-server-deployment-no-ack" > "$TMP_DIR/wildcard-server-deployment-no-ack.out" 2>&1; then
    echo "render-server-deployment-files.py unexpectedly accepted a wildcard bind without --allow-wildcard-bind." >&2
    cat "$TMP_DIR/wildcard-server-deployment-no-ack.out" >&2
    exit 1
fi
grep -q "wildcard game bind host requires --allow-wildcard-bind" "$TMP_DIR/wildcard-server-deployment-no-ack.out"
test ! -e "$TMP_DIR/wildcard-server-deployment-no-ack/2006scape-server.service"
scripts/render-server-deployment-files.py \
    --config "$TMP_DIR/wildcard-bind-config.json" \
    --output-dir "$TMP_DIR/wildcard-server-deployment" \
    --allow-wildcard-bind > "$TMP_DIR/wildcard-server-deployment.out"
grep -q "ok: rendered server deployment files" "$TMP_DIR/wildcard-server-deployment.out"
scripts/prepare-external-deployment.py \
    --config "$TMP_DIR/wildcard-bind-config.json" \
    --output-dir "$TMP_DIR/prepared-wildcard" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --skip-build \
    --allow-placeholder-network-config \
    --allow-wildcard-bind > "$TMP_DIR/prepare-wildcard.out"
grep -q "prepared external deployment artifacts" "$TMP_DIR/prepare-wildcard.out"
test -f "$TMP_DIR/prepared-wildcard/server-deployment/2006scape-server.service"

echo "Verifying external deployment artifacts against the tracked sample config..."
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" > "$TMP_DIR/sample-placeholder-network-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted tracked sample network placeholders without an explicit sample flag." >&2
    cat "$TMP_DIR/sample-placeholder-network-verify.out" >&2
    exit 1
fi
grep -q "still contains a placeholder network value" "$TMP_DIR/sample-placeholder-network-verify.out"

scripts/render-server-deployment-files.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --output-dir "$TMP_DIR/sample-server-deployment" > "$TMP_DIR/sample-server-deployment.out"
grep -q "ok: rendered server deployment files" "$TMP_DIR/sample-server-deployment.out"
test -f "$TMP_DIR/sample-server-deployment/proof-templates/desktop-client-proof.md"
test -f "$TMP_DIR/sample-server-deployment/proof-templates/runtime-data-backup-proof.md"
test -f "$TMP_DIR/sample-server-deployment/proof-templates/deployment-proof-manifest.json"
grep -q "direct_tcp mode: exposes plaintext game/cache listeners directly" "$TMP_DIR/sample-server-deployment/firewall-ufw-example.sh"
grep -q "run sudo ufw allow 43594/tcp comment '2006Scape direct TCP game'" "$TMP_DIR/sample-server-deployment/firewall-ufw-example.sh"
grep -q "sudo install -d -o 2006scape -g 2006scape -m 0700 '/opt/2006scape/2006Scape Server/data/accounts'" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "scripts/backup-runtime-data.py --data-dir '/opt/2006scape/2006Scape Server/data' --output-dir /var/backups/2006scape" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "owner-only archive/proof files" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "rejects symlinked proof notes" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "Desktop client proof must include an \`evidence\` path to a real non-symlink screenshot/log file" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "scripts/write-desktop-client-proof.py" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "backup archive sha256" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "## Live Chat Proof" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "proof-templates/deployment-proof-manifest.json" "$TMP_DIR/sample-server-deployment/README.md"
grep -q -- "--proof-manifest" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "scripts/check-deployment-proof-manifest.py deployment-proof-manifest.json --config ServerConfig.json --secrets '/opt/2006scape/2006Scape Server/data/secrets.json' --require-full-proof --check-files --check-env" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "validates desktop proof evidence and runtime-backup archive/checksum details" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "Final-gate manifests must keep \`require_full_proof:true\`" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "Relative proof-note paths in the manifest are resolved from the manifest file's directory" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "scripts/package-deployment-proof.py" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "live_reject_login_expected_statuses" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "accepted rejection status codes" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "agent_chat_player_delivery" "$TMP_DIR/sample-server-deployment/README.md"
grep -q -- "--agent-chat-delivery-log-text" "$TMP_DIR/sample-server-deployment/README.md"
grep -q "live_login_password_env" "$TMP_DIR/sample-server-deployment/proof-templates/deployment-proof-manifest.json"
grep -q "live_reject_login_expected_statuses" "$TMP_DIR/sample-server-deployment/proof-templates/deployment-proof-manifest.json"
grep -q "usually 3,4" "$TMP_DIR/sample-server-deployment/proof-templates/deployment-proof-manifest.json"
grep -q "agent_chat_delivery_log_text" "$TMP_DIR/sample-server-deployment/proof-templates/deployment-proof-manifest.json"
grep -q '"require_full_proof": true' "$TMP_DIR/sample-server-deployment/proof-templates/deployment-proof-manifest.json"
grep -q "SCREENSHOT_PATH_OR_LOG_PATH" "$TMP_DIR/sample-server-deployment/proof-templates/desktop-client-proof.md"
grep -q "scripts/write-desktop-client-proof.py" "$TMP_DIR/sample-server-deployment/proof-templates/desktop-client-proof.md"
grep -q "scripts/backup-runtime-data.py" "$TMP_DIR/sample-server-deployment/proof-templates/runtime-data-backup-proof.md"
grep -q "BACKUP_ARCHIVE_SHA256" "$TMP_DIR/sample-server-deployment/proof-templates/runtime-data-backup-proof.md"
grep -q "runtime: not started, stopped, or restarted" "$TMP_DIR/sample-server-deployment/proof-templates/runtime-data-backup-proof.md"
grep -q "readiness argument: --runtime-data-backup-proof-file" "$TMP_DIR/sample-server-deployment/proof-templates/runtime-data-backup-proof.md"
if scripts/render-server-deployment-files.py \
    --config "$TMP_DIR/file-server-disabled-overlap-config.json" \
    --output-dir "$TMP_DIR/bad-firewall-interface-deployment" \
    --tailscale-interface "tailscale0;touch-bad" > "$TMP_DIR/bad-firewall-interface.out" 2>&1; then
    echo "render-server-deployment-files.py unexpectedly accepted an unsafe interface name." >&2
    cat "$TMP_DIR/bad-firewall-interface.out" >&2
    exit 1
fi
grep -q "must be a simple interface name" "$TMP_DIR/bad-firewall-interface.out"
test ! -e "$TMP_DIR/bad-firewall-interface-deployment/firewall-ufw-example.sh"
if scripts/render-server-deployment-files.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --output-dir "$TMP_DIR/bad-service-user-deployment" \
    --service-user "2006scape;root" > "$TMP_DIR/bad-service-user.out" 2>&1; then
    echo "render-server-deployment-files.py unexpectedly accepted an unsafe service user." >&2
    cat "$TMP_DIR/bad-service-user.out" >&2
    exit 1
fi
grep -q "must be a simple service user/group name" "$TMP_DIR/bad-service-user.out"
test ! -e "$TMP_DIR/bad-service-user-deployment/2006scape-server.service"
if scripts/render-server-deployment-files.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --output-dir "$TMP_DIR/root-service-user-deployment" \
    --service-user root > "$TMP_DIR/root-service-user.out" 2>&1; then
    echo "render-server-deployment-files.py unexpectedly accepted root as the service user." >&2
    cat "$TMP_DIR/root-service-user.out" >&2
    exit 1
fi
grep -q "must not be root" "$TMP_DIR/root-service-user.out"
test ! -e "$TMP_DIR/root-service-user-deployment/2006scape-server.service"
if scripts/render-server-deployment-files.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --output-dir "$TMP_DIR/bad-install-root-deployment" \
    --install-root "/opt/2006scape bad" > "$TMP_DIR/bad-install-root.out" 2>&1; then
    echo "render-server-deployment-files.py unexpectedly accepted an unsafe install root." >&2
    cat "$TMP_DIR/bad-install-root.out" >&2
    exit 1
fi
grep -q "must be an absolute path with simple characters" "$TMP_DIR/bad-install-root.out"
test ! -e "$TMP_DIR/bad-install-root-deployment/2006scape-server.service"
cat > "$TMP_DIR/bad-render-config.json" <<'JSON'
{
  "external_players_enabled": true,
  "require_secure_external_transport": true,
  "secure_external_transport_confirmed": true,
  "external_transport_mode": "private_network",
  "public_game_host": "example-tailnet-host",
  "game_bind_hosts": ["100.64.0.10"],
  "account_auth_enabled": true,
  "account_auth_auto_create": false,
  "account_auth_legacy_fallback": false,
  "account_auth_pbkdf2_iterations": 120000
}
JSON
if scripts/render-server-deployment-files.py \
    --config "$TMP_DIR/bad-render-config.json" \
    --output-dir "$TMP_DIR/bad-render-config-deployment" > "$TMP_DIR/bad-render-config.out" 2>&1; then
    echo "render-server-deployment-files.py unexpectedly accepted a config that preflight rejects." >&2
    cat "$TMP_DIR/bad-render-config.out" >&2
    exit 1
fi
grep -q "server deployment config preflight failed" "$TMP_DIR/bad-render-config.out"
grep -q "external_transport_mode must be one of" "$TMP_DIR/bad-render-config.out"
test ! -e "$TMP_DIR/bad-render-config-deployment/2006scape-server.service"
scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --server-deployment-dir "$TMP_DIR/sample-server-deployment" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config

echo "Smoke-testing deployment verifier rejects mismatched source config hashes..."
cp "2006Scape Server/ServerConfig.External.Sample.json" "$TMP_DIR/source-config-hash-mismatch.json"
python3 - "$TMP_DIR/source-config-hash-mismatch.json" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
PY
if scripts/verify-external-deployment.py \
    --config "$TMP_DIR/source-config-hash-mismatch.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --archive "$TMP_DIR/2006scape-client-from-config.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/source-config-hash-mismatch-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a package built from different config bytes." >&2
    cat "$TMP_DIR/source-config-hash-mismatch-verify.out" >&2
    exit 1
fi
grep -q "manifest source_server_config_sha256 mismatch" "$TMP_DIR/source-config-hash-mismatch-verify.out"

echo "Smoke-testing deployment readiness report generation..."
AGENT_CHAT_LOG_TMP="$TMP_DIR/agent-chat-log"
mkdir -p "$AGENT_CHAT_LOG_TMP/2026-06-12"
cat > "$AGENT_CHAT_LOG_TMP/2026-06-12/agent-chat.jsonl" <<'JSON'
{"schemaVersion":1,"event":"agent_chat_message","id":41,"createdAt":1781300000000,"timestampMs":1781300000000,"fromType":"discord","fromName":"VerifierUser","fromProfile":"MrFlame","fromBot":false,"discordMessageId":"123456789012345678","toType":"agent","toName":"MrFlame","channel":"agent","text":"network-auth-chat-log-proof-marker","deliveredTo":[],"undeliveredTo":[]}
{"schemaVersion":1,"event":"agent_chat_player_delivery","id":42,"createdAt":1781300000100,"timestampMs":1781300000100,"fromType":"agent","fromName":"MrFlame","fromProfile":"MrFlame","toType":"player","toName":"MrGem","channel":"agent","text":"network-auth-player-delivery-proof-marker","deliveredTo":["MrGem"],"undeliveredTo":[]}
JSON
CHAT_PROOF_MANIFEST="$TMP_DIR/chat-proof-manifest.json"
cat > "$CHAT_PROOF_MANIFEST" <<'EOF'
{
  "_notes": "chat proof helper smoke",
  "desktop_client_proof_file": "desktop-client-proof.md",
  "runtime_data_backup_proof_file": "runtime-data-backup-proof.md"
}
EOF
cat > "$TMP_DIR/desktop-client-proof-evidence.log" <<'EOF'
2026-06-12T12:34:56Z local throwaway and tunnel throwaway desktop Java clients both online together.
EOF
cat > "$TMP_DIR/desktop-proof-manifest.json" <<'EOF'
{
  "_notes": "desktop proof helper smoke",
  "desktop_client_proof_file": "PATH_TO_DESKTOP_CLIENT_PROOF.md",
  "runtime_data_backup_proof_file": "runtime-data-backup-proof.md"
}
EOF
scripts/write-desktop-client-proof.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --same-host-client "local throwaway account" \
    --external-client "tunnel throwaway account" \
    --transport tailscale \
    --public-host "example-tailnet-host" \
    --evidence "$TMP_DIR/desktop-client-proof-evidence.log" \
    --output "$TMP_DIR/desktop-client-proof.md" \
    --proof-manifest "$TMP_DIR/desktop-proof-manifest.json" > "$TMP_DIR/desktop-client-proof.out"
grep -q "runtime: not started, stopped, or restarted" "$TMP_DIR/desktop-client-proof.out"
grep -q "proof manifest: $TMP_DIR/desktop-proof-manifest.json" "$TMP_DIR/desktop-client-proof.out"
grep -q "manifest desktop_client_proof_file: desktop-client-proof.md" "$TMP_DIR/desktop-client-proof.out"
grep -q "readiness argument: --desktop-client-proof-file" "$TMP_DIR/desktop-client-proof.md"
grep -q "same-host/local Java client: local throwaway account connected through 127.0.0.1" "$TMP_DIR/desktop-client-proof.md"
grep -q "external Java client: tunnel throwaway account connected through tailscale to example-tailnet-host" "$TMP_DIR/desktop-client-proof.md"
grep -q "evidence: " "$TMP_DIR/desktop-client-proof.md"
python3 - "$TMP_DIR/desktop-proof-manifest.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["desktop_client_proof_file"] == "desktop-client-proof.md", data
assert data["runtime_data_backup_proof_file"] == "runtime-data-backup-proof.md", data
assert data["_notes"] == "desktop proof helper smoke", data
PY
DESKTOP_PROOF_DEFAULT_OUT="$TMP_DIR/desktop-proof-default-output"
scripts/write-desktop-client-proof.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --same-host-client "local throwaway account" \
    --external-client "tunnel throwaway account" \
    --transport tailscale \
    --public-host "example-tailnet-host" \
    --evidence "$TMP_DIR/desktop-client-proof-evidence.log" \
    --output "$DESKTOP_PROOF_DEFAULT_OUT/desktop-client-proof.md" \
    --json > "$TMP_DIR/desktop-client-proof-json.out"
grep -q '"runtimeTouched": false' "$TMP_DIR/desktop-client-proof-json.out"
test -f "$DESKTOP_PROOF_DEFAULT_OUT/desktop-client-proof.md"
DESKTOP_PROOF_REGISTRY_OUT="$TMP_DIR/desktop-proof-registry-output"
python3 agent-navigation/tools/script_registry.py run desktop_client_proof -- \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --same-host-client "local throwaway account" \
    --external-client "tunnel throwaway account" \
    --transport tailscale \
    --public-host "example-tailnet-host" \
    --evidence "$TMP_DIR/desktop-client-proof-evidence.log" \
    --output "$DESKTOP_PROOF_REGISTRY_OUT/desktop-client-proof.md" > "$TMP_DIR/desktop-client-proof-registry.out"
grep -q "runtime: not started, stopped, or restarted" "$TMP_DIR/desktop-client-proof-registry.out"
test -f "$DESKTOP_PROOF_REGISTRY_OUT/desktop-client-proof.md"
ln -s "$TMP_DIR/desktop-client-proof-evidence.log" "$TMP_DIR/desktop-client-proof-evidence-helper-link.log"
if scripts/write-desktop-client-proof.py \
    --same-host-client "local throwaway account" \
    --external-client "tunnel throwaway account" \
    --transport tailscale \
    --public-host "example-tailnet-host" \
    --evidence "$TMP_DIR/desktop-client-proof-evidence-helper-link.log" \
    --output "$TMP_DIR/desktop-client-proof-symlink-evidence.md" > "$TMP_DIR/desktop-client-proof-symlink-evidence.out" 2>&1; then
    echo "write-desktop-client-proof.py unexpectedly accepted symlinked evidence." >&2
    exit 1
fi
grep -q "desktop client proof evidence must not be a symlink" "$TMP_DIR/desktop-client-proof-symlink-evidence.out"
if scripts/write-desktop-client-proof.py \
    --same-host-client "local throwaway account" \
    --external-client "tunnel throwaway account" \
    --transport tailscale \
    --public-host "example-tailnet-host" \
    --evidence "$TMP_DIR/missing-desktop-client-proof-evidence.log" \
    --output "$TMP_DIR/desktop-client-proof-missing-evidence.md" > "$TMP_DIR/desktop-client-proof-missing-evidence.out" 2>&1; then
    echo "write-desktop-client-proof.py unexpectedly accepted missing evidence." >&2
    exit 1
fi
grep -q "desktop client proof evidence is missing or not a file" "$TMP_DIR/desktop-client-proof-missing-evidence.out"
mkdir -p "$TMP_DIR/desktop-proof-output-target"
ln -s "$TMP_DIR/desktop-proof-output-target" "$TMP_DIR/desktop-proof-output-link"
if scripts/write-desktop-client-proof.py \
    --same-host-client "local throwaway account" \
    --external-client "tunnel throwaway account" \
    --transport tailscale \
    --public-host "example-tailnet-host" \
    --evidence "$TMP_DIR/desktop-client-proof-evidence.log" \
    --output "$TMP_DIR/desktop-proof-output-link/proof.md" > "$TMP_DIR/desktop-client-proof-symlink-output.out" 2>&1; then
    echo "write-desktop-client-proof.py unexpectedly accepted a symlinked proof output directory." >&2
    exit 1
fi
grep -q "refusing to write proof through symlinked parent directory" "$TMP_DIR/desktop-client-proof-symlink-output.out"
ln -s "$TMP_DIR/desktop-proof-manifest.json" "$TMP_DIR/desktop-proof-manifest-link.json"
if scripts/write-desktop-client-proof.py \
    --same-host-client "local throwaway account" \
    --external-client "tunnel throwaway account" \
    --transport tailscale \
    --public-host "example-tailnet-host" \
    --evidence "$TMP_DIR/desktop-client-proof-evidence.log" \
    --output "$TMP_DIR/desktop-client-proof-symlink-manifest.md" \
    --proof-manifest "$TMP_DIR/desktop-proof-manifest-link.json" > "$TMP_DIR/desktop-client-proof-symlink-manifest.out" 2>&1; then
    echo "write-desktop-client-proof.py unexpectedly accepted a symlinked proof manifest." >&2
    exit 1
fi
grep -q "refusing to write proof manifest through symlink path" "$TMP_DIR/desktop-client-proof-symlink-manifest.out"
RUNTIME_DATA_TMP="$TMP_DIR/runtime-data-source"
RUNTIME_BACKUP_ARCHIVE="$TMP_DIR/runtime-data-backup/2006scape-runtime-data-test.tgz"
mkdir -p "$RUNTIME_DATA_TMP/characters" "$RUNTIME_DATA_TMP/accounts" "$TMP_DIR/runtime-data-backup"
cat > "$RUNTIME_DATA_TMP/characters/mrflame.txt" <<'EOF'
sample character save
EOF
cat > "$RUNTIME_DATA_TMP/accounts/external-test.json" <<'EOF'
{"username":"external-test"}
EOF
cat > "$RUNTIME_DATA_TMP/secrets.json" <<'EOF'
{"discord":{"agents":[]}}
EOF
test -x scripts/backup-runtime-data.py
scripts/backup-runtime-data.py \
    --data-dir "$RUNTIME_DATA_TMP" \
    --archive "$RUNTIME_BACKUP_ARCHIVE" \
    --proof-file "$TMP_DIR/runtime-data-backup-proof.md" > "$TMP_DIR/runtime-data-backup.out"
grep -q "runtime: not started, stopped, or restarted" "$TMP_DIR/runtime-data-backup.out"
test -f "$RUNTIME_BACKUP_ARCHIVE"
test -f "$TMP_DIR/runtime-data-backup-proof.md"
tar -tzf "$RUNTIME_BACKUP_ARCHIVE" | grep -q '^characters/mrflame.txt$'
tar -tzf "$RUNTIME_BACKUP_ARCHIVE" | grep -q '^accounts/external-test.json$'
tar -tzf "$RUNTIME_BACKUP_ARCHIVE" | grep -q '^secrets.json$'
grep -q "readiness argument: --runtime-data-backup-proof-file" "$TMP_DIR/runtime-data-backup-proof.md"
grep -q "backup archive sha256:" "$TMP_DIR/runtime-data-backup-proof.md"
grep -q "runtime: not started, stopped, or restarted" "$TMP_DIR/runtime-data-backup-proof.md"
python3 - "$RUNTIME_BACKUP_ARCHIVE" "$TMP_DIR/runtime-data-backup-proof.md" <<'PY'
import os
import stat
import sys
from pathlib import Path

if os.name == "posix":
    for filename in sys.argv[1:]:
        mode = stat.S_IMODE(Path(filename).stat().st_mode)
        if mode != 0o600:
            raise SystemExit("{} should be owner-only 0600, got {:03o}".format(filename, mode))
PY
cat > "$TMP_DIR/runtime-data-proof-manifest.json" <<'EOF'
{
  "live": true,
  "runtime_data_backup_proof_file": "PATH_TO_RUNTIME_DATA_BACKUP_PROOF.md",
  "live_login_username": "ExternalTest"
}
EOF
scripts/backup-runtime-data.py \
    --data-dir "$RUNTIME_DATA_TMP" \
    --archive "$TMP_DIR/runtime-data-backup-manifest.tgz" \
    --proof-file "$TMP_DIR/runtime-data-backup-proof-manifest.md" \
    --proof-manifest "$TMP_DIR/runtime-data-proof-manifest.json" > "$TMP_DIR/runtime-data-backup-manifest.out"
grep -q "proof manifest: $TMP_DIR/runtime-data-proof-manifest.json" "$TMP_DIR/runtime-data-backup-manifest.out"
grep -q "manifest runtime_data_backup_proof_file: runtime-data-backup-proof-manifest.md" "$TMP_DIR/runtime-data-backup-manifest.out"
python3 - "$TMP_DIR/runtime-data-proof-manifest.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["runtime_data_backup_proof_file"] == "runtime-data-backup-proof-manifest.md", data
assert data["live"] is True, data
assert data["live_login_username"] == "ExternalTest", data
PY
ln -s "$TMP_DIR/runtime-data-proof-manifest.json" "$TMP_DIR/runtime-data-proof-manifest-link.json"
if scripts/backup-runtime-data.py \
    --data-dir "$RUNTIME_DATA_TMP" \
    --archive "$TMP_DIR/runtime-data-backup-symlink-manifest.tgz" \
    --proof-file "$TMP_DIR/runtime-data-backup-symlink-manifest.md" \
    --proof-manifest "$TMP_DIR/runtime-data-proof-manifest-link.json" > "$TMP_DIR/runtime-data-backup-symlink-manifest.out" 2>&1; then
    echo "backup-runtime-data.py unexpectedly accepted a symlinked proof manifest path." >&2
    exit 1
fi
grep -q "refusing to write proof manifest through symlink path" "$TMP_DIR/runtime-data-backup-symlink-manifest.out"
test ! -e "$TMP_DIR/runtime-data-backup-symlink-manifest.tgz"
test ! -e "$TMP_DIR/runtime-data-backup-symlink-manifest.md"
RUNTIME_BACKUP_DEFAULT_OUT="$TMP_DIR/runtime-data-default-output"
scripts/backup-runtime-data.py \
    --data-dir "$RUNTIME_DATA_TMP" \
    --output-dir "$RUNTIME_BACKUP_DEFAULT_OUT" > "$TMP_DIR/runtime-data-backup-default.out"
grep -q "runtime: not started, stopped, or restarted" "$TMP_DIR/runtime-data-backup-default.out"
test "$(find "$RUNTIME_BACKUP_DEFAULT_OUT" -name '2006scape-runtime-data-*.tgz' | wc -l | tr -d ' ')" = "1"
test "$(find "$RUNTIME_BACKUP_DEFAULT_OUT" -name 'runtime-data-backup-proof-*.md' | wc -l | tr -d ' ')" = "1"
RUNTIME_BACKUP_REGISTRY_OUT="$TMP_DIR/runtime-data-registry-output"
python3 agent-navigation/tools/script_registry.py run runtime_data_backup -- \
    --data-dir "$RUNTIME_DATA_TMP" \
    --output-dir "$RUNTIME_BACKUP_REGISTRY_OUT" > "$TMP_DIR/runtime-data-backup-registry.out"
grep -q "runtime: not started, stopped, or restarted" "$TMP_DIR/runtime-data-backup-registry.out"
test "$(find "$RUNTIME_BACKUP_REGISTRY_OUT" -name '2006scape-runtime-data-*.tgz' | wc -l | tr -d ' ')" = "1"
test "$(find "$RUNTIME_BACKUP_REGISTRY_OUT" -name 'runtime-data-backup-proof-*.md' | wc -l | tr -d ' ')" = "1"
ln -s "$RUNTIME_DATA_TMP" "$TMP_DIR/runtime-data-source-link"
if scripts/backup-runtime-data.py \
    --data-dir "$TMP_DIR/runtime-data-source-link" \
    --archive "$TMP_DIR/runtime-data-backup-symlink-data.tgz" \
    --proof-file "$TMP_DIR/runtime-data-backup-symlink-data.md" > "$TMP_DIR/runtime-data-backup-symlink-data.out" 2>&1; then
    echo "backup-runtime-data.py unexpectedly accepted a symlinked data directory." >&2
    exit 1
fi
grep -q "refusing to back up symlinked data directory" "$TMP_DIR/runtime-data-backup-symlink-data.out"
RUNTIME_DATA_CHILD_LINK="$TMP_DIR/runtime-data-child-link"
mkdir -p "$RUNTIME_DATA_CHILD_LINK/characters" "$RUNTIME_DATA_CHILD_LINK/accounts"
cat > "$RUNTIME_DATA_CHILD_LINK/characters/mrflame.txt" <<'EOF'
sample character save
EOF
cat > "$RUNTIME_DATA_CHILD_LINK/accounts/external-test.json" <<'EOF'
{"username":"external-test"}
EOF
ln -s "$RUNTIME_DATA_TMP/secrets.json" "$RUNTIME_DATA_CHILD_LINK/secrets.json"
if scripts/backup-runtime-data.py \
    --data-dir "$RUNTIME_DATA_CHILD_LINK" \
    --archive "$TMP_DIR/runtime-data-backup-symlink-child.tgz" \
    --proof-file "$TMP_DIR/runtime-data-backup-symlink-child.md" > "$TMP_DIR/runtime-data-backup-symlink-child.out" 2>&1; then
    echo "backup-runtime-data.py unexpectedly accepted a symlinked secrets path." >&2
    exit 1
fi
grep -q "refusing to back up symlinked Discord secrets path" "$TMP_DIR/runtime-data-backup-symlink-child.out"
RUNTIME_DATA_NESTED_LINK="$TMP_DIR/runtime-data-nested-link"
mkdir -p "$RUNTIME_DATA_NESTED_LINK/characters" "$RUNTIME_DATA_NESTED_LINK/accounts"
cat > "$RUNTIME_DATA_NESTED_LINK/accounts/external-test.json" <<'EOF'
{"username":"external-test"}
EOF
cat > "$RUNTIME_DATA_NESTED_LINK/secrets.json" <<'EOF'
{"discord":{"agents":[]}}
EOF
ln -s "$RUNTIME_DATA_TMP/characters/mrflame.txt" "$RUNTIME_DATA_NESTED_LINK/characters/mrflame-link.txt"
if scripts/backup-runtime-data.py \
    --data-dir "$RUNTIME_DATA_NESTED_LINK" \
    --archive "$TMP_DIR/runtime-data-backup-symlink-nested.tgz" \
    --proof-file "$TMP_DIR/runtime-data-backup-symlink-nested.md" > "$TMP_DIR/runtime-data-backup-symlink-nested.out" 2>&1; then
    echo "backup-runtime-data.py unexpectedly accepted a nested symlinked runtime-data path." >&2
    exit 1
fi
grep -q "refusing to include symlinked runtime-data path" "$TMP_DIR/runtime-data-backup-symlink-nested.out"
ln -s "$TMP_DIR/runtime-data-backup-symlink-target.tgz" "$TMP_DIR/runtime-data-backup-symlink-archive.tgz"
if scripts/backup-runtime-data.py \
    --data-dir "$RUNTIME_DATA_TMP" \
    --archive "$TMP_DIR/runtime-data-backup-symlink-archive.tgz" \
    --proof-file "$TMP_DIR/runtime-data-backup-symlink-archive.md" > "$TMP_DIR/runtime-data-backup-symlink-archive.out" 2>&1; then
    echo "backup-runtime-data.py unexpectedly accepted a symlinked archive output path." >&2
    exit 1
fi
grep -q "refusing to write archive through symlink path" "$TMP_DIR/runtime-data-backup-symlink-archive.out"
ln -s "$TMP_DIR/runtime-data-backup-symlink-target.md" "$TMP_DIR/runtime-data-backup-symlink-proof.md"
if scripts/backup-runtime-data.py \
    --data-dir "$RUNTIME_DATA_TMP" \
    --archive "$TMP_DIR/runtime-data-backup-symlink-proof.tgz" \
    --proof-file "$TMP_DIR/runtime-data-backup-symlink-proof.md" > "$TMP_DIR/runtime-data-backup-symlink-proof.out" 2>&1; then
    echo "backup-runtime-data.py unexpectedly accepted a symlinked proof output path." >&2
    exit 1
fi
grep -q "refusing to write proof through symlink path" "$TMP_DIR/runtime-data-backup-symlink-proof.out"
mkdir -p "$TMP_DIR/runtime-data-output-target"
ln -s "$TMP_DIR/runtime-data-output-target" "$TMP_DIR/runtime-data-output-link"
if scripts/backup-runtime-data.py \
    --data-dir "$RUNTIME_DATA_TMP" \
    --output-dir "$TMP_DIR/runtime-data-output-link" > "$TMP_DIR/runtime-data-backup-symlink-output-dir.out" 2>&1; then
    echo "backup-runtime-data.py unexpectedly accepted a symlinked output directory." >&2
    exit 1
fi
grep -q "refusing to write archive through symlinked parent directory" "$TMP_DIR/runtime-data-backup-symlink-output-dir.out"
mkdir -p "$TMP_DIR/runtime-data-archive-parent-target"
ln -s "$TMP_DIR/runtime-data-archive-parent-target" "$TMP_DIR/runtime-data-archive-parent-link"
if scripts/backup-runtime-data.py \
    --data-dir "$RUNTIME_DATA_TMP" \
    --archive "$TMP_DIR/runtime-data-archive-parent-link/archive.tgz" \
    --proof-file "$TMP_DIR/runtime-data-backup-parent-archive-proof.md" > "$TMP_DIR/runtime-data-backup-symlink-archive-parent.out" 2>&1; then
    echo "backup-runtime-data.py unexpectedly accepted a symlinked archive parent directory." >&2
    exit 1
fi
grep -q "refusing to write archive through symlinked parent directory" "$TMP_DIR/runtime-data-backup-symlink-archive-parent.out"
mkdir -p "$TMP_DIR/runtime-data-proof-parent-target"
ln -s "$TMP_DIR/runtime-data-proof-parent-target" "$TMP_DIR/runtime-data-proof-parent-link"
if scripts/backup-runtime-data.py \
    --data-dir "$RUNTIME_DATA_TMP" \
    --archive "$TMP_DIR/runtime-data-backup-parent-proof.tgz" \
    --proof-file "$TMP_DIR/runtime-data-proof-parent-link/proof.md" > "$TMP_DIR/runtime-data-backup-symlink-proof-parent.out" 2>&1; then
    echo "backup-runtime-data.py unexpectedly accepted a symlinked proof parent directory." >&2
    exit 1
fi
grep -q "refusing to write proof through symlinked parent directory" "$TMP_DIR/runtime-data-backup-symlink-proof-parent.out"
scripts/verify-agent-chat-log.py \
    --log-root "$AGENT_CHAT_LOG_TMP" \
    --text-contains "network-auth-chat-log-proof-marker" \
    --from-type discord \
    --from-bot false \
    --discord-message-id 123456789012345678 \
    --channel agent \
    --proof-manifest "$CHAT_PROOF_MANIFEST" > "$TMP_DIR/agent-chat-log-proof.out"
grep -q "ok: matched 1 agent chat log entry" "$TMP_DIR/agent-chat-log-proof.out"
grep -q "event=agent_chat_message" "$TMP_DIR/agent-chat-log-proof.out"
grep -q "manifest proof kind: discord-ingress" "$TMP_DIR/agent-chat-log-proof.out"
scripts/verify-agent-chat-log.py \
    --log-root "$AGENT_CHAT_LOG_TMP" \
    --event agent_chat_player_delivery \
    --text-contains "network-auth-player-delivery-proof-marker" \
    --from-type agent \
    --to-type player \
    --to-name MrGem \
    --channel agent \
    --delivered-to MrGem \
    --no-undelivered \
    --proof-manifest "$CHAT_PROOF_MANIFEST" > "$TMP_DIR/agent-chat-delivery-log-proof.out"
grep -q "ok: matched 1 agent chat log entry" "$TMP_DIR/agent-chat-delivery-log-proof.out"
grep -q "event=agent_chat_player_delivery" "$TMP_DIR/agent-chat-delivery-log-proof.out"
grep -q "manifest proof kind: agent-player-delivery" "$TMP_DIR/agent-chat-delivery-log-proof.out"
if scripts/verify-agent-chat-log.py \
    --log-root "$AGENT_CHAT_LOG_TMP" \
    --event agent_chat_player_delivery \
    --text-contains "network-auth-player-delivery-proof-marker" \
    --delivered-to MrMissing \
    --channel agent > "$TMP_DIR/agent-chat-delivery-log-wrong-recipient.out" 2>&1; then
    echo "verify-agent-chat-log accepted the wrong deliveredTo filter." >&2
    exit 1
fi
grep -q "no matching agent chat log entry found" "$TMP_DIR/agent-chat-delivery-log-wrong-recipient.out"
if scripts/verify-agent-chat-log.py \
    --log-root "$AGENT_CHAT_LOG_TMP" \
    --text-contains "network-auth-chat-log-proof-marker" \
    --from-type discord \
    --from-bot true \
    --channel agent > "$TMP_DIR/agent-chat-log-proof-bot.out" 2>&1; then
    echo "verify-agent-chat-log accepted the wrong fromBot filter." >&2
    exit 1
fi
grep -q "no matching agent chat log entry found" "$TMP_DIR/agent-chat-log-proof-bot.out"
if scripts/verify-agent-chat-log.py \
    --log-root "$AGENT_CHAT_LOG_TMP" \
    --text-contains "network-auth-chat-log-proof-marker" \
    --from-type discord \
    --from-bot false \
    --discord-message-id 999999999999999999 \
    --channel agent > "$TMP_DIR/agent-chat-log-proof-message-id.out" 2>&1; then
    echo "verify-agent-chat-log accepted the wrong Discord message id filter." >&2
    exit 1
fi
grep -q "no matching agent chat log entry found" "$TMP_DIR/agent-chat-log-proof-message-id.out"
scripts/verify-agent-chat-log.py \
    --log-root "$AGENT_CHAT_LOG_TMP" \
    --text-contains "network-auth-blocked-routing-marker" \
    --from-type discord \
    --from-bot false \
    --channel agent \
    --expect-absent \
    --proof-manifest "$CHAT_PROOF_MANIFEST" > "$TMP_DIR/agent-chat-log-absent-proof.out"
grep -q "ok: no matching agent chat log entries found" "$TMP_DIR/agent-chat-log-absent-proof.out"
grep -q "manifest proof kind: blocked-routing" "$TMP_DIR/agent-chat-log-absent-proof.out"
python3 - "$CHAT_PROOF_MANIFEST" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["_notes"] == "chat proof helper smoke", data
assert data["desktop_client_proof_file"] == "desktop-client-proof.md", data
assert data["runtime_data_backup_proof_file"] == "runtime-data-backup-proof.md", data
assert data["agent_chat_log_text"] == "network-auth-chat-log-proof-marker", data
assert data["agent_chat_log_from_type"] == "discord", data
assert data["agent_chat_log_from_bot"] == "false", data
assert data["agent_chat_log_discord_message_id"] == "123456789012345678", data
assert data["agent_chat_log_channel"] == "agent", data
assert data["agent_chat_delivery_log_text"] == "network-auth-player-delivery-proof-marker", data
assert data["agent_chat_delivery_log_to_name"] == "MrGem", data
assert data["agent_chat_delivery_log_channel"] == "agent", data
assert data["agent_chat_blocked_log_text"] == "network-auth-blocked-routing-marker", data
assert data["agent_chat_blocked_log_channel"] == "agent", data
PY
ln -s "$CHAT_PROOF_MANIFEST" "$TMP_DIR/chat-proof-manifest-link.json"
if scripts/verify-agent-chat-log.py \
    --log-root "$AGENT_CHAT_LOG_TMP" \
    --text-contains "network-auth-chat-log-proof-marker" \
    --from-type discord \
    --from-bot false \
    --channel agent \
    --proof-manifest "$TMP_DIR/chat-proof-manifest-link.json" > "$TMP_DIR/agent-chat-log-symlink-manifest.out" 2>&1; then
    echo "verify-agent-chat-log.py unexpectedly accepted a symlinked proof manifest." >&2
    exit 1
fi
grep -q "refusing to write proof manifest through symlink path" "$TMP_DIR/agent-chat-log-symlink-manifest.out"
cat > "$TMP_DIR/discord-proof-manifest.json" <<'EOF'
{
  "_notes": "discord proof helper smoke",
  "agent_chat_log_text": "network-auth-chat-log-proof-marker"
}
EOF
python3 - "$TMP_DIR/discord-proof-manifest.json" <<'PY'
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

manifest = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location(
    "verify_discord_channel_message",
    Path("scripts/verify-discord-channel-message.py"),
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
args = SimpleNamespace(
    proof_manifest=str(manifest),
    allow_human_author=False,
    text_contains="network-auth-discord-mirror-marker",
    agent=["MrFlame"],
    limit=50,
    after_id="",
    require_all=False,
)
updates = module.update_proof_manifest(args, [{
    "matched": 1,
    "agent": "MrFlame",
    "latestMessageId": "987654321098765432",
}])
assert updates["discord_channel_message_text"] == "network-auth-discord-mirror-marker", updates
assert updates["discord_channel_message_agent"] == ["MrFlame"], updates
data = json.loads(manifest.read_text(encoding="utf-8"))
assert data["_notes"] == "discord proof helper smoke", data
assert data["agent_chat_log_text"] == "network-auth-chat-log-proof-marker", data
assert data["discord_channel_message_text"] == "network-auth-discord-mirror-marker", data
assert data["discord_channel_message_agent"] == ["MrFlame"], data
args.allow_human_author = True
try:
    module.update_proof_manifest(args, [])
except SystemExit as exc:
    assert "--allow-human-author" in str(exc), exc
else:
    raise AssertionError("weak human-author Discord mirror proof was recorded")
PY
if scripts/verify-agent-chat-log.py \
    --log-root "$AGENT_CHAT_LOG_TMP" \
    --text-contains "network-auth-chat-log-proof-marker" \
    --from-type discord \
    --from-bot false \
    --channel agent \
    --expect-absent > "$TMP_DIR/agent-chat-log-absent-fail.out" 2>&1; then
    echo "verify-agent-chat-log accepted an existing marker with --expect-absent." >&2
    exit 1
fi
grep -q "expected none" "$TMP_DIR/agent-chat-log-absent-fail.out"
python3 - <<'PY'
import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location(
    "deployment_readiness_report",
    Path("scripts/deployment-readiness-report.py"),
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
args = SimpleNamespace(
    live=True,
    tls_sni_host="",
    live_login_username="ExternalTest",
    live_login_password_env="EXTERNAL_PASSWORD",
    live_login_hold_seconds=5.0,
    live_local_login_username="LocalTest",
    live_local_login_password_env="LOCAL_PASSWORD",
    live_local_host="127.0.0.1",
    live_local_port=43594,
    live_reject_login_username="RejectTest",
    live_reject_login_password_env="REJECT_PASSWORD",
    live_reject_login_expected_statuses="3,4",
    desktop_client_proof_file="",
    runtime_data_backup_proof_file="",
    live_discord=False,
    agent_chat_log_root=str(module.DEFAULT_AGENT_CHAT_LOG_ROOT),
    agent_chat_log_text="",
    agent_chat_blocked_log_text="",
    agent_chat_delivery_log_text="",
    discord_channel_message_text="",
    discord_channel_message_agent=[],
    discord_channel_message_limit=50,
    discord_channel_message_require_all=False,
)
updates = module.proof_manifest_updates_from_args(args)
assert updates["live"] is True, updates
assert updates["live_login_username"] == "ExternalTest", updates
assert updates["live_login_password_env"] == "EXTERNAL_PASSWORD", updates
assert updates["live_login_hold_seconds"] == 5.0, updates
assert updates["live_local_login_username"] == "LocalTest", updates
assert updates["live_local_login_password_env"] == "LOCAL_PASSWORD", updates
assert updates["live_local_host"] == "127.0.0.1", updates
assert updates["live_local_port"] == 43594, updates
assert updates["live_reject_login_expected_statuses"] == "3,4", updates
assert "agent_chat_log_root" not in updates, updates
assert "discord_channel_message_limit" not in updates, updates
assert "discord_channel_message_allow_human_author" not in updates, updates
PY
cat > "$TMP_DIR/readiness-update-proof-manifest.json" <<'EOF'
{
  "_notes": "readiness update smoke"
}
EOF
scripts/deployment-readiness-report.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --archive "$TMP_DIR/2006scape-client-from-config.zip" \
    --server-deployment-dir "$TMP_DIR/sample-server-deployment" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config \
    --agent-chat-log-root "$AGENT_CHAT_LOG_TMP" \
    --agent-chat-log-text "network-auth-chat-log-proof-marker" \
    --agent-chat-log-from-type discord \
    --agent-chat-log-from-bot false \
    --agent-chat-log-discord-message-id 123456789012345678 \
    --agent-chat-log-channel agent \
    --agent-chat-blocked-log-text "network-auth-blocked-routing-marker" \
    --agent-chat-blocked-log-channel agent \
    --agent-chat-delivery-log-text "network-auth-player-delivery-proof-marker" \
    --agent-chat-delivery-log-to-name MrGem \
    --agent-chat-delivery-log-channel agent \
    --desktop-client-proof-file "$TMP_DIR/desktop-client-proof.md" \
    --runtime-data-backup-proof-file "$TMP_DIR/runtime-data-backup-proof.md" \
    --output "$TMP_DIR/deployment-readiness-report.md" \
    --json-output "$TMP_DIR/deployment-readiness-report.json" \
    --update-proof-manifest "$TMP_DIR/readiness-update-proof-manifest.json" > "$TMP_DIR/deployment-readiness-report.out"
grep -q "report: $TMP_DIR/deployment-readiness-report.md" "$TMP_DIR/deployment-readiness-report.out"
grep -q "jsonReport: $TMP_DIR/deployment-readiness-report.json" "$TMP_DIR/deployment-readiness-report.out"
grep -q "proofManifestUpdated: $TMP_DIR/readiness-update-proof-manifest.json" "$TMP_DIR/deployment-readiness-report.out"
grep -q "proofManifestFields: " "$TMP_DIR/deployment-readiness-report.out"
grep -q "runtime_data_backup_proof_file" "$TMP_DIR/deployment-readiness-report.out"
grep -q 'status: `PASS`' "$TMP_DIR/deployment-readiness-report.md"
grep -q 'deploymentProofStatus: `STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF`' "$TMP_DIR/deployment-readiness-report.md"
grep -q 'liveChecksRequested: `no`' "$TMP_DIR/deployment-readiness-report.md"
grep -q "| Public reachability and bridge non-exposure | MISSING |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "| Fail-closed login cases | MISSING |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "| Discord-to-server chat ingestion | LOG_PROOF_REQUESTED |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "| Agent-to-player chat delivery | DELIVERY_LOG_PROOF_REQUESTED |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "| Blocked Discord routing filters | ABSENCE_PROOF_REQUESTED |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "| Server-to-Discord chat mirroring | MANUAL_WHEN_DISCORD_ENABLED |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "| agent chat log proof | PASS | 0 |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "| agent chat player delivery proof | PASS | 0 |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "| blocked Discord routing proof | PASS | 0 |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "| Desktop client coexistence | MANUAL_PROOF_RECORDED |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "| Runtime data backup before remote replacement/restart | MANUAL_PROOF_RECORDED |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "| desktop client coexistence proof | PASS | 0 |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "| runtime data backup proof | PASS | 0 |" "$TMP_DIR/deployment-readiness-report.md"
grep -q "desktop client proof evidence verified" "$TMP_DIR/deployment-readiness-report.md"
grep -q "backup archive sha256 verified" "$TMP_DIR/deployment-readiness-report.md"
grep -q "archive entries present: accounts, characters, secrets.json" "$TMP_DIR/deployment-readiness-report.md"
grep -q "runtime data backup proof permissions owner-only" "$TMP_DIR/deployment-readiness-report.md"
grep -q "runtime: not started, stopped, or restarted" "$TMP_DIR/deployment-readiness-report.md"
grep -q "serverDeploymentDir: " "$TMP_DIR/deployment-readiness-report.md"
test "$(grep -c "^- clientTlsTunnelDir:" "$TMP_DIR/deployment-readiness-report.md")" = "1"
grep -q "| deployment verification | PASS | 0 |" "$TMP_DIR/deployment-readiness-report.md"
grep -q -- "--agent-chat-log-from-type discord --agent-chat-log-from-bot false" "$TMP_DIR/deployment-readiness-report.md"
grep -q "Remaining Live Proof" "$TMP_DIR/deployment-readiness-report.md"
grep -q "Before a real external deployment is called ready, still prove:" "$TMP_DIR/deployment-readiness-report.md"
grep -q "public reachability plus bridge non-exposure" "$TMP_DIR/deployment-readiness-report.md"
python3 - "$TMP_DIR/deployment-readiness-report.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["schemaVersion"] == 1, data
assert data["status"] == "PASS", data
assert data["deploymentProofStatus"] == "STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF", data
assert data["liveChecksRequested"] is False, data
assert data["liveDiscordRequested"] is False, data
coverage = {item["requirement"]: item for item in data["proofCoverage"]}
assert coverage["Runtime data backup before remote replacement/restart"]["status"] == "MANUAL_PROOF_RECORDED", coverage
assert coverage["Agent-to-player chat delivery"]["status"] == "DELIVERY_LOG_PROOF_REQUESTED", coverage
checks = {check["label"]: check for check in data["checks"]}
assert checks["runtime data backup proof"]["status"] == "PASS", checks
assert "backup archive sha256 verified" in checks["runtime data backup proof"]["output"], checks["runtime data backup proof"]
assert "runtime: not started, stopped, or restarted" in checks["runtime data backup proof"]["output"], checks["runtime data backup proof"]
assert "--from-type discord" in checks["agent chat log proof"]["command"], checks["agent chat log proof"]
assert "--from-bot false" in checks["agent chat log proof"]["command"], checks["agent chat log proof"]
assert data["commandSummary"][-1]["label"] == "deployment verification", data["commandSummary"]
assert any("public reachability plus bridge non-exposure" in item for item in data["remainingLiveProof"]), data["remainingLiveProof"]
assert data["markdownReport"].endswith("deployment-readiness-report.md"), data
PY
python3 - "$TMP_DIR/readiness-update-proof-manifest.json" "$TMP_DIR/desktop-client-proof.md" "$TMP_DIR/runtime-data-backup-proof.md" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["_notes"] == "readiness update smoke", data
assert data["desktop_client_proof_file"] == sys.argv[2], data
assert data["runtime_data_backup_proof_file"] == sys.argv[3], data
assert data["agent_chat_log_text"] == "network-auth-chat-log-proof-marker", data
assert data["agent_chat_log_from_type"] == "discord", data
assert data["agent_chat_log_from_bot"] == "false", data
assert data["agent_chat_log_discord_message_id"] == "123456789012345678", data
assert data["agent_chat_delivery_log_text"] == "network-auth-player-delivery-proof-marker", data
assert data["agent_chat_delivery_log_to_name"] == "MrGem", data
assert data["agent_chat_blocked_log_text"] == "network-auth-blocked-routing-marker", data
assert "live" not in data, data
assert "discord_channel_message_allow_human_author" not in data, data
PY
scripts/deployment-readiness-status.py \
    --readiness-json "$TMP_DIR/deployment-readiness-report.json" > "$TMP_DIR/deployment-readiness-status.out"
grep -q "deploymentProofStatus: STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF" "$TMP_DIR/deployment-readiness-status.out"
grep -q "externallyReady: no" "$TMP_DIR/deployment-readiness-status.out"
grep -q "remainingLiveProofCount:" "$TMP_DIR/deployment-readiness-status.out"
grep -q "public reachability plus bridge non-exposure" "$TMP_DIR/deployment-readiness-status.out"
if grep -q "nextCommands:" "$TMP_DIR/deployment-readiness-status.out"; then
    echo "deployment-readiness-status.py printed next commands without --show-next-commands." >&2
    exit 1
fi
scripts/deployment-readiness-status.py \
    --readiness-json "$TMP_DIR/deployment-readiness-report.json" \
    --show-next-commands > "$TMP_DIR/deployment-readiness-status-next.out"
grep -q "nextCommands:" "$TMP_DIR/deployment-readiness-status-next.out"
grep -q "Record live network/auth proof" "$TMP_DIR/deployment-readiness-status-next.out"
grep -q -- "--live-login-username EXTERNAL_TEST" "$TMP_DIR/deployment-readiness-status-next.out"
grep -q -- "--live-reject-login-expected-statuses 3,4" "$TMP_DIR/deployment-readiness-status-next.out"
grep -q -- "--update-proof-manifest" "$TMP_DIR/deployment-readiness-status-next.out"
grep -q -- "--proof-manifest" "$TMP_DIR/deployment-readiness-status-next.out"
grep -q "scripts/check-deployment-proof-manifest.py" "$TMP_DIR/deployment-readiness-status-next.out"
if grep -q "Back up deployed runtime data" "$TMP_DIR/deployment-readiness-status-next.out"; then
    echo "deployment-readiness-status.py suggested a runtime data backup after proof was already recorded." >&2
    exit 1
fi
scripts/deployment-readiness-status.py \
    --readiness-json "$TMP_DIR/deployment-readiness-report.json" \
    --json > "$TMP_DIR/deployment-readiness-status.json"
python3 - "$TMP_DIR/deployment-readiness-status.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["externallyReady"] is False, data
assert data["deploymentProofStatus"] == "STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF", data
assert data["remainingLiveProofCount"] > 0, data
assert "nextCommands" not in data, data
PY
scripts/deployment-readiness-status.py \
    --readiness-json "$TMP_DIR/deployment-readiness-report.json" \
    --show-next-commands \
    --json > "$TMP_DIR/deployment-readiness-status-next.json"
python3 - "$TMP_DIR/deployment-readiness-status-next.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
commands = data.get("nextCommands")
assert isinstance(commands, list) and commands, data
labels = {command["label"] for command in commands}
assert "Record live network/auth proof" in labels, labels
assert "Check final proof manifest and rerun final readiness" in labels, labels
assert "Back up deployed runtime data" not in labels, labels
live_commands = [command["command"] for command in commands if command["label"] == "Record live network/auth proof"]
assert live_commands, commands
live_command = live_commands[0]
assert "--live-login-username EXTERNAL_TEST" in live_command, live_command
assert "--update-proof-manifest" in live_command, live_command
assert "mkdir -p" in live_command, live_command
assert "test -f" in live_command, live_command
assert "|| cp" in live_command, live_command
assert live_command.index("mkdir -p") < live_command.index("test -f"), live_command
assert live_command.index("test -f") < live_command.index("scripts/deployment-readiness-report.py"), live_command
final_commands = [command["command"] for command in commands if command["label"] == "Check final proof manifest and rerun final readiness"]
assert final_commands, commands
final_command = final_commands[0]
assert "--accounts-dir" in final_command, final_command
assert "--secrets" in final_command, final_command
assert "scripts/check-deployment-proof-manifest.py" in final_command, final_command
assert "mkdir -p" in final_command, final_command
assert "test -f" in final_command, final_command
assert "|| cp" in final_command, final_command
assert final_command.index("mkdir -p") < final_command.index("test -f"), final_command
assert final_command.index("test -f") < final_command.index("scripts/check-deployment-proof-manifest.py"), final_command
PY
python3 - "$TMP_DIR/deployment-readiness-report.json" "$TMP_DIR/deployment-readiness-report-missing-backup.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for item in data["proofCoverage"]:
    if item["requirement"] == "Runtime data backup before remote replacement/restart":
        item["status"] = "MISSING"
        item.pop("evidence", None)
remaining = data.setdefault("remainingLiveProof", [])
if not any("runtime data backup" in item for item in remaining):
    remaining.append("runtime data backup proof")
Path(sys.argv[2]).write_text(json.dumps(data), encoding="utf-8")
PY
python3 - "$TMP_DIR/deployment-readiness-report.json" "$TMP_DIR/deployment-readiness-report-missing-desktop.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for item in data["proofCoverage"]:
    if item["requirement"] == "Desktop client coexistence":
        item["status"] = "MISSING"
        item.pop("evidence", None)
remaining = data.setdefault("remainingLiveProof", [])
if not any("desktop client" in item for item in remaining):
    remaining.append("desktop client coexistence proof")
Path(sys.argv[2]).write_text(json.dumps(data), encoding="utf-8")
PY
python3 - "$TMP_DIR/deployment-readiness-report.json" "$TMP_DIR/deployment-readiness-report-missing-chat.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for item in data["proofCoverage"]:
    if item["requirement"] == "Agent-to-player chat delivery":
        item["status"] = "MISSING"
        item.pop("evidence", None)
remaining = data.setdefault("remainingLiveProof", [])
if not any("agent/player chat" in item or "chat delivery" in item for item in remaining):
    remaining.append("agent/player chat delivery proof")
Path(sys.argv[2]).write_text(json.dumps(data), encoding="utf-8")
PY
scripts/deployment-readiness-status.py \
    --readiness-json "$TMP_DIR/deployment-readiness-report-missing-backup.json" \
    --show-next-commands \
    --json > "$TMP_DIR/deployment-readiness-status-missing-backup-next.json"
python3 - "$TMP_DIR/deployment-readiness-status-missing-backup-next.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
commands = data.get("nextCommands")
assert isinstance(commands, list) and commands, data
backup_commands = [command["command"] for command in commands if command["label"] == "Back up deployed runtime data"]
assert backup_commands, commands
backup_command = backup_commands[0]
assert "scripts/backup-runtime-data.py" in backup_command, backup_command
assert "--proof-file" in backup_command, backup_command
assert "--proof-manifest" in backup_command, backup_command
assert "dist/external-deployment/runtime-data-backup-proof.md" in backup_command, backup_command
assert "mkdir -p" in backup_command, backup_command
assert "test -f" in backup_command, backup_command
assert "|| cp" in backup_command, backup_command
assert backup_command.index("mkdir -p") < backup_command.index("test -f"), backup_command
assert backup_command.index("test -f") < backup_command.index("scripts/backup-runtime-data.py"), backup_command
PY
scripts/deployment-readiness-status.py \
    --readiness-json "$TMP_DIR/deployment-readiness-report-missing-desktop.json" \
    --show-next-commands \
    --json > "$TMP_DIR/deployment-readiness-status-missing-desktop-next.json"
python3 - "$TMP_DIR/deployment-readiness-status-missing-desktop-next.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
commands = data.get("nextCommands")
assert isinstance(commands, list) and commands, data
desktop_commands = [command["command"] for command in commands if command["label"] == "Write desktop-client coexistence proof"]
assert desktop_commands, commands
desktop_command = desktop_commands[0]
assert "--output" in desktop_command, desktop_command
assert "--proof-manifest" in desktop_command, desktop_command
assert "dist/external-deployment/desktop-client-proof.md" in desktop_command, desktop_command
assert "mkdir -p" in desktop_command, desktop_command
assert "test -f" in desktop_command, desktop_command
assert "|| cp" in desktop_command, desktop_command
assert desktop_command.index("mkdir -p") < desktop_command.index("test -f"), desktop_command
assert desktop_command.index("test -f") < desktop_command.index("scripts/write-desktop-client-proof.py"), desktop_command
PY
scripts/deployment-readiness-status.py \
    --readiness-json "$TMP_DIR/deployment-readiness-report-missing-chat.json" \
    --show-next-commands \
    --json > "$TMP_DIR/deployment-readiness-status-missing-chat-next.json"
python3 - "$TMP_DIR/deployment-readiness-status-missing-chat-next.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
commands = data.get("nextCommands")
assert isinstance(commands, list) and commands, data
chat_commands = [command["command"] for command in commands if command["label"] == "Verify direct agent/player chat delivery"]
assert chat_commands, commands
chat_command = chat_commands[0]
assert "scripts/verify-agent-chat-log.py" in chat_command, chat_command
assert "--event agent_chat_player_delivery" in chat_command, chat_command
assert "--proof-manifest" in chat_command, chat_command
assert "mkdir -p" in chat_command, chat_command
assert "test -f" in chat_command, chat_command
assert "|| cp" in chat_command, chat_command
assert chat_command.index("mkdir -p") < chat_command.index("test -f"), chat_command
assert chat_command.index("test -f") < chat_command.index("scripts/verify-agent-chat-log.py"), chat_command
PY
mkdir -p "$TMP_DIR/prepared-status"
cp "$TMP_DIR/deployment-readiness-report.json" "$TMP_DIR/prepared-status/deployment-readiness-report.json"
scripts/deployment-readiness-status.py \
    --prepared-dir "$TMP_DIR/prepared-status" \
    --show-next-commands \
    --json > "$TMP_DIR/deployment-readiness-status-prepared-next.json"
python3 - "$TMP_DIR/deployment-readiness-status-prepared-next.json" "$TMP_DIR/prepared-status/deployment-proof-manifest.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
manifest_path = sys.argv[2]
commands = data.get("nextCommands")
assert isinstance(commands, list) and commands, data
final_commands = [command["command"] for command in commands if command["label"] == "Check final proof manifest and rerun final readiness"]
assert final_commands, commands
assert manifest_path in final_commands[0], final_commands[0]
assert "mkdir -p" in final_commands[0], final_commands[0]
assert not [command["command"] for command in commands if command["label"] == "Back up deployed runtime data"], commands
PY
mkdir -p "$TMP_DIR/prepared-status-missing-desktop"
cp "$TMP_DIR/deployment-readiness-report-missing-desktop.json" "$TMP_DIR/prepared-status-missing-desktop/deployment-readiness-report.json"
scripts/deployment-readiness-status.py \
    --prepared-dir "$TMP_DIR/prepared-status-missing-desktop" \
    --show-next-commands \
    --json > "$TMP_DIR/deployment-readiness-status-prepared-missing-desktop-next.json"
python3 - "$TMP_DIR/deployment-readiness-status-prepared-missing-desktop-next.json" "$TMP_DIR/prepared-status-missing-desktop/desktop-client-proof.md" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
desktop_path = sys.argv[2]
commands = data.get("nextCommands")
assert isinstance(commands, list) and commands, data
desktop_commands = [command["command"] for command in commands if command["label"] == "Write desktop-client coexistence proof"]
assert desktop_commands, commands
assert desktop_path in desktop_commands[0], desktop_commands[0]
assert "--proof-manifest" in desktop_commands[0], desktop_commands[0]
assert str(Path(desktop_path).with_name("deployment-proof-manifest.json")) in desktop_commands[0], desktop_commands[0]
assert "dist/external-deployment/desktop-client-proof.md" not in desktop_commands[0], desktop_commands[0]
PY
mkdir -p "$TMP_DIR/prepared-status-missing-backup"
cp "$TMP_DIR/deployment-readiness-report-missing-backup.json" "$TMP_DIR/prepared-status-missing-backup/deployment-readiness-report.json"
scripts/deployment-readiness-status.py \
    --prepared-dir "$TMP_DIR/prepared-status-missing-backup" \
    --show-next-commands \
    --json > "$TMP_DIR/deployment-readiness-status-prepared-missing-backup-next.json"
python3 - "$TMP_DIR/deployment-readiness-status-prepared-missing-backup-next.json" "$TMP_DIR/prepared-status-missing-backup/deployment-proof-manifest.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
manifest_path = sys.argv[2]
commands = data.get("nextCommands")
assert isinstance(commands, list) and commands, data
backup_commands = [command["command"] for command in commands if command["label"] == "Back up deployed runtime data"]
assert backup_commands, commands
assert manifest_path in backup_commands[0], backup_commands[0]
assert str(Path(manifest_path).with_name("runtime-data-backup-proof.md")) in backup_commands[0], backup_commands[0]
assert "mkdir -p" in backup_commands[0], backup_commands[0]
PY
if scripts/deployment-readiness-status.py \
    --readiness-json "$TMP_DIR/deployment-readiness-report.json" \
    --fail-if-not-ready > "$TMP_DIR/deployment-readiness-status-fail.out" 2>&1; then
    echo "deployment-readiness-status.py accepted a partial/static report with --fail-if-not-ready." >&2
    exit 1
fi
grep -q "externallyReady: no" "$TMP_DIR/deployment-readiness-status-fail.out"
python3 - "$TMP_DIR/deployment-readiness-ready.json" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(json.dumps({
    "schemaVersion": 1,
    "status": "PASS",
    "deploymentProofStatus": "LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_PROOF_RECORDED_DISCORD_NOT_REQUESTED",
    "liveChecksRequested": True,
    "liveDiscordRequested": False,
    "markdownReport": "deployment-readiness-report.md",
    "remainingLiveProof": [],
    "proofCoverage": [
        {"requirement": "Public reachability and bridge non-exposure", "status": "RECORDED", "detail": "live proof recorded"}
    ],
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
scripts/deployment-readiness-status.py \
    --readiness-json "$TMP_DIR/deployment-readiness-ready.json" \
    --fail-if-not-ready > "$TMP_DIR/deployment-readiness-status-ready.out"
grep -q "externallyReady: yes" "$TMP_DIR/deployment-readiness-status-ready.out"
if scripts/deployment-readiness-status.py \
    --readiness-json "$TMP_DIR/deployment-readiness-ready.json" \
    --require-discord \
    --fail-if-not-ready > "$TMP_DIR/deployment-readiness-status-ready-require-discord.out" 2>&1; then
    echo "deployment-readiness-status.py accepted non-Discord final status with --require-discord." >&2
    exit 1
fi
grep -q "externallyReady: no" "$TMP_DIR/deployment-readiness-status-ready-require-discord.out"
mkdir -p "$TMP_DIR/prepared-readiness-status"
cp "$TMP_DIR/deployment-readiness-ready.json" "$TMP_DIR/prepared-readiness-status/deployment-readiness-report.json"
scripts/deployment-readiness-status.py \
    --prepared-dir "$TMP_DIR/prepared-readiness-status" > "$TMP_DIR/deployment-readiness-status-prepared.out"
grep -q "externallyReady: yes" "$TMP_DIR/deployment-readiness-status-prepared.out"
cp "$TMP_DIR/runtime-data-backup-proof.md" "$TMP_DIR/runtime-data-backup-proof-bad-sha.md"
python3 - "$TMP_DIR/runtime-data-backup-proof-bad-sha.md" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(
    r"(?m)^- backup archive sha256: [0-9a-f]{64}$",
    "- backup archive sha256: " + ("0" * 64),
    text,
    count=1,
)
path.write_text(text, encoding="utf-8")
PY
if scripts/deployment-readiness-report.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --archive "$TMP_DIR/2006scape-client-from-config.zip" \
    --server-deployment-dir "$TMP_DIR/sample-server-deployment" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config \
    --runtime-data-backup-proof-file "$TMP_DIR/runtime-data-backup-proof-bad-sha.md" \
    --output "$TMP_DIR/deployment-readiness-bad-runtime-backup-proof.md" > "$TMP_DIR/deployment-readiness-bad-runtime-backup-proof.out" 2>&1; then
    echo "deployment-readiness-report accepted runtime backup proof with a mismatched archive checksum." >&2
    exit 1
fi
grep -q "backup archive sha256 mismatch" "$TMP_DIR/deployment-readiness-bad-runtime-backup-proof.md"
ln -s "$TMP_DIR/runtime-data-backup-proof.md" "$TMP_DIR/runtime-data-backup-proof-link.md"
python3 - "$TMP_DIR/runtime-data-backup-proof-link.md" <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path("scripts/deployment-readiness-report.py")
spec = importlib.util.spec_from_file_location("deployment_readiness_report", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run_runtime_data_backup_proof_file_check(sys.argv[1])
assert result["exitCode"] == 1, result
assert "proof file must not be a symlink" in result["output"], result
PY
cp "$TMP_DIR/runtime-data-backup-proof.md" "$TMP_DIR/runtime-data-backup-proof-open.md"
chmod 0644 "$TMP_DIR/runtime-data-backup-proof-open.md"
python3 - "$TMP_DIR/runtime-data-backup-proof-open.md" <<'PY'
import importlib.util
import os
import sys
from pathlib import Path

path = Path("scripts/deployment-readiness-report.py")
spec = importlib.util.spec_from_file_location("deployment_readiness_report", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run_runtime_data_backup_proof_file_check(sys.argv[1])
if os.name == "posix":
    assert result["exitCode"] == 1, result
    assert "runtime data backup proof permissions must be owner-only" in result["output"], result
else:
    assert result["exitCode"] == 0, result
PY
cp "$TMP_DIR/runtime-data-backup-proof.md" "$TMP_DIR/runtime-data-backup-proof-missing-runtime.md"
python3 - "$TMP_DIR/runtime-data-backup-proof-missing-runtime.md" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
path.write_text("\n".join(line for line in lines if "runtime: not started, stopped, or restarted" not in line) + "\n", encoding="utf-8")
PY
python3 - "$TMP_DIR/runtime-data-backup-proof-missing-runtime.md" <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path("scripts/deployment-readiness-report.py")
spec = importlib.util.spec_from_file_location("deployment_readiness_report", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run_runtime_data_backup_proof_file_check(sys.argv[1])
assert result["exitCode"] == 1, result
assert "no runtime start/stop/restart" in result["output"], result
PY
cp "$TMP_DIR/runtime-data-backup-proof.md" "$TMP_DIR/runtime-data-backup-proof-missing-readiness-argument.md"
python3 - "$TMP_DIR/runtime-data-backup-proof-missing-readiness-argument.md" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
path.write_text("\n".join(line for line in lines if "readiness argument: --runtime-data-backup-proof-file" not in line) + "\n", encoding="utf-8")
PY
python3 - "$TMP_DIR/runtime-data-backup-proof-missing-readiness-argument.md" <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path("scripts/deployment-readiness-report.py")
spec = importlib.util.spec_from_file_location("deployment_readiness_report", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run_runtime_data_backup_proof_file_check(sys.argv[1])
assert result["exitCode"] == 1, result
assert "readiness argument" in result["output"], result
PY
if scripts/deployment-readiness-report.py \
    --config "$TMP_DIR/client-tls-tunnel-config.json" \
    --client-dist "$TMP_DIR/client-tls-tunnel-client" \
    --archive "$TMP_DIR/client-tls-tunnel-client.zip" \
    --server-deployment-dir "$TMP_DIR/client-tls-tunnel-server-deployment" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --desktop-client-proof-file "$TMP_DIR/desktop-client-proof.md" \
    --runtime-data-backup-proof-file "$TMP_DIR/runtime-data-backup-proof.md" \
    --require-full-proof \
    --output "$TMP_DIR/deployment-readiness-require-full.md" > "$TMP_DIR/deployment-readiness-require-full.out" 2>&1; then
    echo "deployment-readiness-report accepted partial/static evidence with --require-full-proof." >&2
    exit 1
fi
grep -q 'deploymentProofStatus: `STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF`' "$TMP_DIR/deployment-readiness-require-full.md"
grep -q "full proof required but deploymentProofStatus is STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF" "$TMP_DIR/deployment-readiness-require-full.out"
if scripts/deployment-readiness-report.py \
    --require-full-proof \
    --allow-placeholder-network-config \
    --output "$TMP_DIR/deployment-readiness-require-full-placeholder.md" > "$TMP_DIR/deployment-readiness-require-full-placeholder.out" 2>&1; then
    echo "deployment-readiness-report accepted source-only placeholder allowance with --require-full-proof." >&2
    exit 1
fi
grep -q "source/test-only flags" "$TMP_DIR/deployment-readiness-require-full-placeholder.out"
if scripts/prepare-external-deployment.py \
    --require-full-proof \
    --allow-placeholder-network-config \
    --output-dir "$TMP_DIR/prepare-require-full-placeholder" > "$TMP_DIR/prepare-require-full-placeholder.out" 2>&1; then
    echo "prepare-external-deployment accepted source-only placeholder allowance with --require-full-proof." >&2
    exit 1
fi
grep -q "source/test-only flags" "$TMP_DIR/prepare-require-full-placeholder.out"
if scripts/deployment-readiness-report.py \
    --agent-chat-log-text "network-auth-chat-log-proof-marker" \
    --agent-chat-log-from-type discord \
    --output "$TMP_DIR/deployment-readiness-weak-chat-proof.md" > "$TMP_DIR/deployment-readiness-weak-chat-proof.out" 2>&1; then
    echo "deployment-readiness-report accepted Discord chat proof without fromBot=false." >&2
    exit 1
fi
grep -q -- "--agent-chat-log-from-bot false" "$TMP_DIR/deployment-readiness-weak-chat-proof.out"
if scripts/deployment-readiness-report.py \
    --agent-chat-log-text "network-auth-chat-log-proof-marker" \
    --agent-chat-log-from-bot false \
    --output "$TMP_DIR/deployment-readiness-missing-discord-source.md" > "$TMP_DIR/deployment-readiness-missing-discord-source.out" 2>&1; then
    echo "deployment-readiness-report accepted chat proof without fromType=discord." >&2
    exit 1
fi
grep -q -- "--agent-chat-log-from-type discord" "$TMP_DIR/deployment-readiness-missing-discord-source.out"
if scripts/deployment-readiness-report.py \
    --discord-channel-message-text "network-auth-discord-mirror-marker" \
    --discord-channel-message-allow-human-author \
    --output "$TMP_DIR/deployment-readiness-human-mirror-proof.md" > "$TMP_DIR/deployment-readiness-human-mirror-proof.out" 2>&1; then
    echo "deployment-readiness-report accepted human-authored Discord mirror proof." >&2
    exit 1
fi
grep -q -- "requires the configured bot author" "$TMP_DIR/deployment-readiness-human-mirror-proof.out"
if scripts/prepare-external-deployment.py \
    --agent-chat-log-text "network-auth-chat-log-proof-marker" \
    --agent-chat-log-from-type discord \
    --output-dir "$TMP_DIR/prepared-weak-chat-proof" > "$TMP_DIR/prepared-weak-chat-proof.out" 2>&1; then
    echo "prepare-external-deployment accepted Discord chat proof without fromBot=false." >&2
    exit 1
fi
grep -q -- "--agent-chat-log-from-bot false" "$TMP_DIR/prepared-weak-chat-proof.out"
python3 - "$TMP_DIR" <<'PY'
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

path = Path("scripts/deployment-readiness-report.py")
spec = importlib.util.spec_from_file_location("deployment_readiness_report", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
tmp_dir = Path(sys.argv[1])
open_discord_secrets = tmp_dir / "readiness-open-discord-secrets.json"
open_discord_secrets.write_text(json.dumps({
    "agent-discord-bots": [
        {
            "agent": "MrFlame",
            "token": "test-token",
            "channelId": "555555555555555555",
            "allowBroadcast": True,
        }
    ]
}), encoding="utf-8")
filtered_discord_secrets = tmp_dir / "readiness-filtered-discord-secrets.json"
filtered_discord_secrets.write_text(json.dumps({
    "agent-discord-bots": [
        {
            "agent": "MrFlame",
            "token": "test-token",
            "channelId": "555555555555555555",
            "allowedAgents": ["MrFlame"],
            "allowedPlayers": ["MrFlame"],
            "allowBroadcast": True,
        }
    ]
}), encoding="utf-8")
discord_disabled_config = tmp_dir / "readiness-discord-disabled-config.json"
discord_disabled_config.write_text(json.dumps({
    "agent_chat_discord_enabled": False,
}), encoding="utf-8")
discord_enabled_config = tmp_dir / "readiness-discord-enabled-config.json"
discord_enabled_config.write_text(json.dumps({
    "agent_chat_discord_enabled": True,
}), encoding="utf-8")

def args(**overrides):
    values = {
        "config": str(discord_disabled_config),
        "live": False,
        "live_login_username": "",
        "live_local_login_username": "",
        "live_reject_login_username": "",
        "live_reject_login_expected_statuses": "",
        "desktop_client_proof_file": "",
        "runtime_data_backup_proof_file": "",
        "agent_chat_delivery_log_text": "",
        "agent_chat_delivery_log_to_name": "",
        "live_discord": False,
        "agent_chat_log_text": "",
        "agent_chat_blocked_log_text": "",
        "discord_channel_message_text": "",
        "secrets": str(open_discord_secrets),
    }
    values.update(overrides)
    return SimpleNamespace(**values)

assert module.deployment_proof_status(args(), True) == "STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF"
assert not module.discord_enabled_in_config(args())
assert module.discord_enabled_in_config(args(config=str(discord_enabled_config)))
misconfigured_login = args(live_login_username="external")
assert "EXTERNAL_LOGIN_PROOF" in module.missing_proof_codes(misconfigured_login)
assert "INVALID_WITHOUT_LIVE" in "\n".join(module.proof_coverage_rows(misconfigured_login))
misconfigured_local = args(live=True, live_local_login_username="local")
assert "CONCURRENT_LOCAL_LOGIN_PROOF" in module.missing_proof_codes(misconfigured_local)
assert "INVALID_WITHOUT_EXTERNAL_LOGIN" in "\n".join(module.proof_coverage_rows(misconfigured_local))
partial = module.deployment_proof_status(args(live=True), True)
assert partial.startswith("LIVE_PROOF_PARTIAL_NEEDS_"), partial
assert "EXTERNAL_LOGIN_PROOF" in partial, partial
assert "DESKTOP_CLIENT_PROOF" in partial, partial
assert "AGENT_PLAYER_CHAT_DELIVERY_PROOF" in partial, partial
unpinned_reject = module.deployment_proof_status(args(
        live=True,
        live_login_username="external",
        live_local_login_username="local",
        live_reject_login_username="reject",
        desktop_client_proof_file="desktop.md",
        runtime_data_backup_proof_file="backup.md",
        agent_chat_delivery_log_text="agent-to-player-marker",
        agent_chat_delivery_log_to_name="MrGem",
), True)
assert "FAIL_CLOSED_REJECTION_PROOF" in unpinned_reject, unpinned_reject
assert "PINNED_STATUS_MISSING" in "\n".join(module.proof_coverage_rows(args(
        live=True,
        live_reject_login_username="reject",
))), module.proof_coverage_rows(args(live=True, live_reject_login_username="reject"))
network_ready = module.deployment_proof_status(args(
        live=True,
        live_login_username="external",
        live_local_login_username="local",
        live_reject_login_username="reject",
        live_reject_login_expected_statuses="3,4",
        desktop_client_proof_file="desktop.md",
        runtime_data_backup_proof_file="backup.md",
        agent_chat_delivery_log_text="agent-to-player-marker",
        agent_chat_delivery_log_to_name="MrGem",
), True)
assert network_ready == "LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_PROOF_RECORDED_DISCORD_NOT_REQUESTED", network_ready
discord_enabled_missing = module.missing_proof_codes(args(
        config=str(discord_enabled_config),
        live=True,
        live_login_username="external",
        live_local_login_username="local",
        live_reject_login_username="reject",
        live_reject_login_expected_statuses="3,4",
        desktop_client_proof_file="desktop.md",
        runtime_data_backup_proof_file="backup.md",
        agent_chat_delivery_log_text="agent-to-player-marker",
        agent_chat_delivery_log_to_name="MrGem",
))
assert "DISCORD_BOT_CHANNEL_PROOF" in discord_enabled_missing, discord_enabled_missing
assert "DISCORD_TO_SERVER_CHAT_PROOF" in discord_enabled_missing, discord_enabled_missing
assert "SERVER_TO_DISCORD_CHAT_PROOF" in discord_enabled_missing, discord_enabled_missing
discord_enabled_status = module.deployment_proof_status(args(
        config=str(discord_enabled_config),
        live=True,
        live_login_username="external",
        live_local_login_username="local",
        live_reject_login_username="reject",
        live_reject_login_expected_statuses="3,4",
        desktop_client_proof_file="desktop.md",
        runtime_data_backup_proof_file="backup.md",
        agent_chat_delivery_log_text="agent-to-player-marker",
        agent_chat_delivery_log_to_name="MrGem",
), True)
assert "LIVE_PROOF_PARTIAL_NEEDS_DISCORD_BOT_CHANNEL_PROOF" in discord_enabled_status, discord_enabled_status
discord_enabled_rows = "\n".join(module.proof_coverage_rows(args(config=str(discord_enabled_config))))
assert "MISSING_REQUIRED_WHEN_ENABLED" in discord_enabled_rows, discord_enabled_rows
full = module.deployment_proof_status(args(
        live=True,
        live_login_username="external",
        live_local_login_username="local",
        live_reject_login_username="reject",
        live_reject_login_expected_statuses="3,4",
        desktop_client_proof_file="desktop.md",
        runtime_data_backup_proof_file="backup.md",
        agent_chat_delivery_log_text="agent-to-player-marker",
        agent_chat_delivery_log_to_name="MrGem",
        live_discord=True,
        agent_chat_log_text="discord-to-server-marker",
        discord_channel_message_text="server-to-discord-marker",
), True)
assert full == "FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED", full
full_config_enabled = module.deployment_proof_status(args(
        config=str(discord_enabled_config),
        live=True,
        live_login_username="external",
        live_local_login_username="local",
        live_reject_login_username="reject",
        live_reject_login_expected_statuses="3,4",
        desktop_client_proof_file="desktop.md",
        runtime_data_backup_proof_file="backup.md",
        agent_chat_delivery_log_text="agent-to-player-marker",
        agent_chat_delivery_log_to_name="MrGem",
        live_discord=True,
        agent_chat_log_text="discord-to-server-marker",
        discord_channel_message_text="server-to-discord-marker",
), True)
assert full_config_enabled == "FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED", full_config_enabled
assert not module.discord_routing_filters_configured(args()), "open Discord routing should not require blocked-proof"
assert module.discord_routing_filters_configured(args(secrets=str(filtered_discord_secrets)))
filtered_missing = module.missing_proof_codes(args(
        live=True,
        live_login_username="external",
        live_local_login_username="local",
        live_reject_login_username="reject",
        live_reject_login_expected_statuses="3,4",
        desktop_client_proof_file="desktop.md",
        runtime_data_backup_proof_file="backup.md",
        agent_chat_delivery_log_text="agent-to-player-marker",
        agent_chat_delivery_log_to_name="MrGem",
        live_discord=True,
        agent_chat_log_text="discord-to-server-marker",
        discord_channel_message_text="server-to-discord-marker",
        secrets=str(filtered_discord_secrets),
))
assert "BLOCKED_DISCORD_ROUTING_PROOF" in filtered_missing, filtered_missing
filtered_rows = "\n".join(module.proof_coverage_rows(args(
        live_discord=True,
        agent_chat_log_text="discord-to-server-marker",
        discord_channel_message_text="server-to-discord-marker",
        secrets=str(filtered_discord_secrets),
)))
assert "MISSING_REQUIRED_FOR_CONFIGURED_FILTERS" in filtered_rows, filtered_rows
full_filtered = module.deployment_proof_status(args(
        live=True,
        live_login_username="external",
        live_local_login_username="local",
        live_reject_login_username="reject",
        live_reject_login_expected_statuses="3,4",
        desktop_client_proof_file="desktop.md",
        runtime_data_backup_proof_file="backup.md",
        agent_chat_delivery_log_text="agent-to-player-marker",
        agent_chat_delivery_log_to_name="MrGem",
        live_discord=True,
        agent_chat_log_text="discord-to-server-marker",
        agent_chat_blocked_log_text="blocked-discord-marker",
        discord_channel_message_text="server-to-discord-marker",
        secrets=str(filtered_discord_secrets),
), True)
assert full_filtered == "FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED", full_filtered
assert module.deployment_proof_status(args(live=True), False) == "CHECKS_FAILED"
PY
python3 - "$TMP_DIR" <<'PY'
import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

path = Path("scripts/lib/deployment_proof_manifest.py")
spec = importlib.util.spec_from_file_location("deployment_proof_manifest", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

tmp_dir = Path(sys.argv[1])
manifest = tmp_dir / "deployment-proof-manifest.json"
manifest.write_text(json.dumps({
    "_notes": "ignored operator note",
    "live": True,
    "live_login_username": "ExternalTest",
    "live_login_password_env": "EXTERNAL_PASSWORD",
    "desktop_client_proof_file": "desktop-client-proof.md",
    "agent_chat_delivery_log_text": "manifest-marker",
    "agent_chat_delivery_log_to_name": "LocalTest",
    "discord_channel_message_agent": ["MrFlame", "MrGem"],
}), encoding="utf-8")

class QuietParser(argparse.ArgumentParser):
    def error(self, message):
        raise SystemExit(message)

parser = QuietParser()
args = SimpleNamespace(
    proof_manifest=str(manifest),
    live=False,
    live_login_username="",
    live_login_password_env="",
    desktop_client_proof_file="",
    agent_chat_delivery_log_text="cli-marker",
    agent_chat_delivery_log_to_name="",
    discord_channel_message_agent=[],
)
module.apply_proof_manifest(
    parser,
    args,
    ["--proof-manifest", str(manifest), "--agent-chat-delivery-log-text", "cli-marker"],
)
assert args.live is True, args
assert args.live_login_username == "ExternalTest", args
assert args.live_login_password_env == "EXTERNAL_PASSWORD", args
assert args.desktop_client_proof_file == str(tmp_dir / "desktop-client-proof.md"), args
assert args.agent_chat_delivery_log_text == "cli-marker", args
assert args.agent_chat_delivery_log_to_name == "LocalTest", args
assert args.discord_channel_message_agent == ["MrFlame", "MrGem"], args

args_override = SimpleNamespace(
    proof_manifest=str(manifest),
    desktop_client_proof_file="cli-desktop-proof.md",
)
module.apply_proof_manifest(
    parser,
    args_override,
    ["--proof-manifest", str(manifest), "--desktop-client-proof-file", "cli-desktop-proof.md"],
)
assert args_override.desktop_client_proof_file == "cli-desktop-proof.md", args_override

bad_manifest = tmp_dir / "bad-deployment-proof-manifest.json"
bad_manifest.write_text(json.dumps({"live_login_password": "not allowed"}), encoding="utf-8")
bad_args = SimpleNamespace(proof_manifest=str(bad_manifest))
try:
    module.apply_proof_manifest(parser, bad_args, ["--proof-manifest", str(bad_manifest)])
except SystemExit:
    pass
else:
    raise AssertionError("raw password-looking proof manifest key was accepted")

bad_env_manifest = tmp_dir / "bad-env-proof-manifest.json"
bad_env_manifest.write_text(json.dumps({"live_login_password_env": "not a password env var"}), encoding="utf-8")
bad_env_args = SimpleNamespace(proof_manifest=str(bad_env_manifest), live_login_password_env="")
try:
    module.apply_proof_manifest(parser, bad_env_args, ["--proof-manifest", str(bad_env_manifest)])
except SystemExit:
    pass
else:
    raise AssertionError("non-env-name live_login_password_env was accepted")

placeholder_manifest = tmp_dir / "placeholder-proof-manifest.json"
placeholder_manifest.write_text(json.dumps({
    "runtime_data_backup_proof_file": "PATH_TO_RUNTIME_DATA_BACKUP_PROOF.md",
}), encoding="utf-8")
placeholder_args = SimpleNamespace(
    proof_manifest=str(placeholder_manifest),
    runtime_data_backup_proof_file="",
)
try:
    module.apply_proof_manifest(parser, placeholder_args, ["--proof-manifest", str(placeholder_manifest)])
except SystemExit:
    pass
else:
    raise AssertionError("placeholder runtime_data_backup_proof_file was accepted")

template_manifest = tmp_dir / "deployment-proof-manifest-template.json"
template_manifest.write_text(json.dumps({
    "live": True,
    "live_login_username": "EXTERNAL_TEST_USERNAME",
    "live_login_password_env": "EXTERNAL_TEST_PASSWORD",
    "live_local_login_username": "LOCAL_TEST_USERNAME",
    "live_local_login_password_env": "LOCAL_TEST_PASSWORD",
    "runtime_data_backup_proof_file": "PATH_TO_RUNTIME_DATA_BACKUP_PROOF.md",
}), encoding="utf-8")
template_values = module.validate_proof_manifest_template(
    template_manifest,
    required_fields={
        "live",
        "live_login_username",
        "live_login_password_env",
        "live_local_login_username",
        "live_local_login_password_env",
        "runtime_data_backup_proof_file",
    },
)
assert template_values["runtime_data_backup_proof_file"] == "PATH_TO_RUNTIME_DATA_BACKUP_PROOF.md", template_values
PY
cat > "$TMP_DIR/proof-manifest-check-ok.json" <<EOF
{
  "live": true,
  "live_login_username": "ExternalTest",
  "live_login_password_env": "EXTERNAL_PASSWORD",
  "live_local_login_username": "LocalTest",
  "live_local_login_password_env": "LOCAL_PASSWORD",
  "live_reject_login_username": "RejectTest",
  "live_reject_login_password_env": "REJECT_PASSWORD",
  "live_reject_login_expected_statuses": "3,4",
  "desktop_client_proof_file": "desktop-client-proof.md",
  "runtime_data_backup_proof_file": "runtime-data-backup-proof.md",
  "agent_chat_delivery_log_text": "agent-to-player-marker",
  "agent_chat_delivery_log_to_name": "MrGem",
  "require_full_proof": true,
  "_notes": "validation fixture"
}
EOF
scripts/check-deployment-proof-manifest.py \
    "$TMP_DIR/proof-manifest-check-ok.json" \
    --require-full-proof \
    --check-files \
    --json > "$TMP_DIR/proof-manifest-check-ok.out"
grep -q '"status": "PASS"' "$TMP_DIR/proof-manifest-check-ok.out"
grep -q '"discordRequired": false' "$TMP_DIR/proof-manifest-check-ok.out"
python3 - "$TMP_DIR/proof-manifest-check-ok.json" "$TMP_DIR/proof-manifest-check-missing-final-gate.json" <<'PY'
import json
import sys

source, target = sys.argv[1:3]
data = json.load(open(source, encoding="utf-8"))
data.pop("require_full_proof")
with open(target, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
if scripts/check-deployment-proof-manifest.py \
    "$TMP_DIR/proof-manifest-check-missing-final-gate.json" \
    --require-full-proof > "$TMP_DIR/proof-manifest-check-missing-final-gate.out" 2>&1; then
    echo "check-deployment-proof-manifest.py unexpectedly accepted a final manifest without require_full_proof=true." >&2
    exit 1
fi
grep -q "final proof manifest must set require_full_proof=true" "$TMP_DIR/proof-manifest-check-missing-final-gate.out"
python3 - "$TMP_DIR/proof-manifest-check-ok.out" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
checks = {check["field"]: check for check in data["proofFileChecks"]}
assert checks["desktop_client_proof_file"]["status"] == "PASS", checks
assert checks["runtime_data_backup_proof_file"]["status"] == "PASS", checks
assert "desktop client proof evidence verified" in checks["desktop_client_proof_file"]["output"], checks
assert "backup archive sha256 verified" in checks["runtime_data_backup_proof_file"]["output"], checks
PY
scripts/package-deployment-proof.py \
    --readiness-report "$TMP_DIR/deployment-readiness-report.md" \
    --readiness-json "$TMP_DIR/deployment-readiness-report.json" \
    --proof-manifest "$TMP_DIR/proof-manifest-check-ok.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --server-deployment-dir "$TMP_DIR/sample-server-deployment" \
    --archive "$TMP_DIR/deployment-proof-bundle.tgz" \
    --json > "$TMP_DIR/deployment-proof-bundle.out"
grep -q '"runtimeTouched": false' "$TMP_DIR/deployment-proof-bundle.out"
test -f "$TMP_DIR/deployment-proof-bundle.tgz"
tar -tzf "$TMP_DIR/deployment-proof-bundle.tgz" | sort > "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^README.md$' "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^bundle-metadata.json$' "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^readiness/deployment-readiness-report.md$' "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^readiness/deployment-readiness-report.json$' "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^proof/deployment-proof-manifest.json$' "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^proof/01-desktop-client-proof.md$' "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^proof/02-runtime-data-backup-proof.md$' "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^client/MANIFEST.txt$' "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^client/SHA256SUMS$' "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^client/README.txt$' "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^client/client.properties$' "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^server-deployment/README.md$' "$TMP_DIR/deployment-proof-bundle.entries"
grep -q '^server-deployment/ServerConfig.json$' "$TMP_DIR/deployment-proof-bundle.entries"
if grep -q '2006scape-runtime-data-test.tgz' "$TMP_DIR/deployment-proof-bundle.entries"; then
    echo "package-deployment-proof.py bundled a runtime-data backup archive." >&2
    exit 1
fi
tar -xOf "$TMP_DIR/deployment-proof-bundle.tgz" bundle-metadata.json > "$TMP_DIR/deployment-proof-bundle-metadata.json"
python3 - "$TMP_DIR/deployment-proof-bundle-metadata.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["schemaVersion"] == 1, data
assert data["runtimeTouched"] is False, data
assert data["readiness"]["deploymentProofStatus"] == "STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF", data
included = {item["archivePath"]: item for item in data["included"]}
for required in (
        "readiness/deployment-readiness-report.md",
        "readiness/deployment-readiness-report.json",
        "proof/deployment-proof-manifest.json",
        "proof/01-desktop-client-proof.md",
        "proof/02-runtime-data-backup-proof.md",
        "client/MANIFEST.txt",
        "server-deployment/README.md"):
    assert required in included, included
assert any(
        "runtime backup archive contains" in item.get("reason", "")
        for item in data["excluded"]), data["excluded"]
assert "archiveSha256" not in data, "bundle metadata should not hash itself recursively"
PY
PREPARED_PROOF_DIR="$TMP_DIR/prepared-proof-dir"
mkdir -p "$PREPARED_PROOF_DIR"
cp "$TMP_DIR/deployment-readiness-report.md" "$PREPARED_PROOF_DIR/deployment-readiness-report.md"
cp "$TMP_DIR/deployment-readiness-report.json" "$PREPARED_PROOF_DIR/deployment-readiness-report.json"
cp "$TMP_DIR/proof-manifest-check-ok.json" "$PREPARED_PROOF_DIR/deployment-proof-manifest.json"
cp "$TMP_DIR/desktop-client-proof.md" "$PREPARED_PROOF_DIR/desktop-client-proof.md"
cp "$TMP_DIR/runtime-data-backup-proof.md" "$PREPARED_PROOF_DIR/runtime-data-backup-proof.md"
cp -R "$TMP_DIR/2006scape-client-from-config" "$PREPARED_PROOF_DIR/2006scape-client"
cp -R "$TMP_DIR/sample-server-deployment" "$PREPARED_PROOF_DIR/server-deployment"
scripts/package-deployment-proof.py \
    --prepared-dir "$PREPARED_PROOF_DIR" \
    --archive "$TMP_DIR/deployment-proof-bundle-prepared-dir.tgz" \
    --json > "$TMP_DIR/deployment-proof-bundle-prepared-dir.out"
grep -q '"runtimeTouched": false' "$TMP_DIR/deployment-proof-bundle-prepared-dir.out"
test -f "$TMP_DIR/deployment-proof-bundle-prepared-dir.tgz"
tar -tzf "$TMP_DIR/deployment-proof-bundle-prepared-dir.tgz" | sort > "$TMP_DIR/deployment-proof-bundle-prepared-dir.entries"
grep -q '^readiness/deployment-readiness-report.md$' "$TMP_DIR/deployment-proof-bundle-prepared-dir.entries"
grep -q '^readiness/deployment-readiness-report.json$' "$TMP_DIR/deployment-proof-bundle-prepared-dir.entries"
grep -q '^proof/deployment-proof-manifest.json$' "$TMP_DIR/deployment-proof-bundle-prepared-dir.entries"
grep -q '^proof/01-desktop-client-proof.md$' "$TMP_DIR/deployment-proof-bundle-prepared-dir.entries"
grep -q '^proof/02-runtime-data-backup-proof.md$' "$TMP_DIR/deployment-proof-bundle-prepared-dir.entries"
grep -q '^client/MANIFEST.txt$' "$TMP_DIR/deployment-proof-bundle-prepared-dir.entries"
grep -q '^server-deployment/README.md$' "$TMP_DIR/deployment-proof-bundle-prepared-dir.entries"
if grep -q '2006scape-runtime-data-test.tgz' "$TMP_DIR/deployment-proof-bundle-prepared-dir.entries"; then
    echo "package-deployment-proof.py --prepared-dir bundled a runtime-data backup archive." >&2
    exit 1
fi
tar -xOf "$TMP_DIR/deployment-proof-bundle-prepared-dir.tgz" bundle-metadata.json > "$TMP_DIR/deployment-proof-bundle-prepared-dir-metadata.json"
python3 - "$TMP_DIR/deployment-proof-bundle-prepared-dir-metadata.json" "$PREPARED_PROOF_DIR" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["runtimeTouched"] is False, data
assert data["preparedDir"] == sys.argv[2], data
assert data["proofManifest"]["requireFullProof"] is True, data
assert data["readiness"]["deploymentProofStatus"] == "STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF", data
PY
if scripts/package-deployment-proof.py \
    --prepared-dir "$PREPARED_PROOF_DIR" \
    --archive "$TMP_DIR/deployment-proof-bundle-require-full-partial.tgz" \
    --require-full-proof > "$TMP_DIR/deployment-proof-bundle-require-full-partial.out" 2>&1; then
    echo "package-deployment-proof.py --require-full-proof accepted a partial readiness report." >&2
    exit 1
fi
grep -q "requires final deploymentProofStatus" "$TMP_DIR/deployment-proof-bundle-require-full-partial.out"
PREPARED_FULL_PROOF_DIR="$TMP_DIR/prepared-full-proof-dir"
cp -R "$PREPARED_PROOF_DIR" "$PREPARED_FULL_PROOF_DIR"
python3 - "$PREPARED_PROOF_DIR/deployment-readiness-report.json" "$PREPARED_FULL_PROOF_DIR/deployment-readiness-report.json" <<'PY'
import json
import sys
from pathlib import Path

source, target = map(Path, sys.argv[1:3])
data = json.loads(source.read_text(encoding="utf-8"))
data["deploymentProofStatus"] = "LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_PROOF_RECORDED_DISCORD_NOT_REQUESTED"
data["liveChecksRequested"] = True
data["remainingLiveProof"] = []
status_by_requirement = {
    "Public reachability and bridge non-exposure": "REQUESTED",
    "External PBKDF2 game-protocol login": "REQUESTED",
    "Concurrent external plus same-host local protocol login": "REQUESTED",
    "Desktop client coexistence": "MANUAL_PROOF_RECORDED",
    "Runtime data backup before remote replacement/restart": "MANUAL_PROOF_RECORDED",
    "Fail-closed login cases": "REQUESTED",
    "Agent-to-player chat delivery": "DELIVERY_LOG_PROOF_REQUESTED",
}
for item in data.get("proofCoverage", []):
    requirement = item.get("requirement")
    if requirement in status_by_requirement:
        item["status"] = status_by_requirement[requirement]
        item["evidence"] = "validation fixture final-proof evidence"
target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
scripts/package-deployment-proof.py \
    --prepared-dir "$PREPARED_FULL_PROOF_DIR" \
    --archive "$TMP_DIR/deployment-proof-bundle-require-full.tgz" \
    --require-full-proof \
    --json > "$TMP_DIR/deployment-proof-bundle-require-full.out"
grep -q '"runtimeTouched": false' "$TMP_DIR/deployment-proof-bundle-require-full.out"
test -f "$TMP_DIR/deployment-proof-bundle-require-full.tgz"
tar -xOf "$TMP_DIR/deployment-proof-bundle-require-full.tgz" bundle-metadata.json > "$TMP_DIR/deployment-proof-bundle-require-full-metadata.json"
python3 - "$TMP_DIR/deployment-proof-bundle-require-full-metadata.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["runtimeTouched"] is False, data
assert data["readiness"]["deploymentProofStatus"] == "LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_PROOF_RECORDED_DISCORD_NOT_REQUESTED", data
assert data["proofManifest"]["requireFullProof"] is True, data
assert data["finalProofCheck"]["status"] == "PASS", data
checks = {check["field"]: check for check in data["finalProofCheck"]["proofFileChecks"]}
assert checks["desktop_client_proof_file"]["status"] == "PASS", checks
assert checks["runtime_data_backup_proof_file"]["status"] == "PASS", checks
PY
python3 agent-navigation/tools/script_registry.py run deployment_proof_bundle -- \
    --prepared-dir "$PREPARED_PROOF_DIR" \
    --archive "$TMP_DIR/deployment-proof-bundle-registry.tgz" \
    --json > "$TMP_DIR/deployment-proof-bundle-registry.out"
grep -q '"runtimeTouched": false' "$TMP_DIR/deployment-proof-bundle-registry.out"
test -f "$TMP_DIR/deployment-proof-bundle-registry.tgz"
if scripts/package-deployment-proof.py \
    --proof-file "$RUNTIME_BACKUP_ARCHIVE" \
    --archive "$TMP_DIR/deployment-proof-bundle-bad-runtime-archive.tgz" > "$TMP_DIR/deployment-proof-bundle-bad-runtime-archive.out" 2>&1; then
    echo "package-deployment-proof.py unexpectedly accepted a runtime-data backup archive as a proof file." >&2
    exit 1
fi
grep -q "runtime/secret-bearing data" "$TMP_DIR/deployment-proof-bundle-bad-runtime-archive.out"
ln -s "$TMP_DIR/deployment-proof-bundle-target.tgz" "$TMP_DIR/deployment-proof-bundle-link.tgz"
if scripts/package-deployment-proof.py \
    --readiness-report "$TMP_DIR/deployment-readiness-report.md" \
    --archive "$TMP_DIR/deployment-proof-bundle-link.tgz" > "$TMP_DIR/deployment-proof-bundle-symlink-output.out" 2>&1; then
    echo "package-deployment-proof.py unexpectedly accepted a symlinked archive output path." >&2
    exit 1
fi
grep -q "refusing to write archive through symlink path" "$TMP_DIR/deployment-proof-bundle-symlink-output.out"
cat > "$TMP_DIR/deployment-proof-bundle-placeholder-manifest.json" <<'EOF'
{
  "runtime_data_backup_proof_file": "PATH_TO_RUNTIME_DATA_BACKUP_PROOF.md"
}
EOF
if scripts/package-deployment-proof.py \
    --proof-manifest "$TMP_DIR/deployment-proof-bundle-placeholder-manifest.json" \
    --archive "$TMP_DIR/deployment-proof-bundle-placeholder-manifest.tgz" > "$TMP_DIR/deployment-proof-bundle-placeholder-manifest.out" 2>&1; then
    echo "package-deployment-proof.py unexpectedly accepted a placeholder proof manifest." >&2
    exit 1
fi
grep -q "deployment proof manifest is invalid" "$TMP_DIR/deployment-proof-bundle-placeholder-manifest.out"
grep -q "placeholder value" "$TMP_DIR/deployment-proof-bundle-placeholder-manifest.out"
if grep -q "Traceback" "$TMP_DIR/deployment-proof-bundle-placeholder-manifest.out"; then
    echo "package-deployment-proof.py printed a traceback for an invalid proof manifest." >&2
    exit 1
fi
cat > "$TMP_DIR/proof-manifest-check-missing-reject-statuses.json" <<EOF
{
  "live": true,
  "live_login_username": "ExternalTest",
  "live_login_password_env": "EXTERNAL_PASSWORD",
  "live_local_login_username": "LocalTest",
  "live_local_login_password_env": "LOCAL_PASSWORD",
  "live_reject_login_username": "RejectTest",
  "live_reject_login_password_env": "REJECT_PASSWORD",
  "desktop_client_proof_file": "$TMP_DIR/desktop-client-proof.md",
  "runtime_data_backup_proof_file": "$TMP_DIR/runtime-data-backup-proof.md",
  "agent_chat_delivery_log_text": "agent-to-player-marker",
  "agent_chat_delivery_log_to_name": "MrGem",
  "require_full_proof": true
}
EOF
if scripts/check-deployment-proof-manifest.py \
    "$TMP_DIR/proof-manifest-check-missing-reject-statuses.json" \
    --require-full-proof > "$TMP_DIR/proof-manifest-check-missing-reject-statuses.out" 2>&1; then
    echo "check-deployment-proof-manifest.py unexpectedly accepted missing reject-login expected statuses." >&2
    exit 1
fi
grep -q "missing required full-proof field: live_reject_login_expected_statuses" "$TMP_DIR/proof-manifest-check-missing-reject-statuses.out"
cat > "$TMP_DIR/proof-manifest-check-bad-runtime-proof.json" <<EOF
{
  "runtime_data_backup_proof_file": "$TMP_DIR/runtime-data-backup-proof-bad-sha.md"
}
EOF
if scripts/check-deployment-proof-manifest.py \
    "$TMP_DIR/proof-manifest-check-bad-runtime-proof.json" \
    --check-files > "$TMP_DIR/proof-manifest-check-bad-runtime-proof.out" 2>&1; then
    echo "check-deployment-proof-manifest.py unexpectedly accepted a bad runtime backup proof file." >&2
    exit 1
fi
grep -q "backup archive sha256 mismatch" "$TMP_DIR/proof-manifest-check-bad-runtime-proof.out"
if scripts/check-deployment-proof-manifest.py \
    "$TMP_DIR/proof-manifest-check-ok.json" \
    --require-full-proof \
    --check-env > "$TMP_DIR/proof-manifest-check-missing-env.out" 2>&1; then
    echo "check-deployment-proof-manifest.py unexpectedly accepted missing password env vars." >&2
    exit 1
fi
grep -q "environment variable named by live_login_password_env is not set" "$TMP_DIR/proof-manifest-check-missing-env.out"
EXTERNAL_PASSWORD=external LOCAL_PASSWORD=local REJECT_PASSWORD=reject \
    scripts/check-deployment-proof-manifest.py \
    "$TMP_DIR/proof-manifest-check-ok.json" \
    --require-full-proof \
    --check-env > "$TMP_DIR/proof-manifest-check-env-ok.out"
grep -q "status: PASS" "$TMP_DIR/proof-manifest-check-env-ok.out"
cat > "$TMP_DIR/proof-manifest-check-placeholder.json" <<'EOF'
{
  "runtime_data_backup_proof_file": "PATH_TO_RUNTIME_DATA_BACKUP_PROOF.md"
}
EOF
if scripts/check-deployment-proof-manifest.py \
    "$TMP_DIR/proof-manifest-check-placeholder.json" > "$TMP_DIR/proof-manifest-check-placeholder.out" 2>&1; then
    echo "check-deployment-proof-manifest.py unexpectedly accepted placeholder proof manifest values." >&2
    exit 1
fi
grep -q "placeholder value" "$TMP_DIR/proof-manifest-check-placeholder.out"
cat > "$TMP_DIR/proof-manifest-check-discord-config.json" <<'EOF'
{
  "agent_chat_discord_enabled": true
}
EOF
if scripts/check-deployment-proof-manifest.py \
    "$TMP_DIR/proof-manifest-check-ok.json" \
    --config "$TMP_DIR/proof-manifest-check-discord-config.json" \
    --require-full-proof > "$TMP_DIR/proof-manifest-check-discord-missing.out" 2>&1; then
    echo "check-deployment-proof-manifest.py unexpectedly accepted missing Discord proof fields." >&2
    exit 1
fi
grep -q "missing required Discord proof field: live_discord" "$TMP_DIR/proof-manifest-check-discord-missing.out"
cat > "$TMP_DIR/proof-manifest-check-discord.json" <<EOF
{
  "live": true,
  "live_login_username": "ExternalTest",
  "live_login_password_env": "EXTERNAL_PASSWORD",
  "live_local_login_username": "LocalTest",
  "live_local_login_password_env": "LOCAL_PASSWORD",
  "live_reject_login_username": "RejectTest",
  "live_reject_login_password_env": "REJECT_PASSWORD",
  "live_reject_login_expected_statuses": "3,4",
  "desktop_client_proof_file": "$TMP_DIR/desktop-client-proof.md",
  "runtime_data_backup_proof_file": "$TMP_DIR/runtime-data-backup-proof.md",
  "agent_chat_delivery_log_text": "agent-to-player-marker",
  "agent_chat_delivery_log_to_name": "MrGem",
  "live_discord": true,
  "agent_chat_log_text": "discord-to-server-marker",
  "agent_chat_log_from_type": "discord",
  "agent_chat_log_from_bot": "false",
  "discord_channel_message_text": "server-to-discord-marker",
  "discord_channel_message_agent": ["MrFlame"]
}
EOF
if scripts/check-deployment-proof-manifest.py \
    "$TMP_DIR/proof-manifest-check-discord.json" \
    --require-full-proof \
    --blocked-routing-required > "$TMP_DIR/proof-manifest-check-blocked-missing.out" 2>&1; then
    echo "check-deployment-proof-manifest.py unexpectedly accepted missing blocked-routing proof field." >&2
    exit 1
fi
grep -q "missing required blocked-routing proof field: agent_chat_blocked_log_text" "$TMP_DIR/proof-manifest-check-blocked-missing.out"
python3 - <<'PY'
import importlib.util
from pathlib import Path
from types import SimpleNamespace

path = Path("scripts/prepare-external-deployment.py")
spec = importlib.util.spec_from_file_location("prepare_external_deployment", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

args = SimpleNamespace(
        config="ServerConfig.json",
        accounts_dir="accounts",
        secrets="secrets.json",
        json_output="report.json",
        allow_empty_accounts=False,
        allow_wildcard_bind=False,
        allow_placeholder_network_config=False,
        allow_placeholder_discord_secrets=False,
        require_full_proof=False,
        live=False,
        timeout=2.0,
        tls_sni_host="",
        allow_untrusted_client_tls=False,
        live_login_username="",
        live_login_password_env="",
        live_login_hold_seconds=0.0,
        live_local_login_username="",
        live_local_login_password_env="",
        live_local_host="127.0.0.1",
        live_local_port=0,
        live_reject_login_username="",
        live_reject_login_password_env="",
        live_reject_login_expected_statuses="",
        live_discord=False,
        agent_chat_log_root="agent-chat-log",
        agent_chat_log_text="discord-marker",
        agent_chat_log_from_type="discord",
        agent_chat_log_from_name="",
        agent_chat_log_from_profile="",
        agent_chat_log_from_bot="false",
        agent_chat_log_discord_message_id="123456789012345678",
        agent_chat_log_to_type="",
        agent_chat_log_to_name="",
        agent_chat_log_channel="agent",
        agent_chat_log_since_seconds=0.0,
        agent_chat_log_since_id=0,
        agent_chat_blocked_log_root="",
        agent_chat_blocked_log_text="blocked-marker",
        agent_chat_blocked_log_channel="agent",
        agent_chat_blocked_log_since_seconds=0.0,
        agent_chat_blocked_log_since_id=0,
        agent_chat_delivery_log_root="",
        agent_chat_delivery_log_text="delivery-marker",
        agent_chat_delivery_log_to_name="MrGem",
        agent_chat_delivery_log_channel="agent",
        agent_chat_delivery_log_since_seconds=0.0,
        agent_chat_delivery_log_since_id=0,
        desktop_client_proof_file="",
        runtime_data_backup_proof_file="runtime-data-backup-proof.md",
        discord_channel_message_text="",
        discord_channel_message_agent=[],
        discord_channel_message_limit=50,
        discord_channel_message_after_id="",
        discord_channel_message_allow_human_author=False,
        discord_channel_message_require_all=False,
        command_timeout=120.0,
)
argv = module.build_report_args(
        args,
        Path("client-dist"),
        Path("client.zip"),
        Path("report.md"),
        Path("server-deployment"),
        Path("client-tls-tunnel-operator"),
)
assert "--client-tls-tunnel-dir" in argv, argv
index = argv.index("--client-tls-tunnel-dir")
assert argv[index + 1] == "client-tls-tunnel-operator", argv
assert "--json-output" in argv, argv
index = argv.index("--json-output")
assert argv[index + 1] == "report.json", argv
assert "--agent-chat-log-from-bot" in argv, argv
index = argv.index("--agent-chat-log-from-bot")
assert argv[index + 1] == "false", argv
assert "--agent-chat-log-discord-message-id" in argv, argv
index = argv.index("--agent-chat-log-discord-message-id")
assert argv[index + 1] == "123456789012345678", argv
assert "--agent-chat-log-from-type" in argv, argv
assert "--agent-chat-log-channel" in argv, argv
assert "--agent-chat-blocked-log-text" in argv, argv
index = argv.index("--agent-chat-blocked-log-text")
assert argv[index + 1] == "blocked-marker", argv
assert "--agent-chat-blocked-log-channel" in argv, argv
assert "--agent-chat-delivery-log-text" in argv, argv
index = argv.index("--agent-chat-delivery-log-text")
assert argv[index + 1] == "delivery-marker", argv
assert "--agent-chat-delivery-log-to-name" in argv, argv
index = argv.index("--agent-chat-delivery-log-to-name")
assert argv[index + 1] == "MrGem", argv
assert "--runtime-data-backup-proof-file" in argv, argv
index = argv.index("--runtime-data-backup-proof-file")
assert argv[index + 1] == "runtime-data-backup-proof.md", argv
args.require_full_proof = True
argv = module.build_report_args(
        args,
        Path("client-dist"),
        Path("client.zip"),
        Path("report.md"),
        Path("server-deployment"),
)
assert "--require-full-proof" in argv, argv
values = module.merged_proof_manifest_values(args)
assert values["require_full_proof"] is True, values
assert values["agent_chat_log_text"] == "discord-marker", values
assert values["agent_chat_delivery_log_text"] == "delivery-marker", values
assert values["runtime_data_backup_proof_file"] == "runtime-data-backup-proof.md", values
assert "desktop_client_proof_file" not in values, values
precheck_argv = module.proof_manifest_precheck_args(args, Path("merged-proof.json"))
assert precheck_argv[:2] == ["scripts/check-deployment-proof-manifest.py", "merged-proof.json"], precheck_argv
assert "--require-full-proof" in precheck_argv, precheck_argv
assert "--check-files" in precheck_argv, precheck_argv
assert "--check-env" in precheck_argv, precheck_argv
assert "--secrets" in precheck_argv, precheck_argv
assert "--discord-required" in precheck_argv, precheck_argv
assert "--blocked-routing-required" in precheck_argv, precheck_argv

calls = []
def fake_run_precheck(command):
    calls.append(command)
    merged_path = Path(command[1])
    merged = __import__("json").loads(merged_path.read_text(encoding="utf-8"))
    assert merged["require_full_proof"] is True, merged
    assert merged["agent_chat_delivery_log_text"] == "delivery-marker", merged
    assert merged["runtime_data_backup_proof_file"] == "runtime-data-backup-proof.md", merged
    assert "desktop_client_proof_file" not in merged, merged

module.run_precheck = fake_run_precheck
module.run_final_proof_manifest_precheck(args)
assert calls, "proof manifest precheck was not called"
assert not Path(calls[0][1]).exists(), "temporary merged proof manifest was not removed"
PY
cat > "$TMP_DIR/prepare-precheck-config.json" <<'EOF'
{
  "agent_chat_discord_enabled": false
}
EOF
if scripts/prepare-external-deployment.py \
    --config "$TMP_DIR/prepare-precheck-config.json" \
    --output-dir "$TMP_DIR/prepare-precheck-output" \
    --require-full-proof > "$TMP_DIR/prepare-precheck-fail.out" 2>&1; then
    echo "prepare-external-deployment.py unexpectedly packaged before final proof precheck failed." >&2
    exit 1
fi
grep -q "missing required full-proof field: live" "$TMP_DIR/prepare-precheck-fail.out"
test ! -e "$TMP_DIR/prepare-precheck-output"
python3 - "$TMP_DIR/sample-server-deployment/proof-templates/desktop-client-proof.md" <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path("scripts/deployment-readiness-report.py")
spec = importlib.util.spec_from_file_location("deployment_readiness_report", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run_desktop_client_proof_file_check(sys.argv[1])
assert result["exitCode"] == 1, result
assert "placeholder text" in result["output"], result
PY
ln -s "$TMP_DIR/sample-server-deployment/proof-templates/desktop-client-proof.md" "$TMP_DIR/desktop-client-proof-link.md"
python3 - "$TMP_DIR/desktop-client-proof-link.md" <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path("scripts/deployment-readiness-report.py")
spec = importlib.util.spec_from_file_location("deployment_readiness_report", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run_desktop_client_proof_file_check(sys.argv[1])
assert result["exitCode"] == 1, result
assert "proof file must not be a symlink" in result["output"], result
PY
python3 - "$TMP_DIR/sample-server-deployment/proof-templates/runtime-data-backup-proof.md" <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path("scripts/deployment-readiness-report.py")
spec = importlib.util.spec_from_file_location("deployment_readiness_report", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run_manual_proof_file_check(
        "runtime data backup proof",
        sys.argv[1],
        module.RUNTIME_DATA_BACKUP_PROOF_REQUIREMENTS,
        "runtime data backup proof",
)
assert result["exitCode"] == 1, result
assert "placeholder text" in result["output"], result
PY
cat > "$TMP_DIR/incomplete-desktop-client-proof.md" <<'EOF'
# Desktop Client Coexistence Proof

Both clients looked okay.
EOF
python3 - "$TMP_DIR/incomplete-desktop-client-proof.md" <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path("scripts/deployment-readiness-report.py")
spec = importlib.util.spec_from_file_location("deployment_readiness_report", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run_desktop_client_proof_file_check(sys.argv[1])
assert result["exitCode"] == 1, result
assert "missing required desktop proof detail" in result["output"], result
PY
cat > "$TMP_DIR/missing-evidence-desktop-client-proof.md" <<'EOF'
# Desktop Client Coexistence Proof

- same-host client: local throwaway account connected through 127.0.0.1
- external client: tunnel throwaway account connected through the configured VPN/tunnel endpoint
- observed: both desktop clients remained online at the same time
EOF
python3 - "$TMP_DIR/missing-evidence-desktop-client-proof.md" <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path("scripts/deployment-readiness-report.py")
spec = importlib.util.spec_from_file_location("deployment_readiness_report", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run_desktop_client_proof_file_check(sys.argv[1])
assert result["exitCode"] == 1, result
assert "desktop client proof is missing an evidence line" in result["output"], result
PY
cat > "$TMP_DIR/symlink-evidence-desktop-client-proof.md" <<EOF
# Desktop Client Coexistence Proof

- same-host client: local throwaway account connected through 127.0.0.1
- external client: tunnel throwaway account connected through the configured VPN/tunnel endpoint
- observed: both desktop clients remained online at the same time
- evidence: $TMP_DIR/desktop-client-proof-evidence-link.log
EOF
ln -s "$TMP_DIR/desktop-client-proof-evidence.log" "$TMP_DIR/desktop-client-proof-evidence-link.log"
python3 - "$TMP_DIR/symlink-evidence-desktop-client-proof.md" <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path("scripts/deployment-readiness-report.py")
spec = importlib.util.spec_from_file_location("deployment_readiness_report", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run_desktop_client_proof_file_check(sys.argv[1])
assert result["exitCode"] == 1, result
assert "desktop client proof evidence must not be a symlink" in result["output"], result
PY
cat > "$TMP_DIR/incomplete-runtime-data-backup-proof.md" <<'EOF'
# Runtime Data Backup Proof

Backed up files.
EOF
python3 - "$TMP_DIR/incomplete-runtime-data-backup-proof.md" <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path("scripts/deployment-readiness-report.py")
spec = importlib.util.spec_from_file_location("deployment_readiness_report", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run_manual_proof_file_check(
        "runtime data backup proof",
        sys.argv[1],
        module.RUNTIME_DATA_BACKUP_PROOF_REQUIREMENTS,
        "runtime data backup proof",
)
assert result["exitCode"] == 1, result
assert "missing required runtime data backup proof detail" in result["output"], result
PY

echo "Smoke-testing deployment verifier rejects incomplete server deployment templates..."
cp -R "$TMP_DIR/sample-server-deployment" "$TMP_DIR/broken-server-deployment"
printf '# Broken server deployment README\n' > "$TMP_DIR/broken-server-deployment/README.md"
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --server-deployment-dir "$TMP_DIR/broken-server-deployment" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/broken-server-deployment-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted an incomplete server deployment README." >&2
    cat "$TMP_DIR/broken-server-deployment-verify.out" >&2
    exit 1
fi
grep -q "server deployment README is missing required text" "$TMP_DIR/broken-server-deployment-verify.out"

cp -R "$TMP_DIR/sample-server-deployment" "$TMP_DIR/broken-server-deployment-readme-secrets"
python3 - "$TMP_DIR/broken-server-deployment-readme-secrets/README.md" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace(" --secrets '/opt/2006scape/2006Scape Server/data/secrets.json'", "")
path.write_text(text, encoding="utf-8")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --server-deployment-dir "$TMP_DIR/broken-server-deployment-readme-secrets" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/broken-server-deployment-readme-secrets-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a server deployment README without proof-manifest --secrets guidance." >&2
    cat "$TMP_DIR/broken-server-deployment-readme-secrets-verify.out" >&2
    exit 1
fi
grep -q "server deployment README is missing required text" "$TMP_DIR/broken-server-deployment-readme-secrets-verify.out"

cp -R "$TMP_DIR/sample-server-deployment" "$TMP_DIR/broken-server-deployment-proof-manifest"
python3 - "$TMP_DIR/broken-server-deployment-proof-manifest/proof-templates/deployment-proof-manifest.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(json.dumps({
    "live": "true",
    "live_login_password_env": "EXTERNAL_TEST_PASSWORD",
    "live_local_login_password_env": "LOCAL_TEST_PASSWORD",
    "runtime_data_backup_proof_file": "PATH_TO_RUNTIME_DATA_BACKUP_PROOF.md",
    "agent_chat_delivery_log_text": "AGENT_TO_PLAYER_MARKER",
    "discord_channel_message_text": "SERVER_TO_DISCORD_MARKER",
}, indent=2), encoding="utf-8")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --server-deployment-dir "$TMP_DIR/broken-server-deployment-proof-manifest" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/broken-server-deployment-proof-manifest-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted an invalid deployment proof manifest template." >&2
    cat "$TMP_DIR/broken-server-deployment-proof-manifest-verify.out" >&2
    exit 1
fi
grep -q "deployment proof manifest template is invalid" "$TMP_DIR/broken-server-deployment-proof-manifest-verify.out"

cp -R "$TMP_DIR/sample-server-deployment" "$TMP_DIR/broken-server-deployment-proof-manifest-final-gate"
python3 - "$TMP_DIR/broken-server-deployment-proof-manifest-final-gate/proof-templates/deployment-proof-manifest.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
data["require_full_proof"] = False
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --server-deployment-dir "$TMP_DIR/broken-server-deployment-proof-manifest-final-gate" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/broken-server-deployment-proof-manifest-final-gate-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a proof manifest template with require_full_proof=false." >&2
    cat "$TMP_DIR/broken-server-deployment-proof-manifest-final-gate-verify.out" >&2
    exit 1
fi
grep -q "deployment proof manifest template must set require_full_proof=true" "$TMP_DIR/broken-server-deployment-proof-manifest-final-gate-verify.out"

cp -R "$TMP_DIR/sample-server-deployment" "$TMP_DIR/broken-server-deployment-desktop-template"
python3 - "$TMP_DIR/broken-server-deployment-desktop-template/proof-templates/desktop-client-proof.md" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
path.write_text(
        "\n".join(line for line in lines if not line.startswith("- evidence:")) + "\n",
        encoding="utf-8",
)
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --server-deployment-dir "$TMP_DIR/broken-server-deployment-desktop-template" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/broken-server-deployment-desktop-template-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a desktop proof template without evidence guidance." >&2
    cat "$TMP_DIR/broken-server-deployment-desktop-template-verify.out" >&2
    exit 1
fi
grep -q "desktop client proof template is missing required text" "$TMP_DIR/broken-server-deployment-desktop-template-verify.out"

cp -R "$TMP_DIR/sample-server-deployment" "$TMP_DIR/broken-server-deployment-runtime-backup-template"
python3 - "$TMP_DIR/broken-server-deployment-runtime-backup-template/proof-templates/runtime-data-backup-proof.md" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
path.write_text(
        "\n".join(line for line in lines
                  if "runtime: not started, stopped, or restarted" not in line) + "\n",
        encoding="utf-8",
)
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --server-deployment-dir "$TMP_DIR/broken-server-deployment-runtime-backup-template" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/broken-server-deployment-runtime-backup-template-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a runtime backup proof template without runtime-unchanged proof." >&2
    cat "$TMP_DIR/broken-server-deployment-runtime-backup-template-verify.out" >&2
    exit 1
fi
grep -q "runtime data backup proof template is missing required text" "$TMP_DIR/broken-server-deployment-runtime-backup-template-verify.out"

cp -R "$TMP_DIR/sample-server-deployment" "$TMP_DIR/broken-server-deployment-service-user"
python3 - "$TMP_DIR/broken-server-deployment-service-user/2006scape-server.service" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(path.read_text(encoding="utf-8").replace("User=2006scape", "User=2006scape;root"), encoding="utf-8")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --server-deployment-dir "$TMP_DIR/broken-server-deployment-service-user" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/broken-server-deployment-service-user-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a tampered systemd service user." >&2
    cat "$TMP_DIR/broken-server-deployment-service-user-verify.out" >&2
    exit 1
fi
grep -q "simple service user/group name" "$TMP_DIR/broken-server-deployment-service-user-verify.out"

cp -R "$TMP_DIR/sample-server-deployment" "$TMP_DIR/broken-server-deployment-env-path"
python3 - "$TMP_DIR/broken-server-deployment-env-path/2006scape-server.env" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(path.read_text(encoding="utf-8").replace("JAVA_BIN=/usr/bin/java", "JAVA_BIN=/usr/bin/java;touch-bad"), encoding="utf-8")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --server-deployment-dir "$TMP_DIR/broken-server-deployment-env-path" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/broken-server-deployment-env-path-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a tampered server env path." >&2
    cat "$TMP_DIR/broken-server-deployment-env-path-verify.out" >&2
    exit 1
fi
grep -q "server deployment environment JAVA_BIN must be an absolute path with simple characters" "$TMP_DIR/broken-server-deployment-env-path-verify.out"

echo "Smoke-testing deployment verifier requires client guidance text..."
cp -R "$TMP_DIR/2006scape-client-from-config" "$TMP_DIR/2006scape-client-missing-readme-guidance"
printf '2006Scape Client\n' > "$TMP_DIR/2006scape-client-missing-readme-guidance/README.txt"
(
    cd "$TMP_DIR/2006scape-client-missing-readme-guidance"
    shasum -a 256 \
        2006scape-client.jar \
        Check-Setup.command \
        Run-2006Scape.command \
        client.properties \
        check-setup-macos-linux.sh \
        check-setup-windows.bat \
        run-macos-linux.sh \
        run-windows.bat \
        README.txt \
        MANIFEST.txt > SHA256SUMS
)
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-missing-readme-guidance" \
    --archive "$TMP_DIR/2006scape-client-from-config.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/missing-readme-guidance-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a client README without Java/transport guidance." >&2
    cat "$TMP_DIR/missing-readme-guidance-verify.out" >&2
    exit 1
fi
grep -q "client README is missing required text" "$TMP_DIR/missing-readme-guidance-verify.out"

cp -R "$TMP_DIR/2006scape-client-from-config" "$TMP_DIR/2006scape-client-missing-launcher-guidance"
python3 - "$TMP_DIR/2006scape-client-missing-launcher-guidance/run-macos-linux.sh" <<'PY'
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as source:
    text = source.read()
text = text.replace("Java is required to run 2006Scape.", "Java is required.")
with open(path, "w", encoding="utf-8") as target:
    target.write(text)
PY
(
    cd "$TMP_DIR/2006scape-client-missing-launcher-guidance"
    shasum -a 256 \
        2006scape-client.jar \
        Check-Setup.command \
        Run-2006Scape.command \
        client.properties \
        check-setup-macos-linux.sh \
        check-setup-windows.bat \
        run-macos-linux.sh \
        run-windows.bat \
        README.txt \
        MANIFEST.txt > SHA256SUMS
)
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-missing-launcher-guidance" \
    --archive "$TMP_DIR/2006scape-client-from-config.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/missing-launcher-guidance-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a launcher without Java guidance." >&2
    cat "$TMP_DIR/missing-launcher-guidance-verify.out" >&2
    exit 1
fi
grep -q "macOS/Linux launcher is missing required text" "$TMP_DIR/missing-launcher-guidance-verify.out"

cp -R "$TMP_DIR/2006scape-client-from-config" "$TMP_DIR/2006scape-client-missing-setup-guidance"
python3 - "$TMP_DIR/2006scape-client-missing-setup-guidance/check-setup-macos-linux.sh" <<'PY'
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as source:
    text = source.read()
text = text.replace("Java is required to run 2006Scape.", "Java is required.")
with open(path, "w", encoding="utf-8") as target:
    target.write(text)
PY
(
    cd "$TMP_DIR/2006scape-client-missing-setup-guidance"
    shasum -a 256 \
        2006scape-client.jar \
        Check-Setup.command \
        Run-2006Scape.command \
        client.properties \
        check-setup-macos-linux.sh \
        check-setup-windows.bat \
        run-macos-linux.sh \
        run-windows.bat \
        README.txt \
        MANIFEST.txt > SHA256SUMS
)
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-missing-setup-guidance" \
    --archive "$TMP_DIR/2006scape-client-from-config.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/missing-setup-guidance-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a setup checker without Java guidance." >&2
    cat "$TMP_DIR/missing-setup-guidance-verify.out" >&2
    exit 1
fi
grep -q "macOS/Linux setup checker is missing required text" "$TMP_DIR/missing-setup-guidance-verify.out"

cp -R "$TMP_DIR/2006scape-client-from-config" "$TMP_DIR/2006scape-client-missing-warning-suppression"
python3 - "$TMP_DIR/2006scape-client-missing-warning-suppression/run-macos-linux.sh" "$TMP_DIR/2006scape-client-missing-warning-suppression/run-windows.bat" <<'PY'
import sys

for filename in sys.argv[1:]:
    with open(filename, "r", encoding="utf-8") as source:
        text = source.read()
    text = text.replace(" -no-java-warnings", "")
    with open(filename, "w", encoding="utf-8") as target:
        target.write(text)
PY
(
    cd "$TMP_DIR/2006scape-client-missing-warning-suppression"
    shasum -a 256 \
        2006scape-client.jar \
        Check-Setup.command \
        Run-2006Scape.command \
        client.properties \
        check-setup-macos-linux.sh \
        check-setup-windows.bat \
        run-macos-linux.sh \
        run-windows.bat \
        README.txt \
        MANIFEST.txt > SHA256SUMS
)
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-missing-warning-suppression" \
    --archive "$TMP_DIR/2006scape-client-from-config.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/missing-warning-suppression-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted launchers without -no-java-warnings." >&2
    cat "$TMP_DIR/missing-warning-suppression-verify.out" >&2
    exit 1
fi
grep -q "macOS/Linux launcher is missing required text" "$TMP_DIR/missing-warning-suppression-verify.out"

cp -R "$TMP_DIR/2006scape-client-from-config" "$TMP_DIR/2006scape-client-lf-windows-launcher"
python3 - "$TMP_DIR/2006scape-client-lf-windows-launcher/run-windows.bat" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
PY
(
    cd "$TMP_DIR/2006scape-client-lf-windows-launcher"
    shasum -a 256 \
        2006scape-client.jar \
        Check-Setup.command \
        Run-2006Scape.command \
        client.properties \
        check-setup-macos-linux.sh \
        check-setup-windows.bat \
        run-macos-linux.sh \
        run-windows.bat \
        README.txt \
        MANIFEST.txt > SHA256SUMS
)
python3 - "$TMP_DIR/2006scape-client-lf-windows-launcher" "$TMP_DIR/2006scape-client-lf-windows-launcher.zip" <<'PY'
import stat
import sys
import zipfile
from pathlib import Path

dist_dir = Path(sys.argv[1]).resolve()
archive_path = Path(sys.argv[2]).resolve()

def zip_info(path, arcname):
    info = zipfile.ZipInfo(arcname)
    info.create_system = 3
    if path.is_dir():
        info.external_attr = (stat.S_IFDIR | 0o755) << 16
    else:
        mode = 0o755 if path.name in {
            "Check-Setup.command",
            "Run-2006Scape.command",
            "run-macos-linux.sh",
            "check-setup-macos-linux.sh",
        } else 0o644
        info.external_attr = (stat.S_IFREG | mode) << 16
    return info

with zipfile.ZipFile(str(archive_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
    archive.writestr(zip_info(dist_dir, dist_dir.name + "/"), b"")
    for path in sorted(dist_dir.rglob("*")):
        arcname = dist_dir.name + "/" + path.relative_to(dist_dir).as_posix()
        if path.is_dir():
            archive.writestr(zip_info(path, arcname + "/"), b"")
        else:
            archive.writestr(zip_info(path, arcname), path.read_bytes())
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-lf-windows-launcher" \
    --archive "$TMP_DIR/2006scape-client-lf-windows-launcher.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/lf-windows-launcher-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a Windows launcher without CRLF line endings." >&2
    cat "$TMP_DIR/lf-windows-launcher-verify.out" >&2
    exit 1
fi
grep -q "Windows launcher must use CRLF line endings" "$TMP_DIR/lf-windows-launcher-verify.out"

echo "Smoke-testing deployment verifier rejects symlinked client package paths..."
cp -R "$TMP_DIR/2006scape-client-from-config" "$TMP_DIR/2006scape-client-symlink-file"
rm "$TMP_DIR/2006scape-client-symlink-file/README.txt"
ln -s "$TMP_DIR/2006scape-client-from-config/README.txt" "$TMP_DIR/2006scape-client-symlink-file/README.txt"
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-symlink-file" \
    --archive "$TMP_DIR/2006scape-client-from-config.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/symlink-client-file-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a symlinked client package file." >&2
    cat "$TMP_DIR/symlink-client-file-verify.out" >&2
    exit 1
fi
grep -q "client package file must not be or contain a symlinked path" "$TMP_DIR/symlink-client-file-verify.out"

cp -R "$TMP_DIR/client-tls-tunnel-client" "$TMP_DIR/client-tls-tunnel-client-symlink-parent"
mv "$TMP_DIR/client-tls-tunnel-client-symlink-parent/client-tls-tunnel" "$TMP_DIR/client-tls-tunnel-parent-target"
ln -s "$TMP_DIR/client-tls-tunnel-parent-target" "$TMP_DIR/client-tls-tunnel-client-symlink-parent/client-tls-tunnel"
if scripts/verify-external-deployment.py \
    --config "$TMP_DIR/client-tls-tunnel-config.json" \
    --client-dist "$TMP_DIR/client-tls-tunnel-client-symlink-parent" \
    --archive "$TMP_DIR/client-tls-tunnel-client.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" > "$TMP_DIR/symlink-client-parent-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a symlinked client package parent directory." >&2
    cat "$TMP_DIR/symlink-client-parent-verify.out" >&2
    exit 1
fi
grep -q "client package file must not be or contain a symlinked path" "$TMP_DIR/symlink-client-parent-verify.out"

echo "Smoke-testing deployment verifier rejects unreachable or malformed account records..."
cp -R "$ACCOUNT_TMP_DIR/accounts" "$TMP_DIR/accounts-open-directory"
chmod 755 "$TMP_DIR/accounts-open-directory"
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$TMP_DIR/accounts-open-directory" \
    --allow-placeholder-network-config > "$TMP_DIR/accounts-open-directory-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a group/world-readable accounts directory." >&2
    cat "$TMP_DIR/accounts-open-directory-verify.out" >&2
    exit 1
fi
grep -q "accounts directory permissions must be owner-only" "$TMP_DIR/accounts-open-directory-verify.out"

cp -R "$ACCOUNT_TMP_DIR/accounts" "$TMP_DIR/accounts-open-record"
chmod 700 "$TMP_DIR/accounts-open-record"
chmod 644 "$TMP_DIR/accounts-open-record/testuser.json"
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$TMP_DIR/accounts-open-record" \
    --allow-placeholder-network-config > "$TMP_DIR/accounts-open-record-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a group/world-readable account record." >&2
    cat "$TMP_DIR/accounts-open-record-verify.out" >&2
    exit 1
fi
grep -q "account record permissions must be owner-only" "$TMP_DIR/accounts-open-record-verify.out"

cp -R "$ACCOUNT_TMP_DIR/accounts" "$TMP_DIR/accounts-filename-mismatch"
mv "$TMP_DIR/accounts-filename-mismatch/testuser.json" "$TMP_DIR/accounts-filename-mismatch/not_testuser.json"
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$TMP_DIR/accounts-filename-mismatch" \
    --allow-placeholder-network-config > "$TMP_DIR/accounts-filename-mismatch-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted an account filename that the Java auth service would not use." >&2
    cat "$TMP_DIR/accounts-filename-mismatch-verify.out" >&2
    exit 1
fi
grep -q "account record filename does not match username" "$TMP_DIR/accounts-filename-mismatch-verify.out"

cp -R "$ACCOUNT_TMP_DIR/accounts" "$TMP_DIR/accounts-invalid-username"
python3 - "$TMP_DIR/accounts-invalid-username/testuser.json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as source:
    record = json.load(source)
record["username"] = "Bad#Name"
with open(path, "w", encoding="utf-8") as target:
    json.dump(record, target, indent=2, sort_keys=True)
    target.write("\n")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$TMP_DIR/accounts-invalid-username" \
    --allow-placeholder-network-config > "$TMP_DIR/accounts-invalid-username-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted an invalid account username." >&2
    cat "$TMP_DIR/accounts-invalid-username-verify.out" >&2
    exit 1
fi
grep -q "account record has invalid username" "$TMP_DIR/accounts-invalid-username-verify.out"

cp -R "$ACCOUNT_TMP_DIR/accounts" "$TMP_DIR/accounts-bad-base64"
python3 - "$TMP_DIR/accounts-bad-base64/testuser.json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as source:
    record = json.load(source)
record["passwordHash"] = "not-base64!!!"
with open(path, "w", encoding="utf-8") as target:
    json.dump(record, target, indent=2, sort_keys=True)
    target.write("\n")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$TMP_DIR/accounts-bad-base64" \
    --allow-placeholder-network-config > "$TMP_DIR/accounts-bad-base64-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted invalid account passwordHash base64." >&2
    cat "$TMP_DIR/accounts-bad-base64-verify.out" >&2
    exit 1
fi
grep -q "account record has invalid base64 passwordHash" "$TMP_DIR/accounts-bad-base64-verify.out"

cp -R "$ACCOUNT_TMP_DIR/accounts" "$TMP_DIR/accounts-short-salt"
python3 - "$TMP_DIR/accounts-short-salt/testuser.json" <<'PY'
import base64
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as source:
    record = json.load(source)
record["passwordSalt"] = base64.b64encode(b"shortsal").decode("ascii")
with open(path, "w", encoding="utf-8") as target:
    json.dump(record, target, indent=2, sort_keys=True)
    target.write("\n")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$TMP_DIR/accounts-short-salt" \
    --allow-placeholder-network-config > "$TMP_DIR/accounts-short-salt-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted an account passwordSalt with the wrong byte length." >&2
    cat "$TMP_DIR/accounts-short-salt-verify.out" >&2
    exit 1
fi
grep -q "account record passwordSalt must decode to 16 bytes" "$TMP_DIR/accounts-short-salt-verify.out"

cp -R "$ACCOUNT_TMP_DIR/accounts" "$TMP_DIR/accounts-string-disabled"
python3 - "$TMP_DIR/accounts-string-disabled/testuser.json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as source:
    record = json.load(source)
record["disabled"] = "false"
with open(path, "w", encoding="utf-8") as target:
    json.dump(record, target, indent=2, sort_keys=True)
    target.write("\n")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$TMP_DIR/accounts-string-disabled" \
    --allow-placeholder-network-config > "$TMP_DIR/accounts-string-disabled-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a non-boolean account disabled flag." >&2
    cat "$TMP_DIR/accounts-string-disabled-verify.out" >&2
    exit 1
fi
grep -q "account record disabled field must be a boolean" "$TMP_DIR/accounts-string-disabled-verify.out"

cp -R "$ACCOUNT_TMP_DIR/accounts" "$TMP_DIR/accounts-string-roles"
python3 - "$TMP_DIR/accounts-string-roles/testuser.json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as source:
    record = json.load(source)
record["roles"] = "admin"
with open(path, "w", encoding="utf-8") as target:
    json.dump(record, target, indent=2, sort_keys=True)
    target.write("\n")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$TMP_DIR/accounts-string-roles" \
    --allow-placeholder-network-config > "$TMP_DIR/accounts-string-roles-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted non-array account roles metadata." >&2
    cat "$TMP_DIR/accounts-string-roles-verify.out" >&2
    exit 1
fi
grep -q "account record roles field must be an array" "$TMP_DIR/accounts-string-roles-verify.out"

cp -R "$ACCOUNT_TMP_DIR/accounts" "$TMP_DIR/accounts-invalid-allowed-character"
python3 - "$TMP_DIR/accounts-invalid-allowed-character/testuser.json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as source:
    record = json.load(source)
record["allowedCharacters"] = ["Not@Valid"]
with open(path, "w", encoding="utf-8") as target:
    json.dump(record, target, indent=2, sort_keys=True)
    target.write("\n")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$TMP_DIR/accounts-invalid-allowed-character" \
    --allow-placeholder-network-config > "$TMP_DIR/accounts-invalid-allowed-character-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted invalid account allowedCharacters metadata." >&2
    cat "$TMP_DIR/accounts-invalid-allowed-character-verify.out" >&2
    exit 1
fi
grep -q "account record allowedCharacters\\[0\\] has invalid character name" "$TMP_DIR/accounts-invalid-allowed-character-verify.out"

cp -R "$ACCOUNT_TMP_DIR/accounts" "$TMP_DIR/accounts-invalid-discord-user"
python3 - "$TMP_DIR/accounts-invalid-discord-user/testuser.json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as source:
    record = json.load(source)
record["discordUserId"] = "not-a-snowflake"
with open(path, "w", encoding="utf-8") as target:
    json.dump(record, target, indent=2, sort_keys=True)
    target.write("\n")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$TMP_DIR/accounts-invalid-discord-user" \
    --allow-placeholder-network-config > "$TMP_DIR/accounts-invalid-discord-user-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted invalid account discordUserId metadata." >&2
    cat "$TMP_DIR/accounts-invalid-discord-user-verify.out" >&2
    exit 1
fi
grep -q "account record discordUserId must be a numeric Discord snowflake string" "$TMP_DIR/accounts-invalid-discord-user-verify.out"

cp -R "$ACCOUNT_TMP_DIR/accounts" "$TMP_DIR/accounts-missing-password-policy"
python3 - "$TMP_DIR/accounts-missing-password-policy/testuser.json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as source:
    record = json.load(source)
record.pop("passwordPolicy", None)
with open(path, "w", encoding="utf-8") as target:
    json.dump(record, target, indent=2, sort_keys=True)
    target.write("\n")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$TMP_DIR/accounts-missing-password-policy" \
    --allow-placeholder-network-config > "$TMP_DIR/accounts-missing-password-policy-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted missing account passwordPolicy metadata." >&2
    cat "$TMP_DIR/accounts-missing-password-policy-verify.out" >&2
    exit 1
fi
grep -q "account record passwordPolicy must be an object" "$TMP_DIR/accounts-missing-password-policy-verify.out"

cp -R "$ACCOUNT_TMP_DIR/accounts" "$TMP_DIR/accounts-weak-password-policy"
python3 - "$TMP_DIR/accounts-weak-password-policy/testuser.json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as source:
    record = json.load(source)
record["passwordPolicy"]["allowWeakPassword"] = True
with open(path, "w", encoding="utf-8") as target:
    json.dump(record, target, indent=2, sort_keys=True)
    target.write("\n")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --accounts-dir "$TMP_DIR/accounts-weak-password-policy" \
    --allow-placeholder-network-config > "$TMP_DIR/accounts-weak-password-policy-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted weak account passwordPolicy metadata." >&2
    cat "$TMP_DIR/accounts-weak-password-policy-verify.out" >&2
    exit 1
fi
grep -q "account record passwordPolicy must not allow weak passwords" "$TMP_DIR/accounts-weak-password-policy-verify.out"

echo "Smoke-testing deployment verifier rejects archive-only client tampering..."
python3 - "$TMP_DIR/2006scape-client-from-config.zip" "$TMP_DIR/2006scape-client-from-config-tampered.zip" <<'PY'
import sys
import zipfile

source_path = sys.argv[1]
target_path = sys.argv[2]
tampered_name = "2006scape-client-from-config/README.txt"
with zipfile.ZipFile(source_path, "r") as source:
    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == tampered_name:
                data = b"tampered archive-only README\n"
            target.writestr(info, data)
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --archive "$TMP_DIR/2006scape-client-from-config-tampered.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/tampered-client-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted an archive-only client tamper." >&2
    cat "$TMP_DIR/tampered-client-verify.out" >&2
    exit 1
fi
grep -q "client archive entry does not match packaged folder file" "$TMP_DIR/tampered-client-verify.out"

echo "Smoke-testing deployment verifier rejects non-executable archive launcher metadata..."
python3 - "$TMP_DIR/2006scape-client-from-config.zip" "$TMP_DIR/2006scape-client-from-config-noexec.zip" <<'PY'
import stat
import sys
import zipfile

source_path = sys.argv[1]
target_path = sys.argv[2]
launcher_name = "2006scape-client-from-config/Run-2006Scape.command"
with zipfile.ZipFile(source_path, "r") as source:
    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for source_info in source.infolist():
            data = source.read(source_info.filename)
            target_info = zipfile.ZipInfo(source_info.filename, source_info.date_time)
            target_info.comment = source_info.comment
            target_info.extra = source_info.extra
            target_info.internal_attr = source_info.internal_attr
            target_info.external_attr = source_info.external_attr
            target_info.create_system = source_info.create_system
            if source_info.filename == launcher_name:
                target_info.create_system = 3
                target_info.external_attr = (stat.S_IFREG | 0o644) << 16
            target.writestr(target_info, data)
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --archive "$TMP_DIR/2006scape-client-from-config-noexec.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/noexec-archive-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a non-executable archive launcher." >&2
    cat "$TMP_DIR/noexec-archive-verify.out" >&2
    exit 1
fi
grep -q "client archive macOS launcher wrapper is not executable" "$TMP_DIR/noexec-archive-verify.out"

echo "Smoke-testing deployment verifier rejects symlink-type archive entries..."
python3 - "$TMP_DIR/2006scape-client-from-config.zip" "$TMP_DIR/2006scape-client-from-config-symlink-entry.zip" <<'PY'
import stat
import sys
import zipfile

source_path = sys.argv[1]
target_path = sys.argv[2]
launcher_name = "2006scape-client-from-config/run-macos-linux.sh"
with zipfile.ZipFile(source_path, "r") as source:
    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for source_info in source.infolist():
            data = source.read(source_info.filename)
            target_info = zipfile.ZipInfo(source_info.filename, source_info.date_time)
            target_info.comment = source_info.comment
            target_info.extra = source_info.extra
            target_info.internal_attr = source_info.internal_attr
            target_info.external_attr = source_info.external_attr
            target_info.create_system = source_info.create_system
            if source_info.filename == launcher_name:
                target_info.create_system = 3
                target_info.external_attr = (stat.S_IFLNK | 0o777) << 16
                data = b"2006scape-client.jar"
            target.writestr(target_info, data)
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --archive "$TMP_DIR/2006scape-client-from-config-symlink-entry.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/symlink-entry-archive-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a symlink-type archive entry." >&2
    cat "$TMP_DIR/symlink-entry-archive-verify.out" >&2
    exit 1
fi
grep -q "client archive file entry must be a regular file" "$TMP_DIR/symlink-entry-archive-verify.out"

echo "Smoke-testing deployment verifier rejects unexpected client package files..."
cp -R "$TMP_DIR/2006scape-client-from-config" "$TMP_DIR/2006scape-client-extra-file"
printf 'unexpected file\n' > "$TMP_DIR/2006scape-client-extra-file/install.sh"
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-extra-file" \
    --archive "$TMP_DIR/2006scape-client-from-config.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/extra-file-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted an extra client package file." >&2
    cat "$TMP_DIR/extra-file-verify.out" >&2
    exit 1
fi
grep -q "client package contains unexpected files" "$TMP_DIR/extra-file-verify.out"

echo "Smoke-testing deployment verifier rejects incomplete checksum manifests..."
cp -R "$TMP_DIR/2006scape-client-from-config" "$TMP_DIR/2006scape-client-missing-checksum"
grep -v 'README.txt$' "$TMP_DIR/2006scape-client-missing-checksum/SHA256SUMS" \
    > "$TMP_DIR/2006scape-client-missing-checksum/SHA256SUMS.new"
mv "$TMP_DIR/2006scape-client-missing-checksum/SHA256SUMS.new" \
    "$TMP_DIR/2006scape-client-missing-checksum/SHA256SUMS"
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-missing-checksum" \
    --archive "$TMP_DIR/2006scape-client-from-config.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/missing-checksum-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted an incomplete checksum manifest." >&2
    cat "$TMP_DIR/missing-checksum-verify.out" >&2
    exit 1
fi
grep -q "SHA256SUMS is missing entries" "$TMP_DIR/missing-checksum-verify.out"

echo "Smoke-testing deployment verifier rejects unsafe checksum paths..."
cp -R "$TMP_DIR/2006scape-client-from-config" "$TMP_DIR/2006scape-client-unsafe-checksum"
printf '0000000000000000000000000000000000000000000000000000000000000000  ../README.md\n' \
    >> "$TMP_DIR/2006scape-client-unsafe-checksum/SHA256SUMS"
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-unsafe-checksum" \
    --archive "$TMP_DIR/2006scape-client-from-config.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/unsafe-checksum-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted an unsafe checksum path." >&2
    cat "$TMP_DIR/unsafe-checksum-verify.out" >&2
    exit 1
fi
grep -q "SHA256SUMS contains unsafe entry" "$TMP_DIR/unsafe-checksum-verify.out"

echo "Smoke-testing deployment verifier rejects unexpected archive entries..."
python3 - "$TMP_DIR/2006scape-client-from-config.zip" "$TMP_DIR/2006scape-client-from-config-extra.zip" <<'PY'
import sys
import zipfile

source_path = sys.argv[1]
target_path = sys.argv[2]
with zipfile.ZipFile(source_path, "r") as source:
    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            target.writestr(info, source.read(info.filename))
        target.writestr("2006scape-client-from-config/install.sh", "unexpected archive entry\n")
PY
if scripts/verify-external-deployment.py \
    --config "2006Scape Server/ServerConfig.External.Sample.json" \
    --client-dist "$TMP_DIR/2006scape-client-from-config" \
    --archive "$TMP_DIR/2006scape-client-from-config-extra.zip" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config > "$TMP_DIR/extra-archive-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted an extra archive entry." >&2
    cat "$TMP_DIR/extra-archive-verify.out" >&2
    exit 1
fi
grep -q "client archive contains unexpected entries" "$TMP_DIR/extra-archive-verify.out"

echo "Preparing Discord-enabled deployment verifier config..."
python3 - "2006Scape Server/ServerConfig.External.Sample.json" "$TMP_DIR/discord-enabled-config.json" <<'PY'
import json
import sys

source_path = sys.argv[1]
target_path = sys.argv[2]
with open(source_path, "r", encoding="utf-8") as source:
    config = json.load(source)
config["agent_chat_discord_enabled"] = True
with open(target_path, "w", encoding="utf-8") as target:
    json.dump(config, target, indent=2)
    target.write("\n")
PY
DISCORD_CLIENT_DIST="$TMP_DIR/discord-enabled-client"
DISCORD_CLIENT_ARCHIVE="$TMP_DIR/discord-enabled-client.zip"
CLIENT_DIST_DIR="$DISCORD_CLIENT_DIST" \
CLIENT_ARCHIVE_PATH="$DISCORD_CLIENT_ARCHIVE" \
SKIP_BUILD=1 \
CLIENT_SERVER_CONFIG="$TMP_DIR/discord-enabled-config.json" \
CLIENT_CHECK_CRC=false \
CLIENT_SINGLE_ONDEMAND=true \
CLIENT_SCALE=1 \
CLIENT_SHOW_NAVBAR=true \
    scripts/package-client.sh
grep -Eq '^source_server_config_sha256=[0-9a-f]{64}$' "$DISCORD_CLIENT_DIST/MANIFEST.txt"
echo "Smoke-testing deployment verifier accepts tracked sample Discord secrets shape..."
cp "2006Scape Server/data/secrets.External.Sample.json" "$TMP_DIR/sample-discord-secrets.json"
chmod 600 "$TMP_DIR/sample-discord-secrets.json"
if scripts/verify-external-deployment.py \
    --config "$TMP_DIR/discord-enabled-config.json" \
    --client-dist "$DISCORD_CLIENT_DIST" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config \
    --secrets "$TMP_DIR/sample-discord-secrets.json" > "$TMP_DIR/sample-discord-secrets-no-placeholder-flag.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted placeholder Discord secrets without an explicit sample flag." >&2
    cat "$TMP_DIR/sample-discord-secrets-no-placeholder-flag.out" >&2
    exit 1
fi
grep -q "still contains a placeholder value" "$TMP_DIR/sample-discord-secrets-no-placeholder-flag.out"

scripts/verify-external-deployment.py \
    --config "$TMP_DIR/discord-enabled-config.json" \
    --client-dist "$DISCORD_CLIENT_DIST" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config \
    --allow-placeholder-discord-secrets \
    --secrets "2006Scape Server/data/secrets.External.Sample.json" > "$TMP_DIR/sample-discord-secrets-verify.out"
grep -q "ok: external deployment artifacts verified" "$TMP_DIR/sample-discord-secrets-verify.out"

cat > "$TMP_DIR/real-discord-secrets.json" <<'JSON'
{
  "agent-discord-bots": [
    {
      "agent": "MrFlame",
      "token": "test-token-one",
      "channelId": "555555555555555555",
      "allowedAgents": ["MrFlame", "MrGem"],
      "allowedPlayers": ["MrFlame"],
      "allowBroadcast": true
    }
  ]
}
JSON
chmod 600 "$TMP_DIR/real-discord-secrets.json"
scripts/verify-external-deployment.py \
    --config "$TMP_DIR/discord-enabled-config.json" \
    --client-dist "$DISCORD_CLIENT_DIST" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config \
    --secrets "$TMP_DIR/real-discord-secrets.json" > "$TMP_DIR/real-discord-secrets-verify.out"
grep -q "ok: external deployment artifacts verified" "$TMP_DIR/real-discord-secrets-verify.out"

cp "$TMP_DIR/real-discord-secrets.json" "$TMP_DIR/open-discord-secrets.json"
chmod 644 "$TMP_DIR/open-discord-secrets.json"
if scripts/verify-external-deployment.py \
    --config "$TMP_DIR/discord-enabled-config.json" \
    --client-dist "$DISCORD_CLIENT_DIST" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config \
    --secrets "$TMP_DIR/open-discord-secrets.json" > "$TMP_DIR/open-discord-secrets-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted group/world-readable Discord secrets." >&2
    cat "$TMP_DIR/open-discord-secrets-verify.out" >&2
    exit 1
fi
grep -q "Discord secrets permissions must be owner-only" "$TMP_DIR/open-discord-secrets-verify.out"

ln -s "$TMP_DIR/real-discord-secrets.json" "$TMP_DIR/symlink-discord-secrets.json"
if scripts/verify-external-deployment.py \
    --config "$TMP_DIR/discord-enabled-config.json" \
    --client-dist "$DISCORD_CLIENT_DIST" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config \
    --secrets "$TMP_DIR/symlink-discord-secrets.json" > "$TMP_DIR/symlink-discord-secrets-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted symlinked Discord secrets." >&2
    cat "$TMP_DIR/symlink-discord-secrets-verify.out" >&2
    exit 1
fi
grep -q "Discord secrets must not be a symlink" "$TMP_DIR/symlink-discord-secrets-verify.out"

echo "Smoke-testing deployment verifier rejects duplicate Discord agent bot configs..."
cat > "$TMP_DIR/duplicate-discord-secrets.json" <<'JSON'
{
  "agent-discord-bots": [
    {"agent": "MrFlame", "token": "test-token-one", "channelId": "123456"},
    {"agent": "mrflame", "token": "test-token-two", "channelId": "654321"}
  ]
}
JSON
chmod 600 "$TMP_DIR/duplicate-discord-secrets.json"
if scripts/verify-external-deployment.py \
    --config "$TMP_DIR/discord-enabled-config.json" \
    --client-dist "$DISCORD_CLIENT_DIST" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config \
    --secrets "$TMP_DIR/duplicate-discord-secrets.json" > "$TMP_DIR/duplicate-discord-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted duplicate Discord agent bot configs." >&2
    cat "$TMP_DIR/duplicate-discord-verify.out" >&2
    exit 1
fi
grep -q "duplicate Discord bot config for agent/profile" "$TMP_DIR/duplicate-discord-verify.out"

echo "Smoke-testing deployment verifier rejects malformed Discord routing filters..."
cat > "$TMP_DIR/malformed-discord-secrets.json" <<'JSON'
{
  "agent-discord-bots": [
    {
      "agent": "MrFlame",
      "token": "test-token-one",
      "channelId": "123456",
      "allowedAgents": {"MrGem": true}
    }
  ]
}
JSON
chmod 600 "$TMP_DIR/malformed-discord-secrets.json"
if scripts/verify-external-deployment.py \
    --config "$TMP_DIR/discord-enabled-config.json" \
    --client-dist "$DISCORD_CLIENT_DIST" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config \
    --secrets "$TMP_DIR/malformed-discord-secrets.json" > "$TMP_DIR/malformed-discord-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted malformed Discord routing filters." >&2
    cat "$TMP_DIR/malformed-discord-verify.out" >&2
    exit 1
fi
grep -q "allowedAgents must be a string or array of strings" "$TMP_DIR/malformed-discord-verify.out"

cat > "$TMP_DIR/empty-discord-allow-secrets.json" <<'JSON'
{
  "agent-discord-bots": [
    {
      "agent": "MrFlame",
      "token": "test-token-one",
      "channelId": "123456",
      "allowedPlayers": []
    }
  ]
}
JSON
chmod 600 "$TMP_DIR/empty-discord-allow-secrets.json"
if scripts/verify-external-deployment.py \
    --config "$TMP_DIR/discord-enabled-config.json" \
    --client-dist "$DISCORD_CLIENT_DIST" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config \
    --secrets "$TMP_DIR/empty-discord-allow-secrets.json" > "$TMP_DIR/empty-discord-allow-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted an empty Discord routing allow list." >&2
    cat "$TMP_DIR/empty-discord-allow-verify.out" >&2
    exit 1
fi
grep -q "allowedPlayers is empty; omit it for open routing" "$TMP_DIR/empty-discord-allow-verify.out"

cat > "$TMP_DIR/string-broadcast-discord-secrets.json" <<'JSON'
{
  "agent-discord-bots": [
    {
      "agent": "MrFlame",
      "token": "test-token-one",
      "channelId": "123456",
      "allowBroadcast": "false"
    }
  ]
}
JSON
chmod 600 "$TMP_DIR/string-broadcast-discord-secrets.json"
if scripts/verify-external-deployment.py \
    --config "$TMP_DIR/discord-enabled-config.json" \
    --client-dist "$DISCORD_CLIENT_DIST" \
    --accounts-dir "$ACCOUNT_TMP_DIR/accounts" \
    --allow-placeholder-network-config \
    --secrets "$TMP_DIR/string-broadcast-discord-secrets.json" > "$TMP_DIR/string-broadcast-discord-verify.out" 2>&1; then
    echo "verify-external-deployment.py unexpectedly accepted a non-boolean Discord broadcast flag." >&2
    cat "$TMP_DIR/string-broadcast-discord-verify.out" >&2
    exit 1
fi
grep -q "allowBroadcast must be a boolean" "$TMP_DIR/string-broadcast-discord-verify.out"

echo "Smoke-testing Discord bot probe helper with a fake Discord API..."
python3 - "$TMP_DIR/real-discord-secrets.json" <<'PY'
import importlib.util
import json
import os
import sys
from pathlib import Path

secrets_path = Path(sys.argv[1])

probe_path = Path("scripts/lib/discord_bot_probe.py")
probe_spec = importlib.util.spec_from_file_location("discord_bot_probe", probe_path)
probe = importlib.util.module_from_spec(probe_spec)
probe_spec.loader.exec_module(probe)

calls = []

def fake_discord_request(token, method, path, timeout=4.0, payload=None):
    calls.append((token, method, path, payload))
    assert token == "test-token-one", token
    if method == "GET" and path == "/users/@me":
        return {"id": "111111111111111111", "username": "ProbeBot", "bot": True}
    if method == "GET" and path == "/channels/555555555555555555":
        return {"id": "555555555555555555", "name": "agent-chat", "type": 0}
    if method == "GET" and path.startswith("/channels/555555555555555555/messages?"):
        assert "limit=5" in path, path
        assert "after=888888888888888888" in path, path
        return [
            {
                "id": "1000000000000000001",
                "timestamp": "2026-06-12T17:00:00.000000+00:00",
                "content": "server mirror proof marker",
                "author": {"id": "111111111111111111", "username": "ProbeBot", "bot": True},
            },
            {
                "id": "1000000000000000000",
                "timestamp": "2026-06-12T16:59:00.000000+00:00",
                "content": "server mirror proof marker",
                "author": {"id": "222222222222222222", "username": "HumanUser", "bot": False},
            },
        ]
    if method == "POST" and path == "/channels/555555555555555555/messages":
        assert payload["content"] == "@\u200beveryone smoke", payload
        return {"id": "999999999999999999"}
    raise AssertionError((method, path, payload))

probe.discord_api_request = fake_discord_request
results = probe.probe_discord_bots(
    secrets_path,
    timeout=1.0,
    send_test_message=True,
    message="@everyone smoke",
)
assert len(results) == 1, results
assert results[0]["agent"] == "MrFlame", results
assert results[0]["botUsername"] == "ProbeBot", results
assert results[0]["channelChecked"] is True, results
assert results[0]["messageSent"] is True, results
assert [call[1:3] for call in calls] == [
    ("GET", "/users/@me"),
    ("GET", "/channels/555555555555555555"),
    ("POST", "/channels/555555555555555555/messages"),
], calls

calls[:] = []
mirror_results = probe.verify_channel_messages(
    secrets_path,
    "server mirror proof marker",
    timeout=1.0,
    limit=5,
    after_id="888888888888888888",
)
assert mirror_results == [{
    "agent": "MrFlame",
    "botUserId": "111111111111111111",
    "botUsername": "ProbeBot",
    "channelId": "555555555555555555",
    "channelName": "agent-chat",
    "matched": 1,
    "latestMessageId": "1000000000000000001",
    "latestTimestamp": "2026-06-12T17:00:00.000000+00:00",
    "latestAuthorId": "111111111111111111",
    "latestAuthorBot": True,
    "latestContentPreview": "server mirror proof marker",
}], mirror_results
assert [call[1:3] for call in calls] == [
    ("GET", "/users/@me"),
    ("GET", "/channels/555555555555555555"),
    ("GET", "/channels/555555555555555555/messages?limit=5&after=888888888888888888"),
], calls

configs = probe.load_bot_configs(secrets_path, agents=["mrflame"])
assert len(configs) == 1 and configs[0]["agent"] == "MrFlame", configs

verify_path = Path("scripts/verify-external-deployment.py")
verify_spec = importlib.util.spec_from_file_location("verify_external_deployment", verify_path)
verify = importlib.util.module_from_spec(verify_spec)
sys.modules["discord_bot_probe"] = probe
verify_spec.loader.exec_module(verify)
verify.probe_discord_bots = lambda path, timeout=4.0: [{
    "agent": "MrFlame",
    "botUsername": "ProbeBot",
    "botUserId": "111111111111111111",
    "channelChecked": True,
    "channelId": "555555555555555555",
    "channelName": "agent-chat",
}]
checks = verify.verify_live_discord(secrets_path, 1.0)
assert checks == [
    "Discord bot MrFlame authenticated as ProbeBot (111111111111111111) and can read channel 555555555555555555 (agent-chat)"
], checks
PY

if command -v javap >/dev/null 2>&1; then
    echo "Checking representative Java classfile target versions..."
    javap -verbose -classpath "2006Scape Server/target/classes" com.rs2.auth.AccountAuthService \
        | grep -q "major version: 52"
    javap -verbose -classpath "2006Scape Server/target/classes" com.rs2.agent.AgentChatService \
        | grep -q "major version: 52"
    javap -verbose -classpath "2006Scape Server/target/classes" com.rs2.integrations.discord.DiscordAgentTransport \
        | grep -q "major version: 52"
    javap -verbose -classpath "2006Scape Client/target/classes" Main \
        | grep -q "major version: 52"
fi

if [[ "${RUN_DOCKER_BUILD:-0}" == "1" ]]; then
    echo "Running Docker Java 8 build..."
    launcher_docker_compose run --rm rsps-2006scape-build
else
    echo "Skipping Docker Java 8 build. Set RUN_DOCKER_BUILD=1 to run it when Docker is installed."
fi

echo "Network/auth/chat source validation passed."
