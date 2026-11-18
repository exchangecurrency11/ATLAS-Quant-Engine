"""E5J: actual local Git race simulations; no exchange, orders, or alerts."""
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import scripts.atlas_e5j_v92_immutable_seal as seal_module

from scripts.atlas_e5j_v92_immutable_seal import BRANCH, CONFIG, SHARED, SealError, seal


def run(*args, cwd=None):
    p = subprocess.run(
        list(args), cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if p.returncode:
        raise AssertionError(f"command failed {args}: {p.stderr}")
    return p.stdout.strip()


def write(repo, path, value):
    p = Path(repo) / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(value, encoding="utf-8")


class ImmutableSealRaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.origin = self.base / "origin.git"
        run("git", "init", "--bare", str(self.origin))
        seed = self.clone("seed", branch=False)
        run("git", "checkout", "-b", BRANCH, cwd=seed)
        write(seed, "README.md", "Immutable research test seed\n")
        run("git", "add", "README.md", cwd=seed)
        run("git", "-c", "user.email=test@example.com",
            "-c", "user.name=Research Test", "commit", "-m", "seed", cwd=seed)
        run("git", "push", "-u", "origin", BRANCH, cwd=seed)
        self.left = self.clone("left")
        self.right = self.clone("right")
        self.now = datetime.now(timezone.utc).replace(minute=30, second=0, microsecond=0)
        self.target = self.now.strftime("%Y-%m-%dT%H-00Z")

    def clone(self, name, branch=True):
        folder = self.base / name
        run("git", "clone", str(self.origin), str(folder))
        if branch:
            run("git", "checkout", BRANCH, cwd=folder)
        return folder

    def prepare(self, repo, asset, *, timestamp="2026-11-18T13:20:00Z", price=100):
        conf = CONFIG[asset]
        hour = self.now.strftime("%Y-%m-%dT%H:00:00Z")
        obj = {
            "mode": conf["mode"],
            "targetClosed1HUTC": hour,
            "capturedAtUTC": timestamp,
            conf["parity"]: True,
            "sourceVerifiedSameHour": True,
            "noPastHourBackfill": True,
            "ethPatternObservationsOnly": True,
            "ethV92RetestVetoEnabled": False,
            "noRetroactiveBackfill": True,
            "noBrokerOrders": True,
            "noUserNotifications": True,
            "assets": {"BTCUSDT": {"close": price}},
        }
        snap = f"{conf['dir']}/{self.target}.json"
        write(repo, snap, json.dumps(obj, sort_keys=True))
        for f in conf["files"]:
            write(repo, f, "{}\n" if f.endswith(".json") else "Paper only\n")
        combined = {
            "mode": "V92_BTC_ETH_SOL_SINGLE_THIRD_1000USDT_PROSPECTIVE_PAPER_ACCOUNT",
            "assets": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            "virtualInitialUSDT": 1000,
            "sharedSingleVirtualPortfolioNotThreeTimes1000": True,
            "noHistorical836USDBackfilledIntoThisAccount": True,
            "noBrokerOrders": True,
            "noUserNotifications": True,
        }
        write(repo, SHARED[0], json.dumps(combined, sort_keys=True))
        write(repo, SHARED[1], "Shared paper only\n")
        return snap

    def remote_snapshot(self, rel):
        run("git", "fetch", "origin", BRANCH, cwd=self.left)
        return json.loads(run("git", "show", "FETCH_HEAD:" + rel, cwd=self.left))

    def test_first_writer_commits_and_sets_output(self):
        path = self.prepare(self.left, "btc-sol")
        output = self.base / "output.txt"
        self.assertTrue(seal(self.left, "btc-sol", self.target,
                             now=self.now, output=output))
        self.assertEqual(output.read_text(), "committed=true\n")
        self.assertTrue(self.remote_snapshot(path)["noBrokerOrders"])

    def test_identical_race_retry_never_rewrites_or_double_counts(self):
        path = self.prepare(self.left, "btc-sol", timestamp="2026-11-18T13:20:00Z")
        self.prepare(self.right, "btc-sol", timestamp="2026-11-18T13:29:59Z")
        self.assertTrue(seal(self.left, "btc-sol", self.target, now=self.now))
        output = self.base / "second_output.txt"
        self.assertFalse(seal(self.right, "btc-sol", self.target,
                              now=self.now, output=output))
        self.assertEqual(output.read_text(), "committed=false\n")
        self.assertEqual(self.remote_snapshot(path)["capturedAtUTC"],
                         "2026-11-18T13:20:00Z")

    def test_divergent_hour_refuses_to_mutate_immutable_evidence(self):
        path = self.prepare(self.left, "btc-sol", price=100)
        self.prepare(self.right, "btc-sol", price=101)
        self.assertTrue(seal(self.left, "btc-sol", self.target, now=self.now))
        with self.assertRaisesRegex(SealError, "CONTENT_CONFLICT"):
            seal(self.right, "btc-sol", self.target, now=self.now)
        self.assertEqual(self.remote_snapshot(path)["assets"]["BTCUSDT"]["close"], 100)

    def test_other_asset_advance_must_not_overwrite_shared_account(self):
        self.prepare(self.left, "btc-sol")
        self.prepare(self.right, "eth")
        self.assertTrue(seal(self.left, "btc-sol", self.target, now=self.now))
        with self.assertRaisesRegex(SealError, "REMOTE_ADVANCED"):
            seal(self.right, "eth", self.target, now=self.now)
        # A fresh next attempt on same UTC hour can recompute from latest Git.
        fresh = self.clone("fresh")
        eth_path = self.prepare(fresh, "eth")
        self.assertTrue(seal(fresh, "eth", self.target, now=self.now))
        self.assertTrue(self.remote_snapshot(eth_path)["noUserNotifications"])


    def test_push_time_duplicate_race_is_safe_noop(self):
        path = self.prepare(self.left, "btc-sol", timestamp="2026-11-18T13:20:00Z")
        self.prepare(self.right, "btc-sol", timestamp="2026-11-18T13:20:01Z")
        original_git = seal_module.git
        collided = [False]

        def intercept(repo, *args, **kw):
            if Path(repo).resolve() == self.left.resolve() and args[0] == "push" and not collided[0]:
                collided[0] = True
                self.assertTrue(seal(self.right, "btc-sol", self.target, now=self.now))
            return original_git(repo, *args, **kw)

        output = self.base / "post_push_duplicate.txt"
        with patch.object(seal_module, "git", side_effect=intercept):
            self.assertFalse(seal(self.left, "btc-sol", self.target,
                                  now=self.now, output=output))
        self.assertTrue(collided[0])
        self.assertEqual(output.read_text(), "committed=false\n")
        self.assertEqual(self.remote_snapshot(path)["capturedAtUTC"],
                         "2026-11-18T13:20:01Z")

    def test_push_time_conflicting_payload_fails_closed(self):
        path = self.prepare(self.left, "btc-sol", price=100)
        self.prepare(self.right, "btc-sol", price=999)
        original_git = seal_module.git
        collided = [False]

        def intercept(repo, *args, **kw):
            if Path(repo).resolve() == self.left.resolve() and args[0] == "push" and not collided[0]:
                collided[0] = True
                self.assertTrue(seal(self.right, "btc-sol", self.target, now=self.now))
            return original_git(repo, *args, **kw)

        with patch.object(seal_module, "git", side_effect=intercept):
            with self.assertRaisesRegex(SealError, "CONTENT_CONFLICT"):
                seal(self.left, "btc-sol", self.target, now=self.now)
        self.assertTrue(collided[0])
        self.assertEqual(self.remote_snapshot(path)["assets"]["BTCUSDT"]["close"], 999)

    def test_expired_hour_cannot_be_backfilled(self):
        self.prepare(self.left, "btc-sol")
        next_hour = self.now.replace(hour=(self.now.hour + 1) % 24)
        with self.assertRaisesRegex(SealError, "OLD_OR_PREMATURE"):
            seal(self.left, "btc-sol", self.target, now=next_hour)

    def test_missing_parity_fails_before_git_commit(self):
        path = self.prepare(self.left, "btc-sol")
        bad = json.loads((self.left / path).read_text())
        bad["sourceV7AndV91RecomputedExactMatch"] = False
        write(self.left, path, json.dumps(bad))
        with self.assertRaisesRegex(SealError, "PARITY_UNVERIFIED"):
            seal(self.left, "btc-sol", self.target, now=self.now)

    def test_eth_requires_unchanged_observational_source(self):
        path = self.prepare(self.left, "eth")
        self.assertTrue(seal(self.left, "eth", self.target, now=self.now))
        self.assertEqual(self.remote_snapshot(path)["mode"],
                         "V92_ETH_VERIFIED_HOURLY_CANDLES_OBSERVATIONAL_PAPER")


if __name__ == "__main__":
    unittest.main()
