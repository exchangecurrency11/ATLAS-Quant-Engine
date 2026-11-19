"""E5N: fail-closed regression for V9.2 shared queue/source ownership.

This module reads workflow YAML as text; it never contacts the network,
executes a source runner, dispatches Actions, or makes any trade.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BTC = ROOT / ".github/workflows/v92-selected-prospective-third-paper.yml"
ETH = ROOT / ".github/workflows/v92-eth-prospective-third-paper.yml"
E5I = ROOT / ".github/workflows/atlas-e5i-v91-v92-source-chain-rescue.yml"
CI = ROOT / ".github/workflows/atlas-e5n-v92-queue-tests.yml"
GROUP = "v92-selected-third-paper-no-orders"


def read(path):
    return path.read_text(encoding="utf-8")


def root_concurrency(source):
    """Read only the root concurrency stanza (not job or inline script text)."""
    match = re.search(r"(?m)^concurrency:\n((?: {2}[a-z][a-z-]*: [^\n]+\n)+)", source)
    if not match:
        raise AssertionError("E5N_ROOT_CONCURRENCY_MISSING")
    pairs = re.findall(r"(?m)^ {2}([a-z][a-z-]*): ([^\n]+)$", match.group(1))
    result = dict(pairs)
    if len(pairs) != len(result):
        raise AssertionError("E5N_DUPLICATE_CONCURRENCY_KEY")
    return result


class SharedQueueSafety(unittest.TestCase):
    def setUp(self):
        self.btc = read(BTC)
        self.eth = read(ETH)

    def test_both_workflows_have_same_serial_owner(self):
        for doc in (self.btc, self.eth):
            with self.subTest(doc=doc.splitlines()[0]):
                self.assertEqual(root_concurrency(doc)["group"], GROUP)
                self.assertEqual(doc.count("\nconcurrency:\n"), 1)

    def test_both_use_max_pending_queue(self):
        for doc in (self.btc, self.eth):
            with self.subTest(doc=doc.splitlines()[0]):
                self.assertEqual(root_concurrency(doc)["queue"], "max")

    def test_running_writer_is_never_cancelled(self):
        for doc in (self.btc, self.eth):
            with self.subTest(doc=doc.splitlines()[0]):
                self.assertEqual(root_concurrency(doc)["cancel-in-progress"], "false")
                self.assertEqual(
                    set(root_concurrency(doc)),
                    {"group", "queue", "cancel-in-progress"},
                )

    def test_source_owners_keep_same_hour_no_backfill_gates(self):
        self.assertIn("V92", self.btc)
        self.assertIn("E5J first-writer-wins", self.btc)
        self.assertIn("E5J first-writer-wins", self.eth)
        self.assertIn("atlas_e5j_v92_immutable_seal.py", self.btc)
        self.assertIn("atlas_e5j_v92_immutable_seal.py", self.eth)
        self.assertIn("steps.seal.outputs.committed == 'true'", self.btc)
        self.assertIn("steps.seal.outputs.committed == 'true'", self.eth)
        self.assertIn("atlas-e5d-silent-hourly-observer.yml/dispatches", self.btc)
        self.assertIn("atlas-e5d-silent-hourly-observer.yml/dispatches", self.eth)

    def test_no_e5d_dispatch_before_source_seal(self):
        for doc in (self.btc, self.eth):
            with self.subTest(doc=doc.splitlines()[0]):
                self.assertLess(
                    doc.index("name: E5J first-writer-wins"),
                    doc.index("name: Dispatch E5D after verified"),
                )

    def test_all_original_schedulers_remain(self):
        self.assertIn("17,29,39,49,56 * * * *", self.btc)
        self.assertIn("18,30,40,50,57 * * * *", self.eth)
        for doc in (self.btc, self.eth):
            self.assertIn("workflow_dispatch:", doc)
            self.assertIn("branches: [main]", doc)

    def test_e5i_dispatch_cap_unchanged(self):
        text = read(E5I)
        self.assertIn("MAX_DISPATCHES_PER_STAGE_HOUR = 2", text)
        self.assertIn("if count >= MAX_DISPATCHES_PER_STAGE_HOUR:", text)
        self.assertIn("MAX_TWO_DISPATCH_ATTEMPTS_PER_HOUR", text)
        self.assertIn('item.get("event") == "workflow_dispatch"', text)
        self.assertIn('if status != "completed":', text)
        self.assertIn("UPSTREAM_WORKFLOW_STILL_RUNNING", text)
        self.assertIn("MISSING_EXACT_HOUR_UPSTREAM_SOURCE", text)

    def test_workflow_permissions_not_elevated(self):
        for doc in (self.btc, self.eth):
            with self.subTest(doc=doc.splitlines()[0]):
                prefix = doc.split("\nconcurrency:\n")[0]
                self.assertIn("permissions:\n  actions: write\n  contents: write", prefix)
                self.assertNotIn("id-token: write", prefix)
                self.assertNotIn("pull-requests: write", prefix)

    def test_pr_ci_cannot_dispatch_or_write(self):
        yaml = read(CI)
        self.assertIn("pull_request:", yaml)
        self.assertIn("permissions:\n  contents: read", yaml)
        self.assertIn("persist-credentials: false", yaml)
        self.assertNotIn("actions: write", yaml)
        self.assertNotIn("id-token: write", yaml)
        self.assertNotIn("git push", yaml)
        self.assertNotIn("GH_TOKEN", yaml)


if __name__ == "__main__":
    unittest.main()
