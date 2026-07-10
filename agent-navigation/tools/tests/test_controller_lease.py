#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from controller_lease import (  # noqa: E402
    ControllerBusyError,
    LEASE_ENV,
    acquire_controller,
    acquire_or_join_controller,
    controller_status,
    request_controller_stop,
)


class ControllerLeaseTests(unittest.TestCase):
    def test_one_live_controller_per_profile_and_profile_isolation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"RS_CONTROLLER_ROOT": tmp}):
            first = acquire_controller("Alpha", "mining", "runner")
            other = acquire_controller("Beta", "routing", "route")
            try:
                with self.assertRaises(ControllerBusyError):
                    acquire_controller("Alpha", "routing", "route")
                self.assertEqual(controller_status("Alpha")["controller"], "mining")
                self.assertEqual(controller_status("Beta")["controller"], "routing")
            finally:
                other.release()
                first.release()
            self.assertFalse(controller_status("Alpha")["active"])

    def test_dead_owner_is_cleaned_before_next_acquire(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"RS_CONTROLLER_ROOT": tmp}):
            stale = acquire_controller("Alpha", "old", "runner", pid=99999999)
            self.assertFalse(controller_status("Alpha")["active"])
            replacement = acquire_controller("Alpha", "new", "runner")
            replacement.release()
            stale.release()

    def test_delegated_child_joins_without_releasing_parent(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"RS_CONTROLLER_ROOT": tmp}):
            parent = acquire_controller("Alpha", "mining", "supervised_runner")
            try:
                with patch.dict(os.environ, {LEASE_ENV: parent.lease_id}):
                    child = acquire_or_join_controller("Alpha", "route", "ml2_route_executor")
                self.assertFalse(child.owns)
                child.release()
                self.assertTrue(controller_status("Alpha")["active"])
            finally:
                parent.release()

    def test_stop_request_is_scoped_to_active_lease(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"RS_CONTROLLER_ROOT": tmp}):
            lease = acquire_controller("Alpha", "mining", "runner")
            try:
                result = request_controller_stop("Alpha")
                self.assertEqual(result["status"], "stop_requested")
                self.assertTrue(lease.stop_requested())
                self.assertEqual(controller_status("Alpha")["status"], "stop_requested")
            finally:
                lease.release()


if __name__ == "__main__":
    unittest.main()
