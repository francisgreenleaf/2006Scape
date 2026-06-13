#!/usr/bin/env python3
"""Start an isolated alternate-port server long enough to prove runtime wiring."""

import argparse
import json
import os
import selectors
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts" / "lib"))

from game_login_probe import login_socket  # noqa: E402

SERVER_DIR = ROOT_DIR / "2006Scape Server"
SERVER_JAR = SERVER_DIR / "target" / "server-1.0-jar-with-dependencies.jar"
ACCOUNT_DIR = SERVER_DIR / "data" / "accounts"
CHARACTER_DIR = SERVER_DIR / "data" / "characters"


def fail(message):
    raise SystemExit("isolated runtime smoke failed: {}".format(message))


def free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def can_connect(port, timeout=1.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def bridge_health(port, timeout=0.4):
    try:
        url = "http://127.0.0.1:{}/agent/health".format(port)
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return None


def unique_smoke_users():
    suffix = "{:06d}".format((int(time.time() * 1000) + os.getpid()) % 1000000)
    return [
        "smk{}a".format(suffix),
        "smk{}b".format(suffix),
        "smk{}c".format(suffix),
        "smk{}d".format(suffix),
        "smk{}e".format(suffix),
    ]


def create_smoke_accounts(usernames, password, disabled_usernames=()):
    created = []
    disabled = set(disabled_usernames or ())
    env = os.environ.copy()
    env["ACCOUNT_PASSWORD"] = password
    ACCOUNT_DIR.mkdir(parents=True, exist_ok=True)
    CHARACTER_DIR.mkdir(parents=True, exist_ok=True)
    for username in usernames:
        account_path = ACCOUNT_DIR / "{}.json".format(username)
        character_path = CHARACTER_DIR / "{}.txt".format(username)
        if account_path.exists() or character_path.exists():
            raise RuntimeError("refusing to overwrite existing smoke account/character for {}".format(username))
        command = [
            "python3",
            str(ROOT_DIR / "scripts" / "create-account.py"),
            username,
            "--password-env",
            "ACCOUNT_PASSWORD",
            "--accounts-dir",
            str(ACCOUNT_DIR),
            "--allowed-character",
            username,
        ]
        if username in disabled:
            command.append("--disabled")
        subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        created.append(account_path)
        created.append(character_path)
    return created


def cleanup_smoke_files(paths):
    for path in paths:
        try:
            if path.is_file() or path.is_symlink():
                path.unlink()
        except OSError:
            pass


def config_for_ports(ports):
    config = {
        "server_name": "2006Scape Isolated Smoke",
        "server_test_version": 2.3,
        "gui_enabled": False,
        "server_debug": False,
        "file_server": True,
        "game_bind_hosts": ["127.0.0.1"],
        "http_bind_hosts": ["127.0.0.1"],
        "jaggrab_bind_hosts": ["127.0.0.1"],
        "public_game_host": "isolated-runtime-smoke.invalid",
        "external_players_enabled": True,
        "external_transport_mode": "client_tls_tunnel",
        "require_secure_external_transport": True,
        "secure_external_transport_confirmed": True,
        "wildcard_bind_confirmed": False,
        "agent_chat_discord_enabled": False,
        "agent_chat_log_enabled": False,
        "agent_bridge_bind_host": "127.0.0.1",
        "account_auth_enabled": True,
        "account_auth_auto_create": False,
        "account_auth_legacy_fallback": False,
        "account_auth_pbkdf2_iterations": 120000,
        "world_id": 1,
        "xp_rate": 1.0,
        "variable_xp_rate": False,
        "members_only": False,
        "tutorial_island_enabled": False,
        "party_room_enabled": True,
        "clues_enabled": True,
        "admin_can_trade": False,
        "admin_can_sell": False,
        "respawn_x": 3222,
        "respawn_y": 3218,
        "save_timer": 120,
        "timeout": 60,
        "item_requirements": True,
        "max_players": 20,
        "website_integration": False,
        "cycle_logging": False,
        "cycle_logging_tick": 10,
        "performance_logging": False,
    }
    config.update(ports)
    return config


def terminate_process(proc):
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (AttributeError, ProcessLookupError):
        proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (AttributeError, ProcessLookupError):
            proc.kill()
        proc.wait(timeout=8)


def run_smoke(timeout_seconds):
    if not SERVER_JAR.exists():
        fail("server jar does not exist; run mvn -q clean -DskipTests package first")
    ports = {
        "game_port": free_port(),
        "http_port": free_port(),
        "jaggrab_port": free_port(),
        "agent_bridge_port": free_port(),
    }
    if len(set(ports.values())) != len(ports):
        fail("could not allocate distinct alternate ports: {}".format(ports))

    temp_dir = Path(tempfile.mkdtemp(prefix="2006scape-runtime-smoke-"))
    config_path = temp_dir / "ServerConfig.IsolatedSmoke.json"
    config_path.write_text(json.dumps(config_for_ports(ports), indent=2), encoding="utf-8")
    smoke_users = unique_smoke_users()
    login_users = smoke_users[:2]
    reject_user = smoke_users[2]
    disabled_user = smoke_users[3]
    missing_user = smoke_users[4]
    missing_account_path = ACCOUNT_DIR / "{}.json".format(missing_user)
    missing_character_path = CHARACTER_DIR / "{}.txt".format(missing_user)
    if missing_account_path.exists() or missing_character_path.exists():
        fail("refusing to use an existing account/character for missing-account smoke: {}".format(missing_user))
    smoke_password = "isolated smoke password {}".format(os.getpid())
    smoke_files = []
    login_sockets = []

    proc = subprocess.Popen(
        ["java", "-jar", str(SERVER_JAR), "-c", str(config_path)],
        cwd=str(SERVER_DIR),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    selector = selectors.DefaultSelector()
    if proc.stdout is not None:
        selector.register(proc.stdout, selectors.EVENT_READ)
    lines = []
    health = None
    try:
        try:
            account_users = login_users + [reject_user, disabled_user]
            smoke_files = create_smoke_accounts(
                account_users,
                smoke_password,
                disabled_usernames=(disabled_user,),
            )
        except Exception as exc:
            fail("could not create throwaway PBKDF2 smoke accounts: {}".format(exc))
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            for key, _ in selector.select(timeout=0.2):
                line = key.fileobj.readline()
                if line:
                    lines.append(line.rstrip())
            health = bridge_health(ports["agent_bridge_port"])
            if health:
                break
            if proc.poll() is not None:
                break
        if not health:
            fail("bridge health did not respond on alternate port {}; exit={} recent_log={}".format(
                ports["agent_bridge_port"], proc.poll(), "\n".join(lines[-30:])))

        connected = []
        for label in ("game_port", "http_port", "jaggrab_port"):
            if not can_connect(ports[label]):
                fail("{} did not accept a local TCP connection on {}".format(label, ports[label]))
            connected.append(label)
        logins = []
        for username in login_users:
            try:
                sock, login = login_socket("127.0.0.1", ports["game_port"], username, smoke_password)
            except Exception as exc:
                fail("PBKDF2 login smoke failed for {}: {}".format(username, exc))
            login_sockets.append(sock)
            logins.append(login)
        try:
            rejected_sock, rejected_login = login_socket(
                "127.0.0.1",
                ports["game_port"],
                reject_user,
                smoke_password + " wrong",
            )
        except Exception as exc:
            fail("PBKDF2 rejected-login smoke failed for {}: {}".format(reject_user, exc))
        if rejected_sock is not None:
            try:
                rejected_sock.close()
            except OSError:
                pass
            fail("wrong-password PBKDF2 login was accepted for {}".format(reject_user))
        try:
            disabled_sock, disabled_login = login_socket(
                "127.0.0.1",
                ports["game_port"],
                disabled_user,
                smoke_password,
            )
        except Exception as exc:
            fail("PBKDF2 disabled-account smoke failed for {}: {}".format(disabled_user, exc))
        if disabled_sock is not None:
            try:
                disabled_sock.close()
            except OSError:
                pass
            fail("disabled PBKDF2 account login was accepted for {}".format(disabled_user))
        try:
            missing_sock, missing_login = login_socket(
                "127.0.0.1",
                ports["game_port"],
                missing_user,
                smoke_password,
            )
        except Exception as exc:
            fail("PBKDF2 missing-account smoke failed for {}: {}".format(missing_user, exc))
        if missing_sock is not None:
            try:
                missing_sock.close()
            except OSError:
                pass
            fail("missing PBKDF2 account login was accepted for {}".format(missing_user))

        return {
            "ok": True,
            "ports": ports,
            "connected": connected,
            "logins": logins,
            "rejectedLogin": rejected_login,
            "disabledLogin": disabled_login,
            "missingLogin": missing_login,
            "health": health,
            "logTail": lines[-8:],
        }
    finally:
        for sock in login_sockets:
            try:
                sock.close()
            except OSError:
                pass
        terminate_process(proc)
        cleanup_smoke_files(smoke_files)
        try:
            config_path.unlink()
            temp_dir.rmdir()
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description="Run an isolated alternate-port runtime smoke test.")
    parser.add_argument("--timeout", type=float, default=75.0)
    parser.add_argument("--json", action="store_true", help="Print the full smoke result as JSON.")
    args = parser.parse_args()

    result = run_smoke(args.timeout)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("isolated runtime smoke passed")
        print("ports: game={game_port} http={http_port} jaggrab={jaggrab_port} bridge={agent_bridge_port}".format(
            **result["ports"]))
        print("logins: {}".format(", ".join(login["username"] for login in result["logins"])))
        print("rejected login: {username} status={statusName}".format(**result["rejectedLogin"]))
        print("disabled login: {username} status={statusName}".format(**result["disabledLogin"]))
        print("missing login: {username} status={statusName}".format(**result["missingLogin"]))
        print("bridge health: {}".format(json.dumps(result["health"], sort_keys=True)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
