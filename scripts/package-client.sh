#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/launcher-common.sh"

ROOT_DIR="$(launcher_repo_root)"
CLIENT_DIR="$ROOT_DIR/2006Scape Client"
CLIENT_JAR="$CLIENT_DIR/target/client-1.0-jar-with-dependencies.jar"
DIST_DIR="${CLIENT_DIST_DIR:-$ROOT_DIR/dist/2006scape-client}"
ARCHIVE_PATH="${CLIENT_ARCHIVE_PATH:-$ROOT_DIR/dist/2006scape-client.zip}"
SERVER_CONFIG="${CLIENT_SERVER_CONFIG:-}"

CONFIG_SERVER_HOST=""
CONFIG_SERVER_PORT=""
CONFIG_SERVER_WORLD=""
CONFIG_HTTP_PORT=""
CONFIG_JAGGRAB_PORT=""
CONFIG_SECURE_TRANSPORT=""
CONFIG_CLIENT_CONNECT_HOST=""

if [[ -n "$SERVER_CONFIG" ]]; then
    PREFLIGHT_ARGS=("$SERVER_CONFIG")
    if [[ "${CLIENT_ALLOW_WILDCARD_BIND:-0}" == "1" ]]; then
        PREFLIGHT_ARGS+=("--allow-wildcard-bind")
    fi
    python3 "$SCRIPT_DIR/preflight-external-config.py" "${PREFLIGHT_ARGS[@]}"
    CONFIG_OUTPUT="$(python3 - "$SERVER_CONFIG" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
except OSError as exc:
    raise SystemExit("could not read server config {}: {}".format(path, exc))
except json.JSONDecodeError as exc:
    raise SystemExit("invalid JSON in server config {}: {}".format(path, exc))

def emit(key, value):
    if value is not None and str(value).strip():
        print("{}\t{}".format(key, str(value).strip()))

emit("SERVER_HOST", data.get("public_game_host"))
emit("SERVER_PORT", data.get("game_port"))
emit("SERVER_WORLD", data.get("world_id"))
emit("HTTP_PORT", data.get("http_port"))
emit("JAGGRAB_PORT", data.get("jaggrab_port"))
emit("SECURE_TRANSPORT", data.get("external_transport_mode"))
emit("CLIENT_CONNECT_HOST", data.get("client_connect_host"))
PY
)"
    while IFS=$'\t' read -r key value; do
        case "$key" in
            SERVER_HOST) CONFIG_SERVER_HOST="$value" ;;
            SERVER_PORT) CONFIG_SERVER_PORT="$value" ;;
            SERVER_WORLD) CONFIG_SERVER_WORLD="$value" ;;
            HTTP_PORT) CONFIG_HTTP_PORT="$value" ;;
            JAGGRAB_PORT) CONFIG_JAGGRAB_PORT="$value" ;;
            SECURE_TRANSPORT) CONFIG_SECURE_TRANSPORT="$value" ;;
            CLIENT_CONNECT_HOST) CONFIG_CLIENT_CONNECT_HOST="$value" ;;
        esac
    done <<< "$CONFIG_OUTPUT"
fi

SERVER_PORT="${CLIENT_SERVER_PORT:-${CONFIG_SERVER_PORT:-43594}}"
SERVER_WORLD="${CLIENT_WORLD:-${CONFIG_SERVER_WORLD:-1}}"
HTTP_PORT="${CLIENT_HTTP_PORT:-${CONFIG_HTTP_PORT:-8080}}"
JAGGRAB_PORT="${CLIENT_JAGGRAB_PORT:-${CONFIG_JAGGRAB_PORT:-43595}}"
CHECK_CRC="${CLIENT_CHECK_CRC:-true}"
SINGLE_ONDEMAND="${CLIENT_SINGLE_ONDEMAND:-true}"
CLIENT_SCALE="${CLIENT_SCALE:-2}"
SHOW_NAVBAR="${CLIENT_SHOW_NAVBAR:-false}"
SECURE_TRANSPORT="${CLIENT_SECURE_TRANSPORT:-${CONFIG_SECURE_TRANSPORT:-external transport not specified}}"
if [[ -z "${CLIENT_SERVER_HOST:-}" && "$(printf '%s' "$SECURE_TRANSPORT" | tr '[:upper:]' '[:lower:]')" == "client_tls_tunnel" ]]; then
    SERVER_HOST="${CONFIG_CLIENT_CONNECT_HOST:-127.0.0.1}"
else
    SERVER_HOST="${CLIENT_SERVER_HOST:-${CONFIG_SERVER_HOST:-localhost}}"
