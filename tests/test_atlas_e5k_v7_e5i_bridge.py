"""Regression tests for E5K's token-scoped, read-only V7 -> E5I bridge.

Execute exactly the production workflow's Python definitions with an isolated
fake GitHub API. Never dispatch a live workflow during testing.
"""
import base64
import json
import os
import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


WORKFLOW = Path(".github/workflows/atlas-e5h-safe-v7-v9-source-rescue.yml")
E5I = "/actions/workflows/atlas-e5i-v91-v92-source-chain-rescue.yml/dispatches"


def bridge_namespace():
    body = WORKFLOW.read_text(encoding="utf-8")
    begin = "          python3 - <<'PY'\n"
    end = "          # Self-test only pure target, bounds, wait window and sensitive workflow allowlist."
    assert body.count(begin) == 1
    assert body.count(end) == 1
    definitions = textwrap.dedent(body.split(begin, 1)[1].split(end, 1)[0])
    with patch.dict(os.environ, {"GH_TOKEN": "X" * 40}):
        ns = {}
        exec(compile(definitions, str(WORKFLOW), "exec"), ns)
    return ns


class FakeAPI:
    def __init__(self, ns, now):
        self.ns = ns
        self.now = now
        self.calls = []
        self.missing_v7 = set()
        self.bad_v7 = {}
        self.sealed_stages = set()
        self.prior = []

    def __call__(self, method, path, body=None, params=None):
        self.calls.append((method, path, body, params))
        if method == "GET" and path.startswith("/contents/"):
            file_path = path.removeprefix("/contents/")
            if file_path in self.missing_v7:
                return 404, b""
            targets = [stage[3] + "/" + self.ns["filename"](self.now)
                       for stage in self.ns["TASKS"][1:]]
            if file_path in targets:
                payload = {
                    "targetClosed1HUTC": self.now.strftime("%Y-%m-%dT%H:00:00Z"),
                    "status": "VERIFIED_PAPER_OBSERVATION",
                    "brokerOrders": False,
                    "productionSystemModified": False,
                    "sourceVerifiedPaperOnly": True,
                }
                payload.update(self.bad_v7.get(file_path, {}))
                raw = json.dumps(payload).encode()
                doc = {
                    "type": "file", "path": file_path,
                    "sha": "f" * 40, "size": len(raw),
                    "encoding": "base64",
                    "content": base64.b64encode(raw).decode(),
                }
                return 200, json.dumps(doc).encode()
            if file_path in self.sealed_stages:
                return 200, json.dumps({
                    "type": "file", "path": file_path, "sha": "e" * 40
                }).encode()
            return 404, b""
        if method == "GET" and path.startswith("/actions/workflows/"):
            return 200, json.dumps({
                "total_count": len(self.prior), "workflow_runs": self.prior
            }).encode()
        if method == "POST" and path == E5I:
            assert body == {"ref": "main"} and params is None
            return 204, b""
        raise AssertionError(f"Unapproved GitHub request: {method} {path}")

    def posts(self):
        return [call for call in self.calls if call[0] == "POST"]

    def upstream_paths(self):
        return [s[3] + "/" + self.ns["filename"](self.now)
                for s in self.ns["TASKS"][1:]]


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.ns = bridge_namespace()
        self.now = datetime(2026, 11, 19, 4, 25, tzinfo=timezone.utc)
        self.api = FakeAPI(self.ns, self.now)
        self.ns["make_request"] = self.api

    def bridge(self, when=None, clock=None):
        when = when or self.now
        return self.ns["e5k_bridge"](when, clock=clock or (lambda: when))

    def test_both_verified_v7_sources_wake_only_e5i(self):
        self.assertEqual(self.bridge(),
                         "E5K_E5I_DISPATCH_ACCEPTED_NOT_PROOF_OF_SOURCE_CAPTURE")
        self.assertEqual(len(self.api.posts()), 1)
        self.assertEqual(self.api.posts()[0][1], E5I)

    def test_missing_v7_source_never_dispatches(self):
        self.api.missing_v7.add(self.api.upstream_paths()[0])
        self.assertEqual(self.bridge(),
                         "E5K_WAITING_FOR_BOTH_VERIFIED_ORIGINAL_V7_SOURCES")
        self.assertEqual(self.api.posts(), [])

    def test_wrong_hour_v7_source_fails_closed(self):
        self.api.bad_v7[self.api.upstream_paths()[0]] = {
            "targetClosed1HUTC": "2026-11-19T03:00:00Z"}
        with self.assertRaisesRegex(ValueError, "E5K_ORIGINAL_SOURCE_NOT_VERIFIED"):
            self.bridge()
        self.assertEqual(self.api.posts(), [])

    def test_order_enabled_v7_source_fails_closed(self):
        self.api.bad_v7[self.api.upstream_paths()[1]] = {"brokerOrders": True}
        with self.assertRaisesRegex(ValueError, "E5K_ORIGINAL_SOURCE_NOT_VERIFIED"):
            self.bridge()
        self.assertEqual(self.api.posts(), [])

    def test_stage_complete_no_unnecessary_dispatch(self):
        self.api.sealed_stages = {folder + "/" + self.ns["filename"](self.now)
                                  for _, _, folder in self.ns["E5K_STAGES"]}
        self.assertEqual(self.bridge(),
                         "E5K_ALL_FOUR_DOWNSTREAM_SOURCE_FILES_ALREADY_SEALED")
        self.assertEqual(self.api.posts(), [])

    def test_running_e5i_prevents_double_dispatch(self):
        self.api.prior = [{
            "created_at": "2026-11-19T04:23:00Z",
            "event": "workflow_dispatch", "head_branch": "main",
            "status": "in_progress"
        }]
        self.assertEqual(self.bridge(), "E5K_E5I_DISPATCH_ALREADY_RUNNING")
        self.assertEqual(self.api.posts(), [])

    def test_two_prior_e5i_attempts_capped(self):
        self.api.prior = [{
            "created_at": f"2026-11-19T04:{minute}:00Z",
            "event": "workflow_dispatch", "head_branch": "main",
            "status": "completed"
        } for minute in ("17", "20")]
        self.assertEqual(self.bridge(), "E5K_MAX_TWO_E5I_DISPATCHES_THIS_HOUR")
        self.assertEqual(self.api.posts(), [])

    def test_early_time_and_rollover_not_dispatched(self):
        early = self.now.replace(minute=15)
        self.assertEqual(self.bridge(when=early), "E5K_OUTSIDE_E5I_SAFE_DISPATCH_WINDOW")
        self.assertEqual(self.bridge(clock=lambda: self.now.replace(minute=50)),
                         "E5K_CLOCK_ROLLOVER_OR_WINDOW_CLOSED_NO_DISPATCH")
        self.assertEqual(self.api.posts(), [])

    def test_bounded_followup_wakes_at_verified_hour(self):
        self.assertEqual(self.ns["e5k_follow_up"](
            self.now, clock=lambda:self.now,
            sleep=lambda seconds: self.fail("unexpected real wait")),
            "E5K_E5I_DISPATCH_ACCEPTED_NOT_PROOF_OF_SOURCE_CAPTURE")
        self.assertEqual(len(self.api.posts()), 1)

    def test_missing_upstream_bounded_timeout_without_backfill(self):
        self.api.missing_v7.add(self.api.upstream_paths()[0])
        start = self.now
        times = [start, start.replace(minute=28)]
        def clock():
            return times.pop(0) if times else start.replace(minute=28)
        self.assertEqual(self.ns["e5k_follow_up"](
            start, clock=clock, sleep=lambda _:None),
            "E5K_WAITING_FOR_BOTH_VERIFIED_ORIGINAL_V7_SOURCES_TIMEOUT_NO_FAKE_SOURCE")
        self.assertEqual(self.api.posts(), [])

    def test_static_never_write_sources_or_place_orders(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ATLAS_E5K_MOCKED_V7_TO_E5I_BRIDGE_SAFE", content)
        self.assertIn('E5K_MAX_WAIT_SECONDS=150', content)
        self.assertIn('source.get("brokerOrders") is False', content)
        self.assertNotIn("/orders", content)
        self.assertNotIn("git push", content)
        self.assertNotIn("git commit", content)
        self.assertNotIn("retroactive_backfill", content)


if __name__ == "__main__":
    unittest.main()
