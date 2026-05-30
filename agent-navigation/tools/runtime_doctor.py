#!/usr/bin/env python3
"""Runtime helper for local 2006Scape agent work.

This script wraps the fragile parts of the documented startup flow: detached
server/client launch, bridge session claim, verification, and route recorder
control. It intentionally never prints bridge tokens.
"""

import argparse
import json
import os
import signal
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
NAV_ROOT = SCRIPT_DIR.parent
REPO_ROOT = NAV_ROOT.parent
LOCAL_DIR = NAV_ROOT / ".local"
SESSION_FILE = LOCAL_DIR / "rsbridge-session.json"
SERVER_PID_FILE = LOCAL_DIR / "server.pid"
CLIENT_PID_FILE = LOCAL_DIR / "client.pid"
SERVER_LOG = Path("/tmp/2006scape-server.log")
CLIENT_LOG = Path("/tmp/2006scape-client.log")
SERVER_PORT = 43594
BRIDGE_PORT = 43610
DEFAULT_USER = "MrFlame"
ROUTE_RECORDER = SCRIPT_DIR / "route_recorder.py"
OBSERVE_SLIM = SCRIPT_DIR / "observe-slim.sh"
NAVDB = SCRIPT_DIR / "navdb.py"


def safe_profile(value):
    text = "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum() or ch in ("-", "_"))
    return text or "default"


def default_user():
    return os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or DEFAULT_USER


def is_default_user(user):
    return safe_profile(user) == safe_profile(DEFAULT_USER)


def session_file_for_user(user):
    override = os.environ.get("RSBRIDGE_SESSION_FILE")
    if override:
        return Path(override).expanduser()
    if is_default_user(user):
        return SESSION_FILE
    return LOCAL_DIR / "rsbridge-session-{}.json".format(safe_profile(user))


def password_file_for_user(user):
    return REPO_ROOT / "2006Scape Server" / "data" / "characters" / "{}.txt".format(safe_profile(user))


def client_pid_file_for_user(user):
    if is_default_user(user):
        return CLIENT_PID_FILE
    return LOCAL_DIR / "client-{}.pid".format(safe_profile(user))


def client_log_for_user(user):
    if is_default_user(user):
        return CLIENT_LOG
    return Path("/tmp/2006scape-client-{}.log".format(safe_profile(user)))


def resolve_session_file(args):
    value = getattr(args, "session_file", None)
    if value:
        return Path(value).expanduser()
    return session_file_for_user(getattr(args, "user", DEFAULT_USER))


def resolve_password_file(args):
    value = getattr(args, "password_file", None)
    if value:
        return Path(value).expanduser()
    return password_file_for_user(getattr(args, "user", DEFAULT_USER))


def resolve_client_pid_file(args):
    value = getattr(args, "client_pid_file", None)
    if value:
        return Path(value).expanduser()
    return client_pid_file_for_user(getattr(args, "user", DEFAULT_USER))


def resolve_client_log(args):
    value = getattr(args, "client_log", None)
    if value:
        return Path(value).expanduser()
    return client_log_for_user(getattr(args, "user", DEFAULT_USER))


def port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port(port, timeout, label):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(port):
            return True
        time.sleep(0.5)
    raise SystemExit("{} did not open on 127.0.0.1:{} within {}s".format(label, port, timeout))


def process_exists(pid):
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except ProcessLookupError:
        return False


def read_pid(path):
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def run_cmd(cmd, cwd=REPO_ROOT, check=True, capture=False, env=None):
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        env=env,
    )
    if check and proc.returncode != 0:
        if capture:
            sys.stderr.write(proc.stderr or proc.stdout or "")
        raise SystemExit(proc.returncode)
    return proc


def print_json(data):
    print(json.dumps(data, sort_keys=True, separators=(",", ":")))


def read_session_summary(session_file):
    if not session_file.exists():
        return {"exists": False}
    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"exists": True, "validJson": False, "error": str(exc)}
    return {
        "exists": True,
        "validJson": True,
        "sessionId": data.get("sessionId", ""),
        "playerId": data.get("playerId"),
        "playerName": data.get("playerName", ""),
        "createdAt": data.get("createdAt"),
        "hasToken": bool(data.get("token")),
    }


