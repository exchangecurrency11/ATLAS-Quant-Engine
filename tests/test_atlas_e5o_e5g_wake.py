"""E5O fail-closed no-network regression of E5G post-E5D health wake.

Only inspects checked-in workflow text. Never executes market code, publishes a
journal, dispatches Actions, modifies a paper portfolio, or sends an alert.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
E5G = ROOT / ".github/workflows/atlas-e5g-hourly-source-health.yml"
E5D = ROOT / ".github/workflows/atlas-e5d-silent-hourly-observer.yml"
CI = ROOT / ".github/workflows/atlas-e5o-e5g-wake-tests.yml"
E5D_NAME = "ATLAS E5D separated read-only observer and journal-only writer"

class E5GObserverWakeSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e5g = E5G.read_text(encoding="utf-8")
        cls.e5d = E5D.read_text(encoding="utf-8")
        cls.ci = CI.read_text(encoding="utf-8")
        cls.run_trigger = cls.e5g.split("  workflow_run:\n", 1)[1].split("  workflow_dispatch:\n", 1)[0]

    def test_e5d_wake_is_single_exact_named_source(self):
        self.assertEqual(self.run_trigger.count("      - " + E5D_NAME + "\n"), 1)
        self.assertEqual(self.e5d.splitlines()[0], "name: " + E5D_NAME)

    def test_existing_four_event_sources_stay_registered(self):
        for name in (
            "Publish BTC SOL Market Data",
            "V9 Hourly BTC ETH SOL Market Context (paper only)",
            "V9.2 selected SOL reversals independent forward paper 1000 USDT NO ALERTS",
            "V9.2 ETH sealed hourly selected-pattern watch third shared paper NO ALERTS",
        ):
            with self.subTest(source=name):
                self.assertEqual(self.run_trigger.count("      - " + name + "\n"), 1)

    def test_no_extra_source_and_main_completed_only(self):
        sources = re.findall(r"(?m)^      - (.+)$", self.run_trigger)
        self.assertEqual(len(sources), 5)
        self.assertEqual(len(sources), len(set(sources)))
        self.assertIn("    types: [completed]\n", self.run_trigger)
        self.assertIn("    branches: [main]\n", self.run_trigger)

    def test_existing_backup_clocks_and_dispatch_remain(self):
        self.assertIn("    - cron: '31,58 * * * *'", self.e5g)
        self.assertIn("  workflow_dispatch:\n", self.e5g)
        self.assertIn("    branches: [main]\n", self.e5g)

    def test_75_minute_mature_gate_and_no_early_consumption(self):
        self.assertIn('d["graceMinutesAfterClose"]==75', self.e5g)
        self.assertIn('len(d["hourlyMatrix"])==12', self.e5g)
        self.assertIn("E5G_EARLY_TRIGGER_SAFE_SKIP_UNTIL_15_MINUTES", self.e5g)
        matches = re.findall(r"(?m)^          eligible=now.minute>=(\d+)$", self.e5g)
        self.assertEqual(matches, ["15"])
        cutoff = int(matches[0])
        for minute in (0, 4, 14):
            self.assertFalse(minute >= cutoff)
        for minute in (15, 17, 31, 58):
            self.assertTrue(minute >= cutoff)

    def test_existing_immutable_hour_guard_and_single_writer(self):
        self.assertIn('output.exists()', self.e5g)
        self.assertIn('with path.open("xb") as f:f.write(raw)', self.e5g)
        self.assertIn("atlas-e5g-single-immutable-health-check-per-utc-hour", self.e5g)
        self.assertIn("  cancel-in-progress: false", self.e5g)

    def test_no_new_access_or_execution_routes(self):
        self.assertIn("permissions:\n  contents: read\n", self.e5g)
        self.assertIn("    if: ${{ needs.gate.outputs.needed == 'true' }}", self.e5g)
        self.assertIn("ref: research/atlas-core-e5g-hourly-health-20261115", self.e5g)
        self.assertIn("persist-credentials: false", self.e5g)
        self.assertNotIn("gh workflow run", self.e5g)
        self.assertNotIn("/dispatches", self.e5g)

    def test_source_journal_is_existing_post_commit_observer(self):
        self.assertIn("  workflow_dispatch:\n", self.e5d)
        self.assertIn("atlas-e5d-hourly-append-only-journal", self.e5d)
        self.assertIn("ref: research/atlas-core-v8b-journal-audit-20261115", self.e5d)
        self.assertIn("ATLAS_E5D_JOURNAL_ADD_ONLY_SUCCESS", self.e5d)

    def test_ci_is_pr_only_and_read_only(self):
        self.assertIn("  pull_request:\n", self.ci)
        self.assertIn("permissions:\n  contents: read\n", self.ci)
        self.assertIn("persist-credentials: false", self.ci)
        for disallowed in ("  workflow_dispatch:", "  schedule:", "actions: write", "contents: write", "gh workflow run", "git push", "secrets."):
            self.assertNotIn(disallowed, self.ci)

if __name__ == "__main__":
    unittest.main()
