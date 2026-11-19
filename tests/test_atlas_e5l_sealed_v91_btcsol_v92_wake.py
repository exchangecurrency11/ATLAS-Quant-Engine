"""Pure mocked regression for the actual E5L source-sealed V9.2 dispatch code.

No GitHub requests are sent by tests. The privileged job has no checkout.
"""
import base64
import hashlib
import json
import os
import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


WORKFLOW = Path(".github/workflows/v91-prospective-hourly-shadow.yml")
CI = Path(".github/workflows/atlas-e5l-direct-wake-tests.yml")
V92_WAKE = "/actions/workflows/v92-selected-prospective-third-paper.yml/dispatches"
TARGET = "2026-11-19T07-00Z"


def production_namespace():
    text = WORKFLOW.read_text(encoding="utf-8")
    block = text.split("      - name: E5L verify real Git blob and dispatch only bounded current-hour V9.2 (NO ORDERS)\n", 1)[1]
    marker = "          python3 - <<'PY'\n"
    assert block.count(marker) == 1
    body = block.split(marker, 1)[1].split("\n          PY", 1)[0]
    namespace = {"__name__": "atlas_e5l_unit_test"}
    exec(compile(textwrap.dedent(body), str(WORKFLOW), "exec"), namespace)
    return namespace


class FakeGitHub:
    def __init__(self):
        self.calls = []
        self.upstream_missing = False
        self.bad_source = {}
        self.tamper_sha = False
        self.upstream_status = 200
        self.downstream_status = 404
        self.post_status = 204

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET" and path.startswith("/contents/forward/v91_prospective_retest/hourly/"):
            if self.upstream_missing:
                return 404, b""
            if self.upstream_status != 200:
                return self.upstream_status, b""
            source = {
                "mode": "V91_PROSPECTIVE_4H_RETEST_IMMUTABLE_PAPER_SHADOW",
                "targetClosed1HUTC": "2026-11-19T07:00:00Z",
                "capturedAtUTC": "2026-11-19T07:16:21Z",
                "sourceVerifiedSameHour": True,
                "V7SnapshotAndIndependentRecomputeExactMatch": True,
                "retrospectiveSnapshotBackfillForbidden": True,
                "noBrokerOrders": True,
                "noNotifications": True,
                "noV7ProductionOrNotificationChanges": True,
                "assets": {"BTCUSDT": {}, "SOLUSDT": {}},
            }
            source.update(self.bad_source)
            data = json.dumps(source, sort_keys=True).encode()
            blobsha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if self.tamper_sha:
                blobsha = "a" * 40 if blobsha != "a" * 40 else "b" * 40
            response = {
                "type": "file",
                "path": "forward/v91_prospective_retest/hourly/" + TARGET + ".json",
                "encoding": "base64", "content": base64.b64encode(data).decode(),
                "sha": blobsha, "size": len(data),
            }
            return 200, json.dumps(response).encode()
        if method == "GET" and path.startswith("/contents/forward/v92_prospective_selected/hourly/"):
            return self.downstream_status, b""
        if method == "POST" and path == V92_WAKE:
            assert body == {"ref": "main"}
            return self.post_status, b""
        raise AssertionError("Unexpected GitHub API access: " + str((method, path, body)))

    def posts(self):
        return [c for c in self.calls if c[0] == "POST"]