def cmd_status(args):
    server_pid = read_pid(SERVER_PID_FILE)
    client_pid_file = resolve_client_pid_file(args)
    client_pid = read_pid(client_pid_file)
    session_file = resolve_session_file(args)
    client_log = resolve_client_log(args)
    summary = {
        "profile": args.user,
        "serverPortOpen": port_open(SERVER_PORT),
        "bridgePortOpen": port_open(BRIDGE_PORT),
        "serverPidFile": str(SERVER_PID_FILE),
        "serverPid": server_pid,
        "serverPidAlive": process_exists(server_pid) if server_pid else False,
        "clientPidFile": str(client_pid_file),
        "clientPid": client_pid,
        "clientPidAlive": process_exists(client_pid) if client_pid else False,
        "sessionFile": read_session_summary(session_file),
        "serverLog": str(SERVER_LOG),
        "clientLog": str(client_log),
    }
    if args.observe:
        env = os.environ.copy()
        env["RS_PROFILE"] = args.user
        env["RSBRIDGE_SESSION_FILE"] = str(session_file)
        proc = run_cmd([str(OBSERVE_SLIM)], check=False, capture=True, env=env)
        summary["observeSlim"] = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "outputPreview": (proc.stdout or proc.stderr or "").strip()[:300],
        }
    print_json(summary)
    return 0


def stop_by_patterns(patterns):
    for pattern in patterns:
        proc = subprocess.run(["pkill", "-f", pattern], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode not in (0, 1):
            text = "{} {}".format(proc.stdout or "", proc.stderr or "").lower()
            if "cannot get process list" in text or "sysmond service not found" in text:
                continue
            raise SystemExit("pkill failed for pattern {!r} with exit {}".format(pattern, proc.returncode))


def stop_pid_file(path, label):
    pid = read_pid(path)
    if not pid:
        path.unlink(missing_ok=True)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except PermissionError:
        raise SystemExit("permission denied stopping {} pid={}; stop it from the owning shell".format(label, pid))
    except ProcessLookupError:
        pass
    path.unlink(missing_ok=True)


def stop_runtime(include_server, include_client, session_file=SESSION_FILE, client_pid_file=CLIENT_PID_FILE,
                 broad_client=True):
    if include_client:
        if broad_client:
            stop_by_patterns(
                [
                    "codex app-server --listen stdio://",
                    "client-1.0-jar-with-dependencies.jar",
                ]
            )
            stop_pid_file(CLIENT_PID_FILE, "default client")
            if client_pid_file != CLIENT_PID_FILE:
                stop_pid_file(client_pid_file, "profile client")
        else:
            stop_pid_file(client_pid_file, "profile client")
    if include_server:
        stop_by_patterns(
            [
                "server-1.0-jar-with-dependencies.jar",
                "2006scape-run/server-",
            ]
        )
        stop_pid_file(SERVER_PID_FILE, "server")
    session_file.unlink(missing_ok=True)
    time.sleep(1.0)


def build_runtime(args):
    if args.test_passive_trace:
        run_cmd(["mvn", "-q", "-pl", "2006Scape Server", "-Dtest=AgentPassiveTraceLogTest", "test"])
    if args.build:
        run_cmd(["mvn", "-q", "-DskipTests", "package"])


def launch_detached(cmd, log_path, pid_path, env=None):
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("ab", buffering=0)
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )
    pid_path.write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


def start_server_if_needed(args):
    if port_open(SERVER_PORT) and port_open(BRIDGE_PORT):
        print("server_ready existing")
        return None
    if port_open(SERVER_PORT) or port_open(BRIDGE_PORT):
        raise SystemExit("runtime ports are partially occupied; rerun with --replace-runtime or inspect status")
    pid = launch_detached(["./scripts/start-server.sh"], SERVER_LOG, SERVER_PID_FILE)
    print("server_starting pid={} log={}".format(pid, SERVER_LOG))
    wait_for_port(SERVER_PORT, args.server_timeout, "game server")
    wait_for_port(BRIDGE_PORT, args.server_timeout, "agent bridge")
    print("server_ready")
    return pid


