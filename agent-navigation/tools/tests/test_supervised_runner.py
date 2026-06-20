#!/usr/bin/env python3

from __future__ import annotations

import json
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


if __name__ == "__main__":
    unittest.main()
