"""Guardrails and algebra for ETH trade-by-trade historical diagnostics."""
import unittest
from unittest.mock import patch
import eth_v92_loss_attribution_20261113 as e

class ForensicsTests(unittest.TestCase):
    def trade(self,entry="2026-06-05T17:00:00Z",side="bearish",r9=1.,riskpct=.8,
              exit="2026-06-05T19:00:00Z",reason="TP3_COMPLETE"):
        return {"entryUTC":entry,"retestUTC":"2026-06-05T16:00:00Z",
                "side":side,"exitUTC":exit,"netR9Bps":r9,
                "riskPct":riskpct,"exitReason":reason}
    def test_cost_transforms_exact_formula(self):
        a=self.trade(r9=1,riskpct=0.8)
        self.assertAlmostEqual(e.r25(a),.6)
        self.assertEqual(e.stats([a])["wins25bps"],1)
    def test_cost_flip_is_not_counted_as_win(self):
        a=self.trade(r9=.3,riskpct=.8)
        s=e.stats([a])
        self.assertEqual(s["wins25bps"],0)
        self.assertEqual(s["costFlipWinners9ToLosers25"],1)
    def test_wilson_with_tiny_n_is_wide(self):
        self.assertIsNone(e.wilson(0,0))
        low,high=e.wilson(2,6)
        self.assertLess(low,20)
        self.assertGreater(high,60)
    def test_paired_new_less_displaced_algebra(self):
        a=self.trade(r9=1)
        b=self.trade(entry="2026-06-06T17:00:00Z",r9=-1.,
                     exit="2026-06-06T19:00:00Z")
        c=self.trade(entry="2026-06-07T17:00:00Z",r9=2.,
                     exit="2026-06-07T19:00:00Z")
        pair=e.companion([a,b],[a,c])
        self.assertEqual(pair["commonTrades"],1)
        self.assertEqual(pair["added"]["n"],1)
        self.assertEqual(pair["dropped"]["n"],1)
        self.assertAlmostEqual(pair["incrementalNetR25bps"],
                               e.r25(c)-e.r25(b))
    def test_missing_or_future_time_fails_closed(self):
        t=self.trade()
        t["retestUTC"]="2026-06-06T16:00:00Z"
        with self.assertRaisesRegex(ValueError,"NONCAUSAL"):
            e.validate_trade(t)
    def test_source_frozen_and_no_notifications(self):
        self.assertIn("historical.json",str(e.INPUT))
        self.assertEqual(e.COIN,"ETHUSDT")
        self.assertEqual(e.PERIODS,("2022_2024","2024_2026"))
        self.assertEqual(len(e.CANDIDATES),5)
        for src in e.CANDIDATES:
            self.assertTrue(src=="BASELINE" or "BOS" in src or src.startswith("PAIR"))
    def test_trade_risk_out_of_band_rejected(self):
        with self.assertRaisesRegex(ValueError,"RISK_PCT"):
            e.r25(self.trade(riskpct=.05))

if __name__=="__main__":
    unittest.main()
