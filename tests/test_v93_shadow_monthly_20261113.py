"""No-order V9.3 frozen monthly shadow prospective protection tests."""
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timezone
import v93_shadow_monthly_20261113 as s
import v92_filter_ablation_20261113 as old
import v92_full_interactions_20261113 as full

class TestShadow(unittest.TestCase):
    def test_start_cutoff_and_six_immutable_configurations(self):
        self.assertEqual(s.FREEZE,"2026-11-14T00:00:00Z")
        self.assertEqual(len(s.CANDIDATES),6)
        self.assertEqual(set(s.CANDIDATES),{
            "BTC_V92_REFERENCE","ETH_V92_REFERENCE","SOL_V92_REFERENCE",
            "ETH_BOS_EMA_RELAX","ETH_BOS_RETEST6","SOL_VOLUME_RELAX"})
        self.assertEqual(s.CANDIDATES["ETH_BOS_EMA_RELAX"][2],
                         ("bos_break_atr","bos_ema_extension"))
        self.assertEqual(s.CANDIDATES["ETH_BOS_RETEST6"][2],
                         ("bos_break_atr","retest_window"))
    def test_complete_month_lag_no_future(self):
        self.assertEqual(s.previous_complete_month(
            datetime(2026,11,13,tzinfo=timezone.utc)),"2026-10")
        self.assertEqual(s.previous_complete_month(
            datetime(2027,1,5,tzinfo=timezone.utc)),"2026-12")
        with self.assertRaises(ValueError):
            s.previous_complete_month(datetime(2026,11,13))
    def test_frozen_source_hashes_and_parity(self):
        old.fork_source()
        manifest=s.frozen_spec()
        self.assertEqual(len(manifest["immutableEngineHashes"]),7)
        self.assertEqual(manifest["costPerSideBps"],[9,25])
        self.assertFalse(manifest["realOrders"])
        self.assertFalse(manifest["currentV7V92AccountWrites"])
        for digest in manifest["immutableEngineHashes"].values():
            self.assertEqual(len(digest),64)
    def test_immutable_snapshots_fail_closed_on_revision(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"snap.json"
            s.immutable_check_or_write(p,{"v":1})
            s.immutable_check_or_write(p,{"v":1})
            with self.assertRaisesRegex(ValueError,"IMMUTABLE"):
                s.immutable_check_or_write(p,{"v":2})
    def test_no_prefreeze_or_future_trades_accepted(self):
        t0=s.FREEZE_EPOCH
        def row(a,b,c,d):
            return {"watchKnownUTC":old.stamp(a),"retestKnownUTC":old.stamp(b),
                    "entryOpenUTC":old.stamp(c),"exitKnownUTC":old.stamp(d)}
        base={"metrics9Bps":{"trades":1},"metrics25Bps":{"trades":1}}
        x={"BASE":{**base,"closedProspectiveTrades":[row(t0,t0+3600,
                                                       t0+3600,t0+7200)]}}
        s.validate_candidate_prospective(x)
        x["BASE"]["closedProspectiveTrades"]=[row(t0-3600,t0,t0+3600,t0+7200)]
        with self.assertRaisesRegex(ValueError,"CHRONOLOGY"):
            s.validate_candidate_prospective(x)
        x["BASE"]["closedProspectiveTrades"]=[row(t0,t0+3600,t0+7200,t0+7200)]
        with self.assertRaisesRegex(ValueError,"CHRONOLOGY"):
            s.validate_candidate_prospective(x)
    def test_research_gate_not_placed_on_live_engine(self):
        self.assertNotIn("_momentum_possible",old.original.replay_pair.__code__.co_names)
        self.assertEqual(old.ABLATIONS["BASELINE"],())
        self.assertEqual(full.VARIANTS["PAIR__bos_break_atr__retest_window"],
                         ("bos_break_atr","retest_window"))

if __name__=="__main__":
    unittest.main()
