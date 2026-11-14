"""Prospective BTC/SOL shadow: future-only, pinned source hashes, no order book."""
import unittest
from unittest.mock import patch
from datetime import datetime,timezone
import btc_sol_v93_prospective_20261114 as f
import btc_sol_v93_causal_regime_20261114 as e

class NewData(unittest.TestCase):
    def trade(self,watch):
        w=e.old.epoch(watch)
        return {"watchKnownUTC":w,"retestKnownUTC":w+3600,
                "entryOpenUTC":w+7200,"exitKnownUTC":w+10800,
                "side":"bullish"}
    def test_frozen_date_future_not_earlier(self):
        self.assertEqual(e.FREEZE,"2026-11-15T00:00:00Z")
        self.assertTrue(f.frozen_spec()["freezeIsAfterHistoricalResearch"])
        self.assertFalse(f.frozen_spec()["noBrokerOrders"]==False)
    def test_pre_freeze_and_boundary_setups_excluded(self):
        pre=self.trade("2026-11-14T23:00:00Z")
        valid=self.trade("2026-11-15T00:00:00Z")
        out=f.after_freeze([pre,valid],e.old.epoch("2026-12-01T00:00:00Z"))
        self.assertEqual(len(out),1)
        self.assertIs(out[0],valid)
    def test_unclosed_trade_does_not_claim_profit(self):
        t=self.trade("2026-11-30T22:00:00Z")
        out=f.after_freeze([t],e.old.epoch("2026-12-01T00:00:00Z"))
        self.assertEqual(out,[])
    def test_timeline_guard(self):
        t=self.trade("2026-11-15T00:00:00Z")
        t["exitKnownUTC"]=t["entryOpenUTC"]
        with self.assertRaisesRegex(ValueError,"LOOKAHEAD"):
            f.after_freeze([t],e.old.epoch("2026-12-01T00:00:00Z"))
    def test_frozen_reference_v93_entry_parity(self):
        t=self.trade("2026-11-15T00:00:00Z")
        t.update(netRIllustrative=1.,entry=100.,risk=1.)
        frame={"BTC_V92_REFERENCE":{"closedProspectiveTrades":[{
          "watchKnownUTC":e.old.stamp(t["watchKnownUTC"]),
          "retestKnownUTC":e.old.stamp(t["retestKnownUTC"]),
          "entryOpenUTC":e.old.stamp(t["entryOpenUTC"]),
          "exitKnownUTC":e.old.stamp(t["exitKnownUTC"]),
          "side":"bullish",
          "netR25Bps":round(f.full.returns_for([t],25)[0],7)}]}}
        self.assertTrue(f.baseline_matches_existing_frozen_v93([t],frame,"BTCUSDT"))
        frame["BTC_V92_REFERENCE"]["closedProspectiveTrades"][0]["netR25Bps"]+=.05
        with self.assertRaisesRegex(ValueError,"ORIGINAL_SIX_STREAM_PARITY"):
            f.baseline_matches_existing_frozen_v93([t],frame,"BTCUSDT")
    def test_competitor_not_original_six_streams(self):
        a=f.frozen_spec()
        self.assertEqual(set(a["candidateNames"]),{"BTCUSDT","SOLUSDT"})
        self.assertEqual(a["perSideStressBps"],[9,25,50])
        self.assertTrue(a["noProductionOrV7V92AccountEdits"])
        self.assertTrue(a["notAutomaticallyPromoted"])

if __name__=="__main__":
    unittest.main()
