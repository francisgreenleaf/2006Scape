#!/usr/bin/env python3
"""Small local helpers for low-overhead runner timing logs."""

import datetime as dt
import json
import time


class TickEventWriter:
    """Adds consistent timing metadata to JSONL runner events.

    This helper is intentionally local-only: it never observes the game or calls
    the bridge. Runners can add detailed timing without increasing server/client
    traffic.
    """

    def __init__(self):
        self.started_at = time.monotonic()
        self.last_event_at = None
        self.seq = 0

    @staticmethod
    def utc_now():
        return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")

    def write(self, handle, event, data):
        now = time.monotonic()
        payload = {
            "ts": self.utc_now(),
            "event": event,
            "seq": self.seq,
            "runElapsedMs": int((now - self.started_at) * 1000),
        }
        if self.last_event_at is not None:
            payload["sincePrevEventMs"] = int((now - self.last_event_at) * 1000)
        payload.update(data)
        self.last_event_at = now
        self.seq += 1
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
