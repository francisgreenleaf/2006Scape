#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parents[1]
SUPERVISED_RUNNER = TOOLS_DIR / "supervised_runner.py"
LAUNCH_DETACHED = TOOLS_DIR / "launch_detached_runner.py"
CONTROLLER_XS = TOOLS_DIR / "gameplay_controller_XS.py"


class SupervisedRunnerSmokeTest(unittest.TestCase):
    def run_supervisor(self, tmp: Path, child_script: Path, max_restarts: int = 2):
        log_path = tmp / "runner.log"
        status_path = tmp / "status.json"
        pid_path = tmp / "child.pid"
        supervisor_pid_path = tmp / "supervisor.pid"
        proc = subprocess.run(
            [
                sys.executable,
                str(SUPERVISED_RUNNER),
                "--profile",
                "TestProfile",
                "--name",
                "test-runner",
                "--log",
                str(log_path),
                "--pid-file",
                str(pid_path),
                "--supervisor-pid-file",
                str(supervisor_pid_path),
                "--status-file",
                str(status_path),
                "--max-restarts",
                str(max_restarts),
                "--backoff-initial",
                "0",
                "--backoff-max",
                "0",
                "--",
                sys.executable,
                str(child_script),
            ],
            cwd=str(REPO_ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "RS_CONTROLLER_ROOT": str(tmp / "controllers")},
            timeout=20,
        )
        status = json.loads(status_path.read_text(encoding="utf-8"))
        return proc, status, log_path

    def test_restarts_once_for_transient_bridge_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            count_path = tmp / "count.txt"
            child = tmp / "child.py"
            child.write_text(textwrap.dedent("""
                import pathlib
                import sys

                count_path = pathlib.Path(sys.argv[0]).with_name("count.txt")
                count = int(count_path.read_text() or "0") if count_path.exists() else 0
                count += 1
                count_path.write_text(str(count))
                if count == 1:
                    print("RuntimeError: wait_until_idle_XS failed: curl: (52) Empty reply from server")
                    raise SystemExit(1)
                print("ok on retry")
            """), encoding="utf-8")

            proc, status, log_path = self.run_supervisor(tmp, child, max_restarts=2)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(count_path.read_text(encoding="utf-8"), "2")
            self.assertEqual(status["status"], "complete")
            self.assertEqual(status["restarts"], 1)
            self.assertIn("ok on retry", log_path.read_text(encoding="utf-8"))

    def test_does_not_restart_terminal_route_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            count_path = tmp / "count.txt"
            child = tmp / "child.py"
            child.write_text(textwrap.dedent("""
                import pathlib
                import sys

                count_path = pathlib.Path(sys.argv[0]).with_name("count.txt")
                count = int(count_path.read_text() or "0") if count_path.exists() else 0
                count += 1
                count_path.write_text(str(count))
                print("hardcoded Seers route to seers_willow_trees stalled at 2710,3480,0")
                raise SystemExit(1)
            """), encoding="utf-8")

            proc, status, _log_path = self.run_supervisor(tmp, child, max_restarts=2)

            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(count_path.read_text(encoding="utf-8"), "1")
            self.assertEqual(status["status"], "terminal")
            self.assertEqual(status["lastClassification"]["kind"], "terminal")

    def test_launch_detached_supervise_starts_supervisor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            child = tmp / "child.py"
            child.write_text("print('detached hello')\n", encoding="utf-8")
            log_path = tmp / "runner.log"
            status_path = tmp / "status.json"
            child_pid_path = tmp / "child.pid"
            supervisor_pid_path = tmp / "supervisor.pid"

            proc = subprocess.run(
                [
                    sys.executable,
                    str(LAUNCH_DETACHED),
                    "--supervise",
                    "--profile",
                    "TestProfile",
                    "--name",
                    "detached-test",
                    "--log",
                    str(log_path),
                    "--pid-file",
                    str(child_pid_path),
                    "--supervisor-pid-file",
                    str(supervisor_pid_path),
                    "--status-file",
                    str(status_path),
                    "--backoff-initial",
                    "0",
                    "--backoff-max",
                    "0",
                    "--",
                    sys.executable,
                    str(child),
                ],
                cwd=str(REPO_ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "RS_CONTROLLER_ROOT": str(tmp / "controllers")},
                timeout=10,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(proc.stdout.strip().isdigit())

            deadline = 5.0
            started = time.time()
            status = {}
            while time.time() - started < deadline:
                if status_path.exists():
                    status = json.loads(status_path.read_text(encoding="utf-8"))
                    if status.get("status") == "complete":
                        break
                time.sleep(0.05)

            self.assertEqual(status.get("status"), "complete", status)
            self.assertIn("detached hello", log_path.read_text(encoding="utf-8"))

    def test_second_controller_is_refused_and_compact_stop_ends_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            child = tmp / "child.py"
            child.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
            blocked_child = tmp / "blocked.py"
            blocked_marker = tmp / "blocked-ran.txt"
            blocked_child.write_text(
                "from pathlib import Path\nPath({!r}).write_text('ran')\n".format(str(blocked_marker)),
                encoding="utf-8",
            )
            env = {**os.environ, "RS_CONTROLLER_ROOT": str(tmp / "controllers")}
            first_status = tmp / "first.status.json"
            first = subprocess.Popen(
                [
                    sys.executable,
                    str(SUPERVISED_RUNNER),
                    "--profile", "TestProfile",
                    "--name", "first",
                    "--log", str(tmp / "first.log"),
                    "--status-file", str(first_status),
                    "--", sys.executable, str(child),
                ],
                cwd=str(REPO_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            try:
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    if first_status.exists():
                        status = json.loads(first_status.read_text(encoding="utf-8"))
                        if status.get("status") == "running":
                            break
                    time.sleep(0.05)
                else:
                    self.fail("first supervisor did not reach running state")

                second = subprocess.run(
                    [
                        sys.executable,
                        str(SUPERVISED_RUNNER),
                        "--profile", "TestProfile",
                        "--name", "second",
                        "--log", str(tmp / "second.log"),
                        "--status-file", str(tmp / "second.status.json"),
                        "--", sys.executable, str(blocked_child),
                    ],
                    cwd=str(REPO_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                    timeout=10,
                )
                self.assertEqual(second.returncode, 6, second.stderr)
                self.assertIn('"status":"controller_conflict"', second.stderr)
                self.assertFalse(blocked_marker.exists())

                stopped = subprocess.run(
                    [sys.executable, str(CONTROLLER_XS), "stop", "--profile", "TestProfile", "--wait", "5"],
                    cwd=str(REPO_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                    timeout=10,
                )
                self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
                self.assertEqual(json.loads(stopped.stdout)["status"], "stopped")
                self.assertEqual(first.wait(timeout=10), 0)
                self.assertEqual(json.loads(first_status.read_text(encoding="utf-8"))["status"], "stopped")
            finally:
                if first.poll() is None:
                    first.terminate()
                    first.wait(timeout=5)

    def test_detached_replace_controller_performs_cooperative_handoff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            long_child = tmp / "long.py"
            long_child.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
            next_marker = tmp / "next-ran.txt"
            next_child = tmp / "next.py"
            next_child.write_text(
                "from pathlib import Path\nPath({!r}).write_text('ran')\n".format(str(next_marker)),
                encoding="utf-8",
            )
            env = {**os.environ, "RS_CONTROLLER_ROOT": str(tmp / "controllers")}
            first_status = tmp / "first.status.json"
            first = subprocess.Popen(
                [
                    sys.executable, str(SUPERVISED_RUNNER),
                    "--profile", "TestProfile", "--name", "first",
                    "--log", str(tmp / "first.log"), "--status-file", str(first_status),
                    "--", sys.executable, str(long_child),
                ],
                cwd=str(REPO_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
            )
            try:
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    if first_status.exists() and json.loads(first_status.read_text(encoding="utf-8")).get("status") == "running":
                        break
                    time.sleep(0.05)
                else:
                    self.fail("first supervisor did not reach running state")

                second_status = tmp / "second.status.json"
                launched = subprocess.run(
                    [
                        sys.executable, str(LAUNCH_DETACHED), "--supervise",
                        "--replace-controller", "--replace-wait", "5",
                        "--profile", "TestProfile", "--name", "second",
                        "--log", str(tmp / "second.log"), "--status-file", str(second_status),
                        "--", sys.executable, str(next_child),
                    ],
                    cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, env=env, timeout=10,
                )
                self.assertEqual(launched.returncode, 0, launched.stderr)
                self.assertEqual(first.wait(timeout=10), 0)
                self.assertEqual(json.loads(first_status.read_text(encoding="utf-8"))["status"], "stopped")

                deadline = time.time() + 5.0
                while time.time() < deadline:
                    if second_status.exists() and json.loads(second_status.read_text(encoding="utf-8")).get("status") == "complete":
                        break
                    time.sleep(0.05)
                else:
                    self.fail("replacement supervisor did not complete")
                self.assertTrue(next_marker.exists())
            finally:
                if first.poll() is None:
                    first.terminate()
                    first.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
