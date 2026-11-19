"""E5M: regression for unique V9.2 BTC/SOL hourly source-writer ownership.

The tests execute the inline consumer-only Git source gate against local,
temporary Git commits; never send a request or dispatch a GitHub workflow.
"""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest


PAIRED = Path(".github/workflows/v92-sol-paired-prospective-paper.yml")
OWNER = Path(".github/workflows/v92-selected-prospective-third-paper.yml")
CI = Path(".github/workflows/atlas-e5m-single-writer-tests.yml")


def gate_python():
    body = PAIRED.read_text(encoding="utf-8")
    start = "          python3 - \"$source\" \"$target\" <<'PY'\n"
    end = "\n          PY"
    assert body.count(start) == 1
    section = body.split(start, 1)[1].split(end, 1)[0]
    return textwrap.dedent(section)


class SourceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-00Z")
        self.path = self.root / ("forward/v92_prospective_selected/hourly/" + self.target + ".json")
        self.path.parent.mkdir(parents=True)
        self.data = {
            "mode": "V92_SELECTED_CANDLE_IMMUTABLE_HOURLY_FORWARD_PAPER_ONLY",
            "targetClosed1HUTC": self.target.replace("-00Z", ":00:00Z"),
            "sourceVerifiedSameHour": True,
            "sourceV7AndV91RecomputedExactMatch": True,
            "noPastHourBackfill": True,
            "noBrokerOrders": True,
            "noUserNotifications": True,
            "assets": {"BTCUSDT": {}, "SOLUSDT": {}},
            "capturedAtUTC": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self.git("init", "-q")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "user.name", "e5m-local-test")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def seal(self):
        self.path.write_text(json.dumps(self.data) + "\n")
        self.git("add", "forward/v92_prospective_selected/hourly")
        self.git("commit", "-q", "-m", "sealed mock source")

    def run_gate(self):
        return subprocess.run(
            [sys.executable, "-c", gate_python(), str(self.path.relative_to(self.root)), self.target],
            cwd=self.root, capture_output=True, text=True,
        )

    def test_matching_precommitted_paper_hour_accepted(self):
        self.seal()
        res = self.run_gate()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("CONSUME_EXISTING_GIT_SEALED_HOUR_ONLY", res.stdout)

    def test_wrong_hour_rejected(self):
        self.data["targetClosed1HUTC"] = "2026-11-18T00:00:00Z"
        self.seal()
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_live_orders_or_alerts_rejected(self):
        for field in ("noBrokerOrders", "noUserNotifications", "noPastHourBackfill"):
            with self.subTest(field=field):
                self.data[field] = False
                self.seal()
                self.assertNotEqual(self.run_gate().returncode, 0)
                self.data[field] = True

    def test_unverified_source_parity_rejected(self):
        self.data["sourceV7AndV91RecomputedExactMatch"] = False
        self.seal()
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_wrong_symbol_or_mode_rejected(self):
        self.data["assets"] = {"SOLUSDT": {}}
        self.seal()
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_file_not_git_sealed_rejected(self):
        self.path.write_text(json.dumps(self.data))
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_git_committed_blob_tamper_rejected(self):
        self.seal()
        self.path.write_text(self.path.read_text().replace("SOLUSDT", "SOLTEST"))
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_future_capture_rejected(self):
        self.data["capturedAtUTC"] = "2099-01-01T00:00:00Z"
        self.seal()
        self.assertNotEqual(self.run_gate().returncode, 0)


class WorkflowIsolationTests(unittest.TestCase):
    def test_paired_source_generator_and_staging_removed(self):
        t = PAIRED.read_text(encoding="utf-8")
        self.assertNotIn("python3 -u v92_prospective_selected.py", t)
        self.assertNotIn("git add forward/v92_prospective_selected/hourly", t)
        self.assertNotIn("git add forward/v92_prospective_selected/third_paper_account", t)
        self.assertIn("if: steps.sealed.outputs.ready == 'true'", t)
        self.assertIn("V92_SOL_PAIRED_SOURCE_NOT_YET_SEALED_SAFE_SKIP", t)
        self.assertIn('test -z "$(git status --porcelain -- forward/v92_prospective_selected/hourly)"', t)
        self.assertIn("git add forward/v92_prospective_selected/paired_sol_account.json", t)
        self.assertNotIn("gh api --method POST", t)

    def test_owner_e5j_and_e5d_dispatch_unchanged(self):
        t = OWNER.read_text(encoding="utf-8")
        self.assertIn("atlas_e5j_v92_immutable_seal.py", t)
        self.assertIn("steps.seal.outputs.committed == 'true'", t)
        self.assertIn("atlas-e5d-silent-hourly-observer.yml/dispatches", t)
        self.assertIn("--asset btc-sol", t)

    def test_consumer_only_source_is_git_tracked(self):
        t = PAIRED.read_text(encoding="utf-8")
        self.assertIn('["git","ls-files","-s","--",str(file)]', t)
        self.assertIn('["git","hash-object",str(file)]', t)
        self.assertIn("noPastHourBackfill", t)
        self.assertIn("noBrokerOrders", t)
        self.assertIn("noUserNotifications", t)

    def test_ci_read_only(self):
        t = CI.read_text(encoding="utf-8")
        unprivileged = t.split("      - name: Prove read-only test environment", 1)[0]
        self.assertIn("contents: read", unprivileged)
        self.assertNotIn("actions: write", unprivileged)
        self.assertNotIn("GH_TOKEN", unprivileged)
        self.assertNotIn("git push", unprivileged)


if __name__ == "__main__":
    unittest.main()