fi
PUBLIC_GAME_HOST="${CONFIG_SERVER_HOST:-$SERVER_HOST}"
GIT_REVISION="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || printf 'unknown')"
BUILD_TIME_UTC="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
SOURCE_SERVER_CONFIG_SHA256=""
if [[ -n "$SERVER_CONFIG" ]]; then
    SOURCE_SERVER_CONFIG_SHA256="$(shasum -a 256 "$SERVER_CONFIG" | awk '{print $1}')"
fi

lowercase() {
    printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

is_loopback_client_host() {
    local host
    host="$(lowercase "$1")"
    case "$host" in
        ""|localhost|127.*|::1|0:0:0:0:0:0:0:1)
            return 0
            ;;
    esac
    return 1
}

is_wildcard_client_host() {
    local host
    host="$(lowercase "$1")"
    case "$host" in
        "*"|0.0.0.0|::)
            return 0
            ;;
    esac
    return 1
}

is_local_or_unspecified_transport() {
    local transport
    transport="$(lowercase "$1")"
    case "$transport" in
        ""|local|"external transport not specified")
            return 0
            ;;
    esac
    return 1
}

is_allowed_external_transport() {
    local transport
    transport="$(lowercase "$1")"
    case "$transport" in
        direct_tcp|tailscale|wireguard|vpn|client_tls_tunnel)
            return 0
            ;;
    esac
    return 1
}

require_single_line_value() {
    local label="$1"
    local value="$2"
    python3 - "$label" "$value" <<'PY'
import sys

label = sys.argv[1]
value = sys.argv[2]
if any(ord(ch) < 32 for ch in value):
    raise SystemExit("{} must be a single-line value without control characters.".format(label))
PY
}

reject_symlinked_output_path() {
    local label="$1"
    local path="$2"
    python3 - "$label" "$path" <<'PY'
import sys
from pathlib import Path

label = sys.argv[1]
raw_path = sys.argv[2]
path = Path(raw_path)
if not raw_path.strip() or path == Path("/"):
    raise SystemExit("refusing to write {} to unsafe path: {}".format(label, raw_path))
if path.is_symlink():
    raise SystemExit("refusing to write {} through symlink path: {}".format(label, raw_path))

parent = path.parent
seen = set()
while parent not in seen:
    seen.add(parent)
    if parent.is_symlink():
        raise SystemExit("refusing to write {} through symlinked parent directory: {}".format(label, parent))
    if parent == parent.parent:
        break
    parent = parent.parent
PY
}

require_single_line_value "source server config" "$SERVER_CONFIG"
require_single_line_value "client server.host" "$SERVER_HOST"
require_single_line_value "client public_game_host" "$PUBLIC_GAME_HOST"
require_single_line_value "client server.port" "$SERVER_PORT"
require_single_line_value "client server.world" "$SERVER_WORLD"
require_single_line_value "client http.port" "$HTTP_PORT"
require_single_line_value "client jaggrab.port" "$JAGGRAB_PORT"
require_single_line_value "client secure.transport" "$SECURE_TRANSPORT"
require_single_line_value "client check_crc" "$CHECK_CRC"
require_single_line_value "client single_ondemand" "$SINGLE_ONDEMAND"
require_single_line_value "client scale" "$CLIENT_SCALE"
require_single_line_value "client show_navbar" "$SHOW_NAVBAR"

if is_wildcard_client_host "$SERVER_HOST"; then
    echo "Refusing to package a client with wildcard server.host=$SERVER_HOST." >&2
    echo "Use the reachable public/private/VPN host name clients should connect to." >&2
    exit 1
fi

if [[ "$(lowercase "$SECURE_TRANSPORT")" == "client_tls_tunnel" ]] && ! is_loopback_client_host "$SERVER_HOST"; then
    echo "Refusing to package client_tls_tunnel with non-loopback server.host=$SERVER_HOST." >&2
    echo "The Java client must connect to a local plaintext tunnel endpoint, usually 127.0.0.1." >&2
    exit 1
fi

if [[ "$(lowercase "$SECURE_TRANSPORT")" == "client_tls_tunnel" && -z "$SERVER_CONFIG" ]]; then
    echo "Refusing to package client_tls_tunnel without CLIENT_SERVER_CONFIG." >&2
    echo "Use a preflighted server config so public_game_host and tunnel ports are recorded in the package." >&2
    exit 1
fi

if ! is_loopback_client_host "$SERVER_HOST"; then
    if is_local_or_unspecified_transport "$SECURE_TRANSPORT"; then
        echo "Refusing to package a non-local client for $SERVER_HOST without external transport metadata." >&2
        echo "Set CLIENT_SECURE_TRANSPORT to direct_tcp, tailscale, wireguard, vpn, or client_tls_tunnel," >&2
        echo "or use CLIENT_SERVER_CONFIG with a preflighted external-player config." >&2
        exit 1
    elif ! is_allowed_external_transport "$SECURE_TRANSPORT"; then
        echo "Refusing to package a non-local client with unsupported secure.transport=$SECURE_TRANSPORT." >&2
        echo "Allowed non-local values: direct_tcp, tailscale, wireguard, vpn, client_tls_tunnel." >&2
        exit 1
    fi