def launch_client(args, nonce):
    env = os.environ.copy()
    if not is_default_user(args.user):
        env["CLIENT_SINGLE_INSTANCE"] = "0"
    elif args.replace_client:
        env["CLIENT_REPLACE_EXISTING"] = "1"
    env["RS_PROFILE"] = args.user
    password_file = resolve_password_file(args)
    client_log = resolve_client_log(args)
    client_pid_file = resolve_client_pid_file(args)
    cmd = [
        "./scripts/start-client.sh",
        "-u",
        args.user,
        "-password-character-save",
        str(password_file),
        "-agent-auto-login",
        "-agent-claim",
        nonce,
        "-scale",
        str(args.scale),
        "-no-nav",
    ]
    pid = launch_detached(cmd, client_log, client_pid_file, env=env)
    print("client_starting profile={} pid={} log={}".format(args.user, pid, client_log))
    return pid


def claim_session(nonce, timeout, session_file):
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"nonce": nonce}).encode("utf-8")
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        request = urllib.request.Request(
            "http://127.0.0.1:{}/agent/session/claim".format(BRIDGE_PORT),
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                data = json.loads(response.read().decode("utf-8"))
            if data.get("success"):
                payload = {
                    "token": data["token"],
                    "sessionId": data.get("sessionId", ""),
                    "playerId": data.get("playerId"),
                    "playerName": data.get("playerName", ""),
                    "createdAt": int(time.time()),
                }
                tmp = session_file.with_suffix(".tmp")
                tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
                os.replace(tmp, session_file)
                print("session_ready player={} sessionId={}".format(payload["playerName"], payload["sessionId"]))
                return payload
        except urllib.error.HTTPError as exc:
            last_error = "HTTP {}".format(exc.code)
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise SystemExit("bridge session claim timed out: {}".format(last_error))


def verify_runtime(args):
    failures = []
    session_file = resolve_session_file(args)
    if not port_open(SERVER_PORT):
        failures.append("server port {} closed".format(SERVER_PORT))
    if not port_open(BRIDGE_PORT):
        failures.append("bridge port {} closed".format(BRIDGE_PORT))

    if args.observe:
        env = os.environ.copy()
        env["RS_PROFILE"] = getattr(args, "user", default_user())
        env["RSBRIDGE_SESSION_FILE"] = str(session_file)
        proc = run_cmd([str(OBSERVE_SLIM)], check=False, capture=True, env=env)
        if proc.returncode != 0:
            failures.append("observe-slim failed: {}".format((proc.stderr or proc.stdout or "").strip()[:300]))
        else:
            print("observe_slim_ok")

    if args.navdb:
        run_cmd([sys.executable, str(NAVDB), "validate"])
        run_cmd([sys.executable, str(NAVDB), "self-test"])
        print("navdb_ok")

    if args.recorder_status:
        run_cmd([sys.executable, str(ROUTE_RECORDER), "status", "--profile", getattr(args, "user", default_user())])

    if failures:
        raise SystemExit("; ".join(failures))
    print("runtime_verify_ok")
    return 0


def cmd_restart(args):
    if args.build and (port_open(SERVER_PORT) or port_open(BRIDGE_PORT)) and not args.replace_runtime:
        raise SystemExit("build requested while runtime appears live; use --replace-runtime or stop it first")
    if args.replace_runtime:
        print("stopping_runtime")
        stop_runtime(include_server=True, include_client=True, session_file=resolve_session_file(args),
                     client_pid_file=resolve_client_pid_file(args), broad_client=True)
    elif args.replace_client:
        print("stopping_client_helpers")
        stop_runtime(include_server=False, include_client=True, session_file=resolve_session_file(args),
                     client_pid_file=resolve_client_pid_file(args), broad_client=is_default_user(args.user))
    build_runtime(args)
    start_server_if_needed(args)
    nonce = secrets.token_urlsafe(32)
    launch_client(args, nonce)
    claim_session(nonce, args.claim_timeout, resolve_session_file(args))
    if args.start_recorder:
        cmd_recorder(argparse.Namespace(recorder_command="start", interval=args.recorder_interval,
                                        idle_every=args.recorder_idle_every, user=args.user))
    if args.verify:
        verify_runtime(argparse.Namespace(observe=True, navdb=False, recorder_status=args.start_recorder,
                                          user=args.user, session_file=str(resolve_session_file(args))))
    return 0


def cmd_claim(args):
    wait_for_port(BRIDGE_PORT, args.server_timeout, "agent bridge")
    if args.replace_client:
        stop_runtime(include_server=False, include_client=True, session_file=resolve_session_file(args),
                     client_pid_file=resolve_client_pid_file(args), broad_client=is_default_user(args.user))
    nonce = secrets.token_urlsafe(32)
    launch_client(args, nonce)
    claim_session(nonce, args.claim_timeout, resolve_session_file(args))
    if args.verify:
        verify_runtime(argparse.Namespace(observe=True, navdb=False, recorder_status=False,
                                          user=args.user, session_file=str(resolve_session_file(args))))
    return 0


def cmd_verify(args):
    return verify_runtime(args)


def cmd_recorder(args):
    if args.recorder_command == "start":
        cmd = [
            sys.executable,
            str(ROUTE_RECORDER),
            "start",
            "--interval",
            str(args.interval),
            "--idle-every",
            str(args.idle_every),
            "--profile",
            args.user,
        ]
    elif args.recorder_command == "stop":
        cmd = [sys.executable, str(ROUTE_RECORDER), "stop", "--profile", args.user]
    else:
        cmd = [sys.executable, str(ROUTE_RECORDER), "status", "--profile", args.user]
    run_cmd(cmd)
    return 0


def add_profile_args(parser):
    parser.add_argument("--user", "--profile", dest="user", default=default_user())
    parser.add_argument("--session-file")
    parser.add_argument("--client-pid-file")
    parser.add_argument("--client-log")


def add_claim_args(parser):
    add_profile_args(parser)
    parser.add_argument("--password-file")
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--claim-timeout", type=float, default=90.0)
    parser.add_argument("--server-timeout", type=float, default=45.0)
    parser.add_argument("--replace-client", dest="replace_client", action="store_true")
    parser.add_argument("--keep-client", dest="replace_client", action="store_false")
    parser.add_argument("--verify", action="store_true")
    parser.set_defaults(replace_client=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Start, claim, verify, and diagnose the local 2006Scape agent runtime.")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Report ports, pid files, and session file status without printing tokens.")
    add_profile_args(status)
    status.add_argument("--observe", action="store_true", help="Also run observe-slim and include a compact preview.")
    status.set_defaults(func=cmd_status)

    restart = sub.add_parser("restart", help="Start or replace the server/client and claim a bridge session.")
    add_claim_args(restart)
    restart.add_argument("--build", action="store_true", help="Run mvn -q -DskipTests package before launch.")
    restart.add_argument("--test-passive-trace", action="store_true", help="Run the focused passive trace test before launch.")
    restart.add_argument("--replace-runtime", action="store_true", help="Stop existing server, client, app-server helpers, and session file first.")
    restart.add_argument("--start-recorder", action="store_true", help="Start route_recorder.py after the bridge claim.")
    restart.add_argument("--recorder-interval", type=float, default=1.2)
    restart.add_argument("--recorder-idle-every", type=float, default=0.0)
    restart.set_defaults(func=cmd_restart)

    claim = sub.add_parser("claim", help="Launch/relaunch the client and claim a bridge session against an existing server.")
    add_claim_args(claim)
    claim.set_defaults(func=cmd_claim)

    verify = sub.add_parser("verify", help="Verify the runtime and optional route tooling.")
    add_profile_args(verify)
    verify.add_argument("--observe", action="store_true", default=True)
    verify.add_argument("--no-observe", dest="observe", action="store_false")
    verify.add_argument("--navdb", action="store_true", help="Run navdb validate and self-test.")
    verify.add_argument("--recorder-status", action="store_true", help="Include route recorder status.")
    verify.set_defaults(func=cmd_verify)

    recorder = sub.add_parser("recorder", help="Delegate to route_recorder.py start/stop/status.")
    add_profile_args(recorder)
    recorder.add_argument("recorder_command", choices=("start", "stop", "status"))
    recorder.add_argument("--interval", type=float, default=1.2)
    recorder.add_argument("--idle-every", type=float, default=0.0)
    recorder.set_defaults(func=cmd_recorder)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
