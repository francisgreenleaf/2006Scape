#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runner_recovery import classify_failure, sanitize_command


class RunnerRecoveryClassificationTest(unittest.TestCase):
    def test_transient_bridge_transport_patterns(self):
        samples = [
            "RuntimeError: wait_until_idle_XS failed: curl: (52) Empty reply from server",
            "RuntimeError: observe_state_XXS failed: [Errno 61] Connection refused",
            "RuntimeError: walk_to_tile_until_arrived_XS failed: HTTP 502 Bad Gateway",
            "RuntimeError: observe_state_XXS failed: Invalid or expired agent session",
            "/tools/rs-tool.sh: line 127: is: command not found",
            "HTTP 400 {\"message\":\"Timed out waiting for the next game tick.\"}",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(classify_failure(sample, exit_code=1).kind, "transient")

    def test_terminal_gameplay_and_safety_patterns(self):
        samples = [
            "hardcoded Seers route to seers_willow_trees stalled at 2710,3480,0",
            "RuntimeError: could not route to mine site",
            "Full observe_state is blocked by rs-tool.sh unless RS_ALLOW_FULL_OBSERVE=1",
            "safety stop: player died and respawned",
            "visible but not reachable",
            "No matching rock found nearby",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(classify_failure(sample, exit_code=1).kind, "terminal")

    def test_unknown_failure_does_not_become_transient(self):
        result = classify_failure("Traceback: ValueError: unexpected local bug", exit_code=1)
        self.assertEqual(result.kind, "unknown")

    def test_clean_exit_is_terminal(self):
        result = classify_failure("", exit_code=0)
        self.assertEqual(result.kind, "terminal")
        self.assertEqual(result.reason, "clean_exit")

    def test_sanitize_command_redacts_sensitive_values(self):
        command = [
            "python3",
            "runner.py",
            "--profile",
            "MrFlame",
            "--token",
            "secret-token",
            "--password=secret-password",
            "--nonce",
            "claim-code",
        ]
        self.assertEqual(
            sanitize_command(command),
            [
                "python3",
                "runner.py",
                "--profile",
                "MrFlame",
                "--token",
                "<redacted>",
                "--password=<redacted>",
                "--nonce",
                "<redacted>",
            ],
        )


if __name__ == "__main__":
    unittest.main()