fi

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
    "$SCRIPT_DIR/build-local.sh" -DskipTests
fi

launcher_require_file "$CLIENT_JAR" "Client jar is missing after build: $CLIENT_JAR"
reject_symlinked_output_path "client distribution directory" "$DIST_DIR"
reject_symlinked_output_path "client archive" "$ARCHIVE_PATH"

transport_guidance() {
    case "$(lowercase "$SECURE_TRANSPORT")" in
        tailscale)
            cat <<EOF
Transport setup:
  Connect Tailscale before launching the client. The configured server host is
  $PUBLIC_GAME_HOST, which should be reachable through the tailnet.
EOF
            ;;
        wireguard)
            cat <<EOF
Transport setup:
  Connect the WireGuard VPN profile before launching the client. The configured
  server host is $PUBLIC_GAME_HOST and should be reachable only through that VPN.
EOF
            ;;
        vpn)
            cat <<EOF
Transport setup:
  Connect the configured VPN before launching the client. The configured server
  host is $PUBLIC_GAME_HOST and should not be used over an unencrypted public path.
EOF
            ;;
        client_tls_tunnel)
            cat <<EOF
Transport setup:
  The packaged launchers try to start the bundled client-side stunnel config
  automatically when stunnel is installed:
    client-tls-tunnel/stunnel-client.conf
  The Java client connects locally to $SERVER_HOST, and stunnel carries that
  traffic over TLS to $PUBLIC_GAME_HOST. If the automatic start fails, start
  the tunnel manually with: stunnel client-tls-tunnel/stunnel-client.conf
EOF
            ;;
        direct_tcp)
            cat <<EOF
Transport setup:
  No VPN or client-side tunnel is required for this package. The Java client
  connects directly to $PUBLIC_GAME_HOST over plaintext TCP, so use this only
  for an operator-controlled public server with PBKDF2 account auth enabled.
EOF
            ;;
        local|"external transport not specified"|"")
            cat <<EOF
Transport setup:
  No external transport metadata is configured. This package is intended for
  local testing unless the operator supplies a separate encrypted network path.
EOF
            ;;
        *)
            cat <<EOF
Transport setup:
  Connect through the configured VPN or client-side tunnel before launching the
  client. Configured transport: $SECURE_TRANSPORT.
EOF
            ;;
    esac
}

TRANSPORT_GUIDANCE="$(transport_guidance)"

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

cp "$CLIENT_JAR" "$DIST_DIR/2006scape-client.jar"

cat > "$DIST_DIR/client.properties" <<EOF
server.host=$SERVER_HOST
server.port=$SERVER_PORT
server.world=$SERVER_WORLD
http.port=$HTTP_PORT
jaggrab.port=$JAGGRAB_PORT
secure.transport=$SECURE_TRANSPORT
check_crc=$CHECK_CRC
single_ondemand=$SINGLE_ONDEMAND
client.scale=$CLIENT_SCALE
show_navbar=$SHOW_NAVBAR
EOF

cat > "$DIST_DIR/run-macos-linux.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROPERTIES="$DIR/client.properties"

read_prop() {
    local key="$1"
    awk -F= -v key="$key" '$1 == key {print substr($0, length($1) + 2); exit}' "$PROPERTIES"
}

tcp_check_quiet() {
    local host="$1"
    local port="$2"
    if [[ -z "$host" || -z "$port" ]]; then
        return 1
    fi
    if command -v nc >/dev/null 2>&1; then
        nc -G 1 -z "$host" "$port" >/dev/null 2>&1 || nc -w 1 -z "$host" "$port" >/dev/null 2>&1
        return $?
    fi
    (echo >"/dev/tcp/$host/$port") >/dev/null 2>&1
}

wait_for_tunnel() {
    local host="$1"
    local port="$2"
    local attempt
    for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
        if tcp_check_quiet "$host" "$port"; then
            return 0
        fi
        sleep 1
    done
    return 1
}

STUNNEL_PID=""

cleanup_tunnel() {
    if [[ -n "$STUNNEL_PID" ]]; then
        kill "$STUNNEL_PID" >/dev/null 2>&1 || true
        wait "$STUNNEL_PID" >/dev/null 2>&1 || true
    fi
}