class E5LSealedWakeTests(unittest.TestCase):
    def setUp(self):
        self.ns = production_namespace()
        self.api = FakeGitHub()
        self.now = datetime(2026, 11, 19, 7, 18, tzinfo=timezone.utc)
        self.env = patch.dict(os.environ, {
            "V91_SEALED_TARGET": TARGET,
            "GITHUB_REPOSITORY": "exchangecurrency11/ATLAS-Quant-Engine",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def wake(self, now=None, clock=None):
        now = now or self.now
        return self.ns["e5l_wake"](now=now, api=self.api,
                                    clock=clock or (lambda: now))

    def test_verified_exact_hour_dispatches_only_v92_btc_sol(self):
        self.assertEqual(self.wake(), "E5L_V92_DISPATCH_ACCEPTED_NOT_A_VERIFIED_SOURCE_SEAL")
        self.assertEqual(len(self.api.posts()), 1)
        self.assertEqual(self.api.posts()[0], ("POST", V92_WAKE, {"ref": "main"}))
        self.assertEqual(len(self.api.calls), 3)

    def test_existing_immutable_v92_hour_never_wakes(self):
        self.api.downstream_status = 200
        self.assertEqual(self.wake(), "E5L_V92_EXISTING_SOURCE_FILE_NO_DISPATCH_NOT_A_NEW_CAPTURE")
        self.assertEqual(self.api.posts(), [])

    def test_missing_prior_git_sealed_v91_hour_fails_closed(self):
        self.api.upstream_missing = True
        with self.assertRaisesRegex(ValueError, "E5L_GIT_SEALED_V91_SOURCE_ABSENT"):
            self.wake()
        self.assertEqual(self.api.posts(), [])

    def test_unexpected_api_error_never_dispatched(self):
        self.api.upstream_status = 403
        with self.assertRaisesRegex(ValueError, "E5L_V91_SOURCE_READ_FAILED"):
            self.wake()
        self.assertEqual(self.api.posts(), [])
        self.api.upstream_status = 200
        self.api.downstream_status = 500
        with self.assertRaisesRegex(ValueError, "E5L_V92_LOOKUP_UNCERTAIN"):
            self.wake()
        self.assertEqual(self.api.posts(), [])

    def test_tampered_source_sha_never_wakes(self):
        self.api.tamper_sha = True
        with self.assertRaisesRegex(ValueError, "E5L_V91_SOURCE_BLOB_MISMATCH"):
            self.wake()
        self.assertEqual(self.api.posts(), [])

    def test_wrong_closed_hour_is_rejected(self):
        self.api.bad_source["targetClosed1HUTC"] = "2026-11-19T06:00:00Z"
        with self.assertRaisesRegex(ValueError, "E5L_V91_SOURCE_NOT_VERIFIED"):
            self.wake()
        self.assertEqual(self.api.posts(), [])

    def test_orders_notifications_or_backfill_are_rejected(self):
        for field, value in (
            ("noBrokerOrders", False),
            ("noNotifications", False),
            ("retrospectiveSnapshotBackfillForbidden", False),
            ("V7SnapshotAndIndependentRecomputeExactMatch", False),
            ("sourceVerifiedSameHour", False),
        ):
            with self.subTest(field=field):
                self.api.bad_source = {field: value}
                self.api.calls.clear()
                with self.assertRaisesRegex(ValueError, "E5L_V91_SOURCE_NOT_VERIFIED"):
                    self.wake()
                self.assertEqual(self.api.posts(), [])

    def test_wrong_symbol_or_mode_rejected(self):
        for field, value in (
            ("assets", {"BTCUSDT": {}}),
            ("mode", "LIVE_ENTRY"),
        ):
            with self.subTest(field=field):
                self.api.bad_source = {field: value}
                self.api.calls.clear()
                with self.assertRaisesRegex(ValueError, "E5L_V91_SOURCE_NOT_VERIFIED"):
                    self.wake()
                self.assertEqual(self.api.posts(), [])

    def test_future_capture_timestamp_fails_closed(self):
        self.api.bad_source["capturedAtUTC"] = "2026-11-19T07:35:00Z"
        with self.assertRaisesRegex(ValueError, "E5L_V91_CAPTURE_TIMESTAMP_INVALID"):
            self.wake()
        self.assertEqual(self.api.posts(), [])

    def test_early_late_and_wrong_hour_no_api_access(self):
        for now in (
            self.now.replace(minute=11),
            self.now.replace(minute=50),
            self.now.replace(hour=8),
        ):
            with self.subTest(now=now):
                self.api.calls.clear()
                self.assertEqual(self.wake(now), "E5L_CLOCK_OUTSIDE_CURRENT_VERIFIED_SOURCE_WINDOW_SAFE_SKIP")
                self.assertEqual(self.api.calls, [])

    def test_source_sealed_in_15th_minute_dispatches_current_hour(self):
        now = self.now.replace(minute=15)
        self.api.bad_source["capturedAtUTC"] = "2026-11-19T07:15:00Z"
        self.assertEqual(self.wake(now), "E5L_V92_DISPATCH_ACCEPTED_NOT_A_VERIFIED_SOURCE_SEAL")
        self.assertEqual(len(self.api.posts()), 1)

    def test_clock_rollover_between_validation_and_dispatch(self):
        later = self.now.replace(hour=8, minute=0)
        self.assertEqual(self.wake(clock=lambda: later), "E5L_CLOCK_ROLLOVER_NO_DISPATCH")
        self.assertEqual(self.api.posts(), [])

    def test_nonaccepted_dispatch_does_not_claim_seal(self):
        self.api.post_status = 403
        with self.assertRaisesRegex(ValueError, "E5L_V92_DISPATCH_NOT_ACCEPTED"):
            self.wake()

    def test_bad_target_format_rejected_before_read(self):
        with patch.dict(os.environ, {"V91_SEALED_TARGET": "../06-00Z"}):
            with self.assertRaisesRegex(ValueError, "E5L_TARGET_NOT_EXACT"):
                self.wake()
        self.assertEqual(self.api.calls, [])

    def test_run_code_does_not_have_an_implicit_live_side_effect(self):
        # Merely extracting and compiling the privileged production code
        # does not make any request or write source files.
        self.assertEqual(self.api.calls, [])
        self.assertTrue(callable(self.ns["e5l_wake"]))

    def test_credential_isolated_from_research_strategy_runner(self):
        wf = WORKFLOW.read_text()
        main, wake = wf.split("\n  v92-btc-sol-wake:\n", 1)
        assert "actions: write" not in main
        assert "    permissions:\n      contents: read\n      actions: write" in wake
        assert "needs: hourly-paper" in wake
        assert "new_source_sealed == 'true'" in wake
        assert "id: persist" in main
        assert 'echo "committed=true" >> "$GITHUB_OUTPUT"' in main
        assert "git push" not in wake
        assert "actions/checkout" not in wake
        assert "test -s" not in wake
        assert "binance" not in wake.lower()
        assert wake.count(V92_WAKE) == 1
        assert "workflow_dispatch:" in main
        assert "echo \"committed=true\"" in main

    def test_read_only_ci_and_no_network_testing(self):
        ci = CI.read_text()
        header = ci.split("      - name: Prove CI", 1)[0]
        assert "contents: read" in header
        assert "actions: write" not in header
        assert "git push" not in header
        assert "GH_TOKEN" not in header
        assert "gh api" not in header


if __name__ == "__main__":
    unittest.main()
