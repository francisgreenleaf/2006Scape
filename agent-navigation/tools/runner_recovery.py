#!/usr/bin/env python3
"""Runner failure classification and recovery helpers.

These helpers are intentionally separate from bridge_script.call_tool. Bridge
calls should surface failures; long-running process policy belongs here.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from profile_utils import LOCAL_ROOT, resolve_profile, safe_profile


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
RUNTIME_DOCTOR = SCRIPT_DIR / "runtime_doctor.py"
REMOTE_CLAIM = SCRIPT_DIR / "remote_claim.py"
RUNNER_ROOT = LOCAL_ROOT / "runners"


@dataclass(frozen=True)
class FailureClassification:
    kind: str
    reason: str
    matched: str = ""

    def to_dict(self) -> dict:
        payload = {"kind": self.kind, "reason": self.reason}
        if self.matched:
            payload["matched"] = self.matched
        return payload


TERMINAL_PATTERNS = [
    (r"\bstop[_ -]?requested\b|\buser requested stop\b|\bkeyboardinterrupt\b", "stop_requested"),
    (r"\bplayer died\b|\bdeath\b|\bdied\b|\bdead\b", "death_or_dead_player"),
    (r"\bsafety stop\b|\bcombat safety\b|\bunexpected combat\b|\bin combat\b", "safety_or_combat"),
    (r"\binsufficient\b|\bnot enough\b|\bmissing required\b|\brequires level\b", "missing_requirement"),
    (r"\bmissing (tool|item|supplies|food)\b|\bout of food\b|\bno food\b", "missing_supplies"),
    (r"\bno matching (rock|tree|object|npc|resource)\b", "no_matching_target"),
    (r"\bnot reachable\b|\bunreachable\b|\bvisible but not reachable\b", "unreachable_target"),
    (r"\bstalled at\b|\bcould not route\b|\bno route\b|\broute failed\b", "route_or_path_blocker"),
    (r"\bfull observe_state is blocked\b", "full_observe_blocked"),
    (r"\bmade no progress\b|\bno progress\b", "no_progress"),
    (r"\bbank depleted\b|\bsupplies depleted\b", "depleted_supplies"),
]


TRANSIENT_PATTERNS = [
    (r"\binvalid or expired agent session\b|\bexpired agent session\b", "expired_session"),
    (r"\bbridge session file not found\b", "missing_session_file"),
    (r"\bclaimed player is no longer online\b|\bplayer is no longer online\b", "player_offline"),
    (r"\bno pending agent bridge claim was found\b", "claim_not_ready"),
    (r"\bhttp\s+(502|503|504)\b|\bbad gateway\b|\bservice unavailable\b|\bgateway timeout\b", "gateway_unavailable"),
    (r"\bhttp\s+401\b.*\b(session|token|unauthorized|invalid|expired)\b", "unauthorized_session"),
    (r"\bconnection refused\b|\berrno 61\b|\berrno 111\b", "connection_refused"),
    (r"\bconnection reset by peer\b|\brecv failure\b|\bcurl:\s*\(56\)", "connection_reset"),
    (r"\bempty reply from server\b|\bcurl:\s*\(52\)", "empty_bridge_reply"),
    (r"\bremote end closed connection without response\b", "closed_without_response"),
    (r"\btimed out waiting for the next game tick\b", "game_tick_timeout"),
    (r"\burlerror\b|\btemporarily unavailable\b|\bnetwork is unreachable\b", "transport_error"),
    (r"rs-tool\.sh: line \d+:\s+\w+:\s+command not found", "wrapper_shell_parse_failure"),
]


SENSITIVE_ARG_RE = re.compile(r"(token|password|passwd|secret|api[-_]?key|nonce|session)", re.IGNORECASE)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _first_match(patterns: list[tuple[str, str]], text: str) -> FailureClassification | None:
    for pattern, reason in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return FailureClassification("", reason, match.group(0)[:160])
    return None


def classify_failure(log_tail: str, exit_code: int | None = None) -> FailureClassification:
    """Classify a runner failure from its exit code and recent log tail."""
    if exit_code == 0:
        return FailureClassification("terminal", "clean_exit")
    text = str(log_tail or "")
    terminal = _first_match(TERMINAL_PATTERNS, text)
    if terminal:
        return FailureClassification("terminal", terminal.reason, terminal.matched)
    transient = _first_match(TRANSIENT_PATTERNS, text)
    if transient:
        return FailureClassification("transient", transient.reason, transient.matched)
    if exit_code is None:
        return FailureClassification("unknown", "no_exit_code")
    return FailureClassification("unknown", "unclassified_exit_{}".format(exit_code))


def read_log_tail(path: Path | str, max_bytes: int = 12000) -> str:
    log_path = Path(path)
    try:
        size = log_path.stat().st_size
        with log_path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(-max_bytes, os.SEEK_END)
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def process_exists(pid: int | str | None) -> bool:
    try:
        value = int(pid or 0)
    except (TypeError, ValueError):
        return False
    if value <= 0:
        return False
    try:
        os.kill(value, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def runner_dir(profile: str | None = "") -> Path:
    selected = resolve_profile(profile, default="")
    return RUNNER_ROOT / safe_profile(selected)


def default_status_path(profile: str | None, name: str) -> Path:
    return runner_dir(profile) / "{}.supervisor.status.json".format(safe_profile(name))


def default_supervisor_pid_path(profile: str | None, name: str) -> Path:
    return runner_dir(profile) / "{}.supervisor.pid".format(safe_profile(name))


def default_child_pid_path(profile: str | None, name: str) -> Path:
    return runner_dir(profile) / "{}.pid".format(safe_profile(name))


def default_log_path(profile: str | None, name: str) -> Path:
    return runner_dir(profile) / "{}.log".format(safe_profile(name))


def write_json_file(path: Path | str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(target))


def write_pid_file(path: Path | str, pid: int) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(int(pid)), encoding="utf-8")


def sanitize_command(command: list[str]) -> list[str]:
    redacted: list[str] = []
    redact_next = False
    for raw in command:
        arg = str(raw)
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        if SENSITIVE_ARG_RE.search(arg):
            if "=" in arg:
                key = arg.split("=", 1)[0]
                redacted.append(key + "=<redacted>")
            elif arg.startswith("--"):
                redacted.append(arg)
                redact_next = True
            else:
                redacted.append("<redacted>")
            continue
        redacted.append(arg)
    return redacted


def check_session(profile: str | None = "", timeout_seconds: float = 8.0) -> dict:
    """Return compact session status using observe_state_XXS."""
    old_timeout = os.environ.get("RSBRIDGE_TIMEOUT_SECONDS")
    os.environ["RSBRIDGE_TIMEOUT_SECONDS"] = str(max(1.0, float(timeout_seconds)))
    try:
        import bridge_script
        result = bridge_script.call_tool("observe_state_XXS", {}, profile=profile or "")
        if isinstance(result, dict) and result.get("success") is False:
            classification = classify_failure(str(result), exit_code=1)
            return {
                "ok": False,
                "status": "invalid",
                "classification": classification.to_dict(),
                "message": str(result.get("message") or result.get("error") or "")[:300],
            }
        return {"ok": True, "status": "valid"}
    except Exception as exc:
        text = str(exc)
        classification = classify_failure(text, exit_code=1)
        status = "invalid"
        if classification.reason == "missing_session_file":
            status = "missing_session"
        elif classification.reason in ("expired_session", "unauthorized_session"):
            status = "expired"
        elif classification.kind == "transient":
            status = "gateway_down"
        return {
            "ok": False,
            "status": status,
            "classification": classification.to_dict(),
            "message": text[:300],
        }
    finally:
        if old_timeout is None:
            os.environ.pop("RSBRIDGE_TIMEOUT_SECONDS", None)
        else:
            os.environ["RSBRIDGE_TIMEOUT_SECONDS"] = old_timeout


def reclaim_profile(profile: str | None = "", bridge_url: str = "", ssl_cert_file: str = "",
        claim_mode: str = "none", timeout_seconds: float = 90.0) -> dict:
    """Attempt a selected-profile reclaim according to an explicit policy."""
    selected = resolve_profile(profile, default="")
    mode = str(claim_mode or "none").strip().lower().replace("_", "-")
    if mode in ("", "none", "off", "false"):
        return {"ok": False, "status": "skipped", "reason": "auto_reclaim_disabled"}

    env = os.environ.copy()
    if selected:
        env["RS_PROFILE"] = selected
        env["RSBRIDGE_PROFILE"] = selected
    if ssl_cert_file:
        env["SSL_CERT_FILE"] = ssl_cert_file

    if mode == "local-runtime-doctor":
        command = [sys.executable, str(RUNTIME_DOCTOR), "claim"]
        if selected:
            command.extend(["--profile", selected])
        command.append("--verify")
        proc = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=max(5.0, float(timeout_seconds)),
        )
        return {
            "ok": proc.returncode == 0,
            "status": "claimed" if proc.returncode == 0 else "failed",
            "mode": mode,
            "returncode": proc.returncode,
            "stdoutTail": proc.stdout[-500:],
            "stderrTail": proc.stderr[-500:],
            "command": sanitize_command(command),
        }

    if mode in ("remote-existing-client", "remote-manual"):
        command = [sys.executable, str(REMOTE_CLAIM)]
        if selected:
            command.extend(["--profile", selected])
        if bridge_url:
            command.extend(["--bridge-url", bridge_url])
        command.append("--verify")
        return {
            "ok": False,
            "status": "manual_required",
            "mode": mode,
            "reason": "remote reclaim requires the exact claim command to be typed into the selected character client",
            "command": sanitize_command(command),
            "matchingClientWindows": find_client_for_profile(selected),
        }

    return {"ok": False, "status": "unsupported", "mode": mode, "reason": "unknown reclaim mode"}


def _applescript_string(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def find_client_for_profile(profile: str | None = "") -> list[dict]:
    """Return visible macOS Java client windows whose title contains profile."""
    selected = str(profile or "").strip()
    if not selected or platform.system() != "Darwin":
        return []
    script = """
set needle to {needle}
set matchesText to ""
tell application "System Events"
  repeat with p in (every process whose name contains "java")
    repeat with w in windows of p
      set windowTitle to name of w as text
      if windowTitle contains needle then
        set matchesText to matchesText & (name of p as text) & tab & windowTitle & linefeed
      end if
    end repeat
  end repeat
end tell
return matchesText
""".format(needle=_applescript_string(selected))
    proc = subprocess.run(["osascript", "-e", script], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return [{"error": proc.stderr.strip()[-300:]}]
    matches = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        process, _, title = line.partition("\t")
        matches.append({"process": process.strip(), "title": title.strip()})
    return matches