start_client_tls_tunnel_if_needed() {
    local host="$1"
    local port="$2"
    local config="$DIR/client-tls-tunnel/stunnel-client.conf"
    if tcp_check_quiet "$host" "$port"; then
        echo "Client TLS tunnel is already reachable at $host:$port."
        return 0
    fi
    if [[ ! -f "$config" ]]; then
        echo "This package uses client_tls_tunnel, but $config is missing." >&2
        exit 1
    fi
    if ! command -v stunnel >/dev/null 2>&1; then
        echo "This package uses client_tls_tunnel, but stunnel was not found on PATH." >&2
        echo "Install stunnel, or start the tunnel manually before launching:" >&2
        echo "  stunnel \"$config\"" >&2
        exit 1
    fi
    echo "Starting stunnel for encrypted 2006Scape transport..."
    stunnel "$config" &
    STUNNEL_PID="$!"
    trap cleanup_tunnel EXIT INT TERM
    if ! wait_for_tunnel "$host" "$port"; then
        echo "stunnel did not open $host:$port in time. Check client-tls-tunnel/stunnel-client.conf and server reachability." >&2
        exit 1
    fi
}

if ! command -v java >/dev/null 2>&1; then
    echo "Java is required to run 2006Scape." >&2
    echo "Install Java 8 or newer, then run this launcher again." >&2
    exit 1
fi
if [[ ! -f "$PROPERTIES" ]]; then
    echo "Missing client.properties next to this launcher." >&2
    exit 1
fi

SERVER_HOST="$(read_prop server.host)"
SERVER_PORT="$(read_prop server.port)"
TRANSPORT="$(read_prop secure.transport)"

if [[ "$(printf '%s' "$TRANSPORT" | tr '[:upper:]' '[:lower:]')" == "client_tls_tunnel" ]]; then
    start_client_tls_tunnel_if_needed "$SERVER_HOST" "$SERVER_PORT"
fi

set +e
java -jar "$DIR/2006scape-client.jar" -no-java-warnings -client-config "$PROPERTIES" "$@"
status=$?
set -e
exit "$status"
EOF
chmod +x "$DIST_DIR/run-macos-linux.sh"

cat > "$DIST_DIR/Run-2006Scape.command" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/run-macos-linux.sh" "$@"
EOF
chmod +x "$DIST_DIR/Run-2006Scape.command"

{
    printf '%s\r\n' '@echo off'
    printf '%s\r\n' 'setlocal EnableExtensions'
    printf '%s\r\n' 'set DIR=%~dp0'
    printf '%s\r\n' 'set PROPERTIES=%DIR%client.properties'
    printf '%s\r\n' 'where java >nul 2>nul'
    printf '%s\r\n' 'if errorlevel 1 ('
    printf '%s\r\n' '    echo Java is required to run 2006Scape.'
    printf '%s\r\n' '    echo Install Java 8 or newer, then run this launcher again.'
    printf '%s\r\n' '    exit /b 1'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'if not exist "%PROPERTIES%" ('
    printf '%s\r\n' '    echo Missing client.properties next to this launcher.'
    printf '%s\r\n' '    exit /b 1'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'for /f "usebackq tokens=1,* delims==" %%A in ("%PROPERTIES%") do ('
    printf '%s\r\n' '    if "%%A"=="server.host" set SERVER_HOST=%%B'
    printf '%s\r\n' '    if "%%A"=="server.port" set SERVER_PORT=%%B'
    printf '%s\r\n' '    if "%%A"=="secure.transport" set TRANSPORT=%%B'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'if /I "%TRANSPORT%"=="client_tls_tunnel" call :ensuretunnel'
    printf '%s\r\n' 'if errorlevel 1 exit /b 1'
    printf '%s\r\n' 'java -jar "%DIR%2006scape-client.jar" -no-java-warnings -client-config "%PROPERTIES%" %*'
    printf '%s\r\n' 'exit /b %ERRORLEVEL%'
    printf '%s\r\n' ':ensuretunnel'
    printf '%s\r\n' 'set TUNNEL_CONFIG=%DIR%client-tls-tunnel\stunnel-client.conf'
    printf '%s\r\n' 'if not exist "%TUNNEL_CONFIG%" ('
    printf '%s\r\n' '    echo This package uses client_tls_tunnel, but %TUNNEL_CONFIG% is missing.'
    printf '%s\r\n' '    exit /b 1'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'call :tcpcheckquiet "%SERVER_HOST%" "%SERVER_PORT%"'
    printf '%s\r\n' 'if not errorlevel 1 ('
    printf '%s\r\n' '    echo Client TLS tunnel is already reachable at %SERVER_HOST%:%SERVER_PORT%.'
    printf '%s\r\n' '    exit /b 0'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'where stunnel >nul 2>nul'
    printf '%s\r\n' 'if errorlevel 1 ('
    printf '%s\r\n' '    echo This package uses client_tls_tunnel, but stunnel was not found on PATH.'
    printf '%s\r\n' '    echo Install stunnel, or start the tunnel manually before launching:'
    printf '%s\r\n' '    echo   stunnel "%TUNNEL_CONFIG%"'
    printf '%s\r\n' '    exit /b 1'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'echo Starting stunnel for encrypted 2006Scape transport...'
    printf '%s\r\n' 'start "2006Scape stunnel" /min stunnel "%TUNNEL_CONFIG%"'
    printf '%s\r\n' 'for /L %%I in (1,1,15) do ('
    printf '%s\r\n' '    call :tcpcheckquiet "%SERVER_HOST%" "%SERVER_PORT%"'
    printf '%s\r\n' '    if not errorlevel 1 exit /b 0'
    printf '%s\r\n' '    ping -n 2 127.0.0.1 >nul'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'echo stunnel did not open %SERVER_HOST%:%SERVER_PORT% in time. Check client-tls-tunnel\stunnel-client.conf and server reachability.'
    printf '%s\r\n' 'exit /b 1'
    printf '%s\r\n' ':tcpcheckquiet'
    printf '%s\r\n' 'set HOST=%~1'
    printf '%s\r\n' 'set PORT=%~2'
    printf '%s\r\n' 'if "%HOST%"=="" exit /b 1'
    printf '%s\r\n' 'if "%PORT%"=="" exit /b 1'
    printf '%s\r\n' 'where powershell >nul 2>nul'
    printf '%s\r\n' 'if errorlevel 1 exit /b 1'
    printf '%s\r\n' 'powershell -NoProfile -ExecutionPolicy Bypass -Command "$client = New-Object Net.Sockets.TcpClient; try { $async = $client.BeginConnect(''%HOST%'', [int]''%PORT%'', $null, $null); if (-not $async.AsyncWaitHandle.WaitOne(1500, $false)) { throw ''timeout'' }; $client.EndConnect($async); exit 0 } catch { exit 1 } finally { $client.Close() }"'
    printf '%s\r\n' 'exit /b %ERRORLEVEL%'
} > "$DIST_DIR/run-windows.bat"

