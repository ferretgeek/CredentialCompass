from __future__ import annotations

import time
import unittest

from credential_compass.cpa_client import DemoCPAClient
from credential_compass.state import CompassState


def wait_for_scan(state: CompassState, timeout: float = 3) -> dict:
    deadline = time.monotonic() + timeout
    snapshot = state.snapshot()
    while snapshot["running"] and time.monotonic() < deadline:
        time.sleep(0.02)
        snapshot = state.snapshot()
    return snapshot


class StateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = CompassState(DemoCPAClient(), live_probe=True, concurrency=4)

    def test_demo_scan_completes_with_all_records_counted(self) -> None:
        self.assertTrue(self.state.start_scan(concurrency=4, limit=0))
        snapshot = wait_for_scan(self.state)
        self.assertFalse(snapshot["running"])
        self.assertEqual(snapshot["phase"], "complete")
        self.assertEqual(snapshot["percent"], 100.0)
        self.assertEqual(snapshot["summary"]["total"], 6)

    def test_public_snapshot_masks_accounts_and_raw_ids(self) -> None:
        self.state.start_scan(concurrency=4, limit=0)
        snapshot = wait_for_scan(self.state)
        serialized = str(snapshot)
        self.assertNotIn("aurora@example.com", serialized)
        self.assertNotIn("demo-aurora.json", serialized)
        self.assertIn("a•••@e•••.com", serialized)

    def test_reveal_requires_explicit_snapshot_mode(self) -> None:
        self.state.start_scan(concurrency=4, limit=1)
        wait_for_scan(self.state)
        self.assertEqual(self.state.snapshot(reveal=True)["items"][0]["account"], "aurora@example.com")

    def test_only_one_scan_can_run(self) -> None:
        self.assertTrue(self.state.start_scan(concurrency=1, limit=0))
        self.assertFalse(self.state.start_scan(concurrency=1, limit=0))
        wait_for_scan(self.state)

    def test_status_change_uses_opaque_handle(self) -> None:
        self.state.start_scan(concurrency=4, limit=1)
        snapshot = wait_for_scan(self.state)
        handle = snapshot["items"][0]["handle"]
        result = self.state.change_status([handle], disabled=True)
        self.assertEqual(result, {"matched": 1, "changed": 1, "failed": 0})
        self.assertTrue(self.state.snapshot()["items"][0]["disabled"])

    def test_unknown_handles_do_not_reach_client(self) -> None:
        result = self.state.change_status(["cc_unknown"], disabled=True)
        self.assertEqual(result, {"matched": 0, "changed": 0, "failed": 0})


if __name__ == "__main__":
    unittest.main()
