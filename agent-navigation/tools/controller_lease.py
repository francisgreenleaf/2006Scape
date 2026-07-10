#!/usr/bin/env python3
"""Profile-scoped ownership for processes that control a player.

The active lease is intentionally separate from per-runner pid/status files. A
profile may have many historical runner records, but only one live gameplay
controller. Child processes can join the active lease when the owner delegates
its opaque lease id through the environment.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

from profile_utils import LOCAL_ROOT, resolve_profile, safe_profile
from runner_recovery import process_exists, utc_now, write_json_file


LEASE_ENV = "RS_CONTROLLER_LEASE_ID"
CONTROLLER_ROOT_ENV = "RS_CONTROLLER_ROOT"
ACTIVE_FILENAME = "active-controller.json"
STOP_FILENAME = "controller-stop.json"
LOCK_FILENAME = ".controller.lock"


class ControllerLeaseError(RuntimeError):
    """Base error for invalid controller ownership state."""


class ControllerBusyError(ControllerLeaseError):
    def __init__(self, current: dict[str, Any]):
        self.current = compact_lease(current)
        super().__init__(
            "profile {} is already controlled by {} (pid {})".format(
                self.current.get("profile") or "default",
                self.current.get("controller") or "unknown",
                self.current.get("pid") or "unknown",
            )
        )


@dataclass(frozen=True)
class ControllerPaths:
    directory: Path
    active: Path
    stop: Path
    lock: Path


def controller_root() -> Path:
    override = str(os.environ.get(CONTROLLER_ROOT_ENV) or "").strip()
    return Path(override).expanduser().resolve() if override else LOCAL_ROOT / "runners"


def controller_paths(profile: str | None = "") -> ControllerPaths:
    selected = resolve_profile(profile, default="")
    directory = controller_root() / safe_profile(selected)
    return ControllerPaths(
        directory=directory,
        active=directory / ACTIVE_FILENAME,
        stop=directory / STOP_FILENAME,
        lock=directory / LOCK_FILENAME,
    )


@contextmanager
def _locked(paths: ControllerPaths) -> Iterator[None]:
    paths.directory.mkdir(parents=True, exist_ok=True)
    with paths.lock.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _remove_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _live_payload_locked(paths: ControllerPaths) -> Optional[dict[str, Any]]:
    payload = _read_json(paths.active)
    if not payload:
        if paths.active.exists():
            _remove_if_exists(paths.active)
        _remove_if_exists(paths.stop)
        return None
    if not process_exists(payload.get("pid")):
        _remove_if_exists(paths.active)
        _remove_if_exists(paths.stop)
        return None
    return payload


def compact_lease(payload: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not payload:
        return {}
    result = {
        "profile": payload.get("profile") or payload.get("profileKey") or "default",
        "controller": payload.get("controller") or "",
        "kind": payload.get("kind") or "",
        "pid": payload.get("pid"),
        "startedAt": payload.get("startedAt"),
        "updatedAt": payload.get("updatedAt"),
    }
    return {key: value for key, value in result.items() if value not in (None, "")}


class ControllerLease:
    def __init__(self, profile: str, lease_id: str, paths: ControllerPaths, owns: bool):
        self.profile = profile
        self.lease_id = lease_id
        self.paths = paths
        self.owns = owns
        self.released = False

    def current(self) -> dict[str, Any]:
        with _locked(self.paths):
            payload = _live_payload_locked(self.paths)
            if not payload or payload.get("leaseId") != self.lease_id:
                raise ControllerLeaseError("controller lease is no longer active")
            return dict(payload)

    def transfer_pid(self, pid: int) -> None:
        with _locked(self.paths):
            payload = _live_payload_locked(self.paths)
            if not payload or payload.get("leaseId") != self.lease_id:
                raise ControllerLeaseError("cannot transfer an inactive controller lease")
            payload["pid"] = int(pid)
            payload["updatedAt"] = utc_now()
            write_json_file(self.paths.active, payload)

    def refresh(self) -> None:
        if self.released:
            return
        with _locked(self.paths):
            payload = _live_payload_locked(self.paths)
            if not payload or payload.get("leaseId") != self.lease_id:
                raise ControllerLeaseError("controller lease is no longer active")
            payload["updatedAt"] = utc_now()
            write_json_file(self.paths.active, payload)

    def stop_requested(self) -> bool:
        request = _read_json(self.paths.stop)
        return bool(request and request.get("leaseId") == self.lease_id)

    def release(self) -> None:
        if self.released or not self.owns:
            return
        with _locked(self.paths):
            payload = _read_json(self.paths.active)
            if payload and payload.get("leaseId") == self.lease_id:
                _remove_if_exists(self.paths.active)
                request = _read_json(self.paths.stop)
                if not request or request.get("leaseId") == self.lease_id:
                    _remove_if_exists(self.paths.stop)
        self.released = True


def acquire_controller(
    profile: str | None,
    controller: str,
    kind: str,
    pid: Optional[int] = None,
    replace: bool = False,
    replace_wait_seconds: float = 10.0,
) -> ControllerLease:
    selected = resolve_profile(profile, default="")
    paths = controller_paths(selected)
    if replace:
        try:
            return acquire_controller(selected, controller, kind, pid=pid)
        except ControllerBusyError:
            request_controller_stop(selected)
            deadline = time.monotonic() + max(0.0, float(replace_wait_seconds))
            while time.monotonic() < deadline:
                if not controller_status(selected).get("active"):
                    break
                time.sleep(0.1)

    with _locked(paths):
        current = _live_payload_locked(paths)
        if current:
            raise ControllerBusyError(current)
        now = utc_now()
        lease_id = uuid.uuid4().hex
        payload = {
            "schemaVersion": 1,
            "leaseId": lease_id,
            "profile": selected,
            "profileKey": safe_profile(selected),
            "controller": str(controller or "gameplay-controller"),
            "kind": str(kind or "gameplay"),
            "pid": int(pid if pid is not None else os.getpid()),
            "startedAt": now,
            "updatedAt": now,
        }
        _remove_if_exists(paths.stop)
        write_json_file(paths.active, payload)
        return ControllerLease(selected, lease_id, paths, owns=True)


def join_controller(profile: str | None, lease_id: str) -> ControllerLease:
    selected = resolve_profile(profile, default="")
    paths = controller_paths(selected)
    with _locked(paths):
        payload = _live_payload_locked(paths)
        if not payload or payload.get("leaseId") != str(lease_id or ""):
            raise ControllerLeaseError("delegated controller lease is missing, stale, or for another profile")
        return ControllerLease(selected, str(lease_id), paths, owns=False)


def adopt_controller(profile: str | None, lease_id: str, pid: Optional[int] = None) -> ControllerLease:
    """Take ownership of a reservation created by the detached launcher."""
    selected = resolve_profile(profile, default="")
    paths = controller_paths(selected)
    with _locked(paths):
        payload = _live_payload_locked(paths)
        if not payload or payload.get("leaseId") != str(lease_id or ""):
            raise ControllerLeaseError("controller reservation is missing or stale")
        payload["pid"] = int(pid if pid is not None else os.getpid())
        payload["updatedAt"] = utc_now()
        write_json_file(paths.active, payload)
        return ControllerLease(selected, str(lease_id), paths, owns=True)


def acquire_or_join_controller(profile: str | None, controller: str, kind: str) -> ControllerLease:
    delegated = str(os.environ.get(LEASE_ENV) or "").strip()
    if delegated:
        return join_controller(profile, delegated)
    return acquire_controller(profile, controller, kind)


def request_controller_stop(profile: str | None) -> dict[str, Any]:
    selected = resolve_profile(profile, default="")
    paths = controller_paths(selected)
    with _locked(paths):
        payload = _live_payload_locked(paths)
        if not payload:
            return {"ok": True, "profile": selected, "active": False, "status": "idle"}
        request = {
            "schemaVersion": 1,
            "leaseId": payload.get("leaseId"),
            "profile": selected,
            "requestedAt": utc_now(),
            "requestedByPid": os.getpid(),
        }
        write_json_file(paths.stop, request)
        result = compact_lease(payload)
        result.update({"ok": True, "active": True, "status": "stop_requested"})
        return result


def controller_status(profile: str | None) -> dict[str, Any]:
    selected = resolve_profile(profile, default="")
    paths = controller_paths(selected)
    with _locked(paths):
        payload = _live_payload_locked(paths)
        if not payload:
            return {"ok": True, "profile": selected, "active": False, "status": "idle"}
        result = compact_lease(payload)
        request = _read_json(paths.stop)
        result.update({
            "ok": True,
            "active": True,
            "status": "stop_requested" if request and request.get("leaseId") == payload.get("leaseId") else "running",
        })
        return result


def all_controller_statuses() -> list[dict[str, Any]]:
    root = controller_root()
    if not root.exists():
        return []
    profiles: list[str] = []
    for active_path in sorted(root.glob("*/{}".format(ACTIVE_FILENAME))):
        payload = _read_json(active_path)
        if payload is not None:
            profiles.append(str(payload.get("profile") or active_path.parent.name))
    statuses = [controller_status(profile) for profile in profiles]
    return [status for status in statuses if status.get("active")]