cat > "$DIST_DIR/check-setup-macos-linux.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROPERTIES="$DIR/client.properties"

read_prop() {
    local key="$1"
    awk -F= -v key="$key" '$1 == key {print substr($0, length($1) + 2); exit}' "$PROPERTIES"
}

tcp_check() {
    local label="$1"
    local host="$2"
    local port="$3"
    if [[ -z "$host" || -z "$port" ]]; then
        echo "$label: skipped; host or port missing"
        return 0
    fi
    if ! command -v nc >/dev/null 2>&1; then
        echo "$label: skipped; install nc/netcat to test TCP reachability"
        return 0
    fi
    if nc -G 3 -z "$host" "$port" >/dev/null 2>&1 || nc -w 3 -z "$host" "$port" >/dev/null 2>&1; then
        echo "$label: OK ($host:$port)"
        return 0
    fi
    echo "$label: FAILED ($host:$port)"
    return 1
}

tcp_check_quiet() {
    local host="$1"
    local port="$2"
    if [[ -z "$host" || -z "$port" ]]; then
        return 1
    fi
    if command -v nc >/dev/null 2>&1; then
        nc -G 1 -z "$host" "$port" >/dev/null 2>&1 || nc -w 1 -z "$host" "$port" >/dev/null 2>&1
        return $?
    fi
    (echo >"/dev/tcp/$host/$port") >/dev/null 2>&1
}

wait_for_tunnel() {
    local host="$1"
    local port="$2"
    local attempt
    for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
        if tcp_check_quiet "$host" "$port"; then
            return 0
        fi
        sleep 1
    done
    return 1
}

STUNNEL_PID=""

cleanup_tunnel() {
    if [[ -n "$STUNNEL_PID" ]]; then
        kill "$STUNNEL_PID" >/dev/null 2>&1 || true
        wait "$STUNNEL_PID" >/dev/null 2>&1 || true
    fi
}

start_client_tls_tunnel_for_setup() {
    local host="$1"
    local port="$2"
    local config="$DIR/client-tls-tunnel/stunnel-client.conf"
    if tcp_check_quiet "$host" "$port"; then
        echo "Client TLS tunnel is already reachable at $host:$port."
        return 0
    fi
    if [[ ! -f "$config" ]]; then
        echo "This package uses client_tls_tunnel, but $config is missing." >&2
        return 1
    fi
    if ! command -v stunnel >/dev/null 2>&1; then
        echo "This package uses client_tls_tunnel, but stunnel was not found on PATH." >&2
        echo "Install stunnel, or start the tunnel manually before running this setup check:" >&2
        echo "  stunnel \"$config\"" >&2
        return 1
    fi
    echo "Starting stunnel temporarily for setup checks..."
    stunnel "$config" &
    STUNNEL_PID="$!"
    trap cleanup_tunnel EXIT INT TERM
    if ! wait_for_tunnel "$host" "$port"; then
        echo "stunnel did not open $host:$port in time. Check client-tls-tunnel/stunnel-client.conf and server reachability." >&2
        return 1
    fi
}

if ! command -v java >/dev/null 2>&1; then
    echo "Java is required to run 2006Scape." >&2
    echo "Install Java 8 or newer, then run this checker again." >&2
    exit 1
fi

if [[ ! -f "$PROPERTIES" ]]; then
    echo "Missing client.properties next to this setup checker." >&2
    exit 1
fi

SERVER_HOST="$(read_prop server.host)"
SERVER_PORT="$(read_prop server.port)"
HTTP_PORT="$(read_prop http.port)"
JAGGRAB_PORT="$(read_prop jaggrab.port)"
TRANSPORT="$(read_prop secure.transport)"

echo "Java:"
java -version 2>&1 | sed 's/^/  /'
echo
echo "Client configuration:"
echo "  server.host=$SERVER_HOST"
echo "  server.port=$SERVER_PORT"
echo "  http.port=$HTTP_PORT"
echo "  jaggrab.port=$JAGGRAB_PORT"
echo "  secure.transport=$TRANSPORT"
echo

status=0
case "$(printf '%s' "$TRANSPORT" | tr '[:upper:]' '[:lower:]')" in
    client_tls_tunnel)
        echo "Transport note: this checker starts the bundled stunnel config temporarily when stunnel is installed."
        start_client_tls_tunnel_for_setup "$SERVER_HOST" "$SERVER_PORT" || status=1
        ;;
    direct_tcp)
        echo "Transport note: direct_tcp connects directly to the public host over plaintext TCP."
        ;;
    tailscale|wireguard|vpn)
        echo "Transport note: connect the configured private network before running the client."
        ;;
esac

tcp_check "Game TCP check" "$SERVER_HOST" "$SERVER_PORT" || status=1
tcp_check "HTTP cache TCP check" "$SERVER_HOST" "$HTTP_PORT" || status=1
tcp_check "JAGGRAB TCP check" "$SERVER_HOST" "$JAGGRAB_PORT" || status=1

if [[ "$status" -eq 0 ]]; then
    echo "Setup check complete."
else
    echo "One or more TCP checks failed. Verify the server is online and transport setup is connected." >&2
fi
exit "$status"
EOF
chmod +x "$DIST_DIR/check-setup-macos-linux.sh"

cat > "$DIST_DIR/Check-Setup.command" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/check-setup-macos-linux.sh" "$@"
EOF
chmod +x "$DIST_DIR/Check-Setup.command"

{
    printf '%s\r\n' '@echo off'
    printf '%s\r\n' 'setlocal EnableExtensions'
    printf '%s\r\n' 'set DIR=%~dp0'
    printf '%s\r\n' 'set PROPERTIES=%DIR%client.properties'
    printf '%s\r\n' 'where java >nul 2>nul'
    printf '%s\r\n' 'if errorlevel 1 ('
    printf '%s\r\n' '    echo Java is required to run 2006Scape.'
    printf '%s\r\n' '    echo Install Java 8 or newer, then run this checker again.'
    printf '%s\r\n' '    exit /b 1'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'if not exist "%PROPERTIES%" ('
    printf '%s\r\n' '    echo Missing client.properties next to this setup checker.'
    printf '%s\r\n' '    exit /b 1'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'for /f "usebackq tokens=1,* delims==" %%A in ("%PROPERTIES%") do ('
    printf '%s\r\n' '    if "%%A"=="server.host" set SERVER_HOST=%%B'
    printf '%s\r\n' '    if "%%A"=="server.port" set SERVER_PORT=%%B'
    printf '%s\r\n' '    if "%%A"=="http.port" set HTTP_PORT=%%B'
    printf '%s\r\n' '    if "%%A"=="jaggrab.port" set JAGGRAB_PORT=%%B'
    printf '%s\r\n' '    if "%%A"=="secure.transport" set TRANSPORT=%%B'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'echo Java:'
    printf '%s\r\n' 'java -version'
    printf '%s\r\n' 'echo.'
    printf '%s\r\n' 'echo Client configuration:'
    printf '%s\r\n' 'echo   server.host=%SERVER_HOST%'
    printf '%s\r\n' 'echo   server.port=%SERVER_PORT%'
    printf '%s\r\n' 'echo   http.port=%HTTP_PORT%'
    printf '%s\r\n' 'echo   jaggrab.port=%JAGGRAB_PORT%'
    printf '%s\r\n' 'echo   secure.transport=%TRANSPORT%'
    printf '%s\r\n' 'echo.'
    printf '%s\r\n' 'if /I "%TRANSPORT%"=="client_tls_tunnel" echo Transport note: the launcher can start stunnel automatically, but this Windows checker expects the local tunnel endpoint to be reachable first.'
    printf '%s\r\n' 'if /I "%TRANSPORT%"=="direct_tcp" echo Transport note: direct_tcp connects directly to the public host over plaintext TCP.'
    printf '%s\r\n' 'if /I "%TRANSPORT%"=="tailscale" echo Transport note: connect the configured private network before running the client.'
    printf '%s\r\n' 'if /I "%TRANSPORT%"=="wireguard" echo Transport note: connect the configured private network before running the client.'
    printf '%s\r\n' 'if /I "%TRANSPORT%"=="vpn" echo Transport note: connect the configured private network before running the client.'
    printf '%s\r\n' 'set STATUS=0'
    printf '%s\r\n' 'call :tcpcheck "Game TCP check" "%SERVER_HOST%" "%SERVER_PORT%"'
    printf '%s\r\n' 'if errorlevel 1 set STATUS=1'
    printf '%s\r\n' 'call :tcpcheck "HTTP cache TCP check" "%SERVER_HOST%" "%HTTP_PORT%"'
    printf '%s\r\n' 'if errorlevel 1 set STATUS=1'
    printf '%s\r\n' 'call :tcpcheck "JAGGRAB TCP check" "%SERVER_HOST%" "%JAGGRAB_PORT%"'
    printf '%s\r\n' 'if errorlevel 1 set STATUS=1'
    printf '%s\r\n' 'if "%STATUS%"=="0" ('
    printf '%s\r\n' '    echo Setup check complete.'
    printf '%s\r\n' ') else ('
    printf '%s\r\n' '    echo One or more TCP checks failed. Verify the server is online and transport setup is connected.'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'exit /b %STATUS%'
    printf '%s\r\n' ':tcpcheck'
    printf '%s\r\n' 'set LABEL=%~1'
    printf '%s\r\n' 'set HOST=%~2'
    printf '%s\r\n' 'set PORT=%~3'
    printf '%s\r\n' 'if "%HOST%"=="" ('
    printf '%s\r\n' '    echo %LABEL%: skipped; host missing'
    printf '%s\r\n' '    exit /b 0'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'if "%PORT%"=="" ('
    printf '%s\r\n' '    echo %LABEL%: skipped; port missing'
    printf '%s\r\n' '    exit /b 0'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'where powershell >nul 2>nul'
    printf '%s\r\n' 'if errorlevel 1 ('
    printf '%s\r\n' '    echo %LABEL%: skipped; PowerShell is required for TCP checks.'
    printf '%s\r\n' '    exit /b 0'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'powershell -NoProfile -ExecutionPolicy Bypass -Command "$client = New-Object Net.Sockets.TcpClient; try { $async = $client.BeginConnect(''%HOST%'', [int]''%PORT%'', $null, $null); if (-not $async.AsyncWaitHandle.WaitOne(3000, $false)) { throw ''timeout'' }; $client.EndConnect($async); exit 0 } catch { exit 1 } finally { $client.Close() }"'
    printf '%s\r\n' 'if errorlevel 1 ('
    printf '%s\r\n' '    echo %LABEL%: FAILED (%HOST%:%PORT%)'
    printf '%s\r\n' '    exit /b 1'
    printf '%s\r\n' ')'
    printf '%s\r\n' 'echo %LABEL%: OK (%HOST%:%PORT%)'
    printf '%s\r\n' 'exit /b 0'
} > "$DIST_DIR/check-setup-windows.bat"

cat > "$DIST_DIR/README.txt" <<EOF
2006Scape Client

Check setup:
  macOS: double-click Check-Setup.command, or run ./check-setup-macos-linux.sh from Terminal.
  Linux: ./check-setup-macos-linux.sh
  Windows: double-click check-setup-windows.bat or run it from Command Prompt.
  The checker verifies Java, prints client.properties, and attempts TCP checks
  without logging in or changing server state.

Run:
  macOS: double-click Run-2006Scape.command, or run ./run-macos-linux.sh from Terminal.
  Linux: ./run-macos-linux.sh
  Windows: double-click run-windows.bat or run it from Command Prompt.
  For client_tls_tunnel packages, the launchers try to start the bundled
  stunnel config automatically when stunnel is installed.
  macOS/Linux setup checker: can start stunnel temporarily for TCP checks.
  Windows setup checker: expects the local tunnel endpoint to be reachable first.

Java:
  Install Java 8 or newer first. The launchers print a short error if Java
  is not available on PATH.
  Packaged launchers suppress the legacy Parabot-focused Java-version warning
  dialogs; use a current 64-bit Java runtime for normal play.
  The packaged client defaults to the repo-native 2x game scale with the old
  web navbar hidden. That keeps the larger testing window while preserving
  normal in-game mouse coordinates on macOS and other HiDPI desktops.

Server:
  host: $SERVER_HOST
  game port: $SERVER_PORT
  HTTP cache port: $HTTP_PORT
  world: $SERVER_WORLD
  JAGGRAB/cache port: $JAGGRAB_PORT
  expected external transport: $SECURE_TRANSPORT
  public game host: $PUBLIC_GAME_HOST

$TRANSPORT_GUIDANCE

Login:
  Use the username and password provided by the server operator.
  Do not use a RuneScape.com password or reuse passwords from other services.
  For direct_tcp packages, use a password unique to this 2006Scape server because
  the legacy game/cache protocol is plaintext to the public host.

AI agent mode:
  The in-game /agent command needs the server-side agent bridge on port 43610,
  but that bridge must stay private and loopback-only. For remote servers, use
  an operator-approved SSH/VPN/tunnel path to 127.0.0.1:43610 before trying
  /agent status, /agent key, or /agent <task>. Do not expose port 43610 publicly.

Edit client.properties only if the server host or ports change.
If this package uses Tailscale, WireGuard, or VPN, connect that transport first.
If this package uses client_tls_tunnel, the launcher starts stunnel when it can; otherwise start it manually first.
If this package uses direct_tcp, no VPN/tunnel is expected; the game/cache protocol is plaintext to the public host.
EOF

if [[ "$(lowercase "$SECURE_TRANSPORT")" == "client_tls_tunnel" ]]; then
    TUNNEL_RENDER_ARGS=(
        --config "$SERVER_CONFIG"
        --output-dir "$DIST_DIR/client-tls-tunnel"
        --client-only
    )
    if [[ "${CLIENT_ALLOW_PLACEHOLDER_NETWORK_CONFIG:-0}" == "1" ]]; then
        TUNNEL_RENDER_ARGS+=(--allow-placeholder-network-config)
    fi
    python3 "$SCRIPT_DIR/render-client-tls-tunnel-config.py" \
        "${TUNNEL_RENDER_ARGS[@]}"
fi

JAR_SHA256="$(shasum -a 256 "$DIST_DIR/2006scape-client.jar" | awk '{print $1}')"

cat > "$DIST_DIR/MANIFEST.txt" <<EOF
2006Scape Client Package

build_time_utc=$BUILD_TIME_UTC
git_revision=$GIT_REVISION
source_server_config=$SERVER_CONFIG
source_server_config_sha256=$SOURCE_SERVER_CONFIG_SHA256
server_host=$SERVER_HOST
public_game_host=$PUBLIC_GAME_HOST
server_port=$SERVER_PORT
server_world=$SERVER_WORLD
http_port=$HTTP_PORT
jaggrab_port=$JAGGRAB_PORT
check_crc=$CHECK_CRC
single_ondemand=$SINGLE_ONDEMAND
client_scale=$CLIENT_SCALE
show_navbar=$SHOW_NAVBAR
expected_external_transport=$SECURE_TRANSPORT
jar_sha256=$JAR_SHA256

Security note:
The legacy Java client speaks plaintext to the configured host and ports.
External play should use an encrypted transport boundary such as Tailscale,
WireGuard, VPN, or a paired client/server TLS tunnel when practical.
direct_tcp intentionally connects directly over plaintext TCP to the public host.
EOF

(
    cd "$DIST_DIR"
    CHECKSUM_FILES=(
        2006scape-client.jar \
        Check-Setup.command \
        Run-2006Scape.command \
        client.properties \
        check-setup-macos-linux.sh \
        check-setup-windows.bat \
        run-macos-linux.sh \
        run-windows.bat \
        README.txt \
        MANIFEST.txt
    )
    if [[ -f client-tls-tunnel/README.txt ]]; then
        CHECKSUM_FILES+=(client-tls-tunnel/README.txt)
    fi
    if [[ -f client-tls-tunnel/stunnel-client.conf ]]; then
        CHECKSUM_FILES+=(client-tls-tunnel/stunnel-client.conf)
    fi
    shasum -a 256 "${CHECKSUM_FILES[@]}" > SHA256SUMS
)

mkdir -p "$(dirname "$ARCHIVE_PATH")"
rm -f "$ARCHIVE_PATH"
python3 - "$DIST_DIR" "$ARCHIVE_PATH" <<'PY'
import stat
import sys
import zipfile
from pathlib import Path

dist_dir = Path(sys.argv[1]).resolve()
archive_path = Path(sys.argv[2]).resolve()
root_dir = dist_dir.parent

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
        arcname = str(path.relative_to(root_dir))
        if path.is_dir():
            archive.writestr(zip_info(path, arcname.rstrip("/") + "/"), b"")
        else:
            archive.writestr(zip_info(path, arcname), path.read_bytes())
PY

echo "Packaged client in $DIST_DIR"
echo "Packaged client archive at $ARCHIVE_PATH"
