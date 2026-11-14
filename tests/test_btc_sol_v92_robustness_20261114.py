"""BTC SOL historical robustness proof tests; do not call external exchange."""
import unittest
from datetime import datetime,timezone
import btc_sol_v92_robustness_20261114 as m

class V92Robustness(unittest.TestCase):
    def trade(self,entry="2025-05-02T10:00:00Z",exit="2025-05-02T15:00:00Z",
              side="bullish",R=1.,risk=.8):
        return {"entryUTC":entry,"retestUTC":"2025-05-02T09:00:00Z",
                "exitUTC":exit,"side":side,"exitReason":"TP3_COMPLETE",
                "riskPct":risk,"netR9Bps":R}
    def test_costs_9_25_50_per_side(self):
        t=self.trade()
        self.assertAlmostEqual(m.ret(t,9),1.)
        self.assertAlmostEqual(m.ret(t,25),.6)
        self.assertAlmostEqual(m.ret(t,50),-.025)
    def test_small_risk_stress_is_larger(self):
        narrow=self.trade(risk=.2)
        wide=self.trade(risk=1.2)
        self.assertLess(m.ret(narrow,25),m.ret(wide,25))
        self.assertLess(m.ret(narrow,50),m.ret(narrow,25))
    def test_dd_realizes_equity_peak(self):
        tr=[self.trade(R=2.),self.trade(R=-2.),self.trade(R=1.)]
        s=m.metrics(tr,9)
        self.assertEqual(s["trades"],3)
        self.assertEqual(s["wins"],2)
        self.assertAlmostEqual(s["maxDrawdownR"],2.)
    def test_wilson_tiny_n_has_wide_range(self):
        self.assertIsNone(m.wilson(0,0))
        a,b=m.wilson(11,20)
        self.assertLess(a,35.)
        self.assertGreater(b,70.)
    def test_q4_rolls_to_next_year_without_lookahead(self):
        out=m.bootstrap([],20261114)
        self.assertEqual(out["p2_5"],0)
        self.assertTrue(out["notIndependentOrMultipleTestCorrected"])
    def test_regime_must_cover_every_frozen_trade(self):
        source={
            "trades":2,"netR25Bps":.5,"at25bps":{"wins":1},
            "regimeSlices":{
                "direction:bullish":{"at25bps":{"trades":2,"wins":1,"netR":.5}},
                "trend:bull":{"at25bps":{"trades":1,"wins":1,"netR":1.}},
                "trend:range":{"at25bps":{"trades":1,"wins":0,"netR":-.5}},
                "volatility:high":{"at25bps":{"trades":2,"wins":1,"netR":.5}}
            }
        }
        x=m.closed_daily_regimes(source)
        self.assertEqual(x["trend"]["bull"]["wins"],1)
        del source["regimeSlices"]["trend:range"]
        with self.assertRaisesRegex(ValueError,"COVERAGE"):
            m.closed_daily_regimes(source)
    def test_no_shared_overlap_is_not_independence(self):
        a=self.trade()
        b=self.trade(entry="2025-05-03T10:00:00Z",exit="2025-05-03T16:00:00Z")
        x=m.overlaps([a],[b])
        self.assertEqual(x["simultaneousOpenTradePairs"],0)
        self.assertTrue(x["noAssumptionOfIndependentBTCSOLRisks"])
    def test_overlap_is_accurate(self):
        a=self.trade()
        b=self.trade(entry="2025-05-02T14:00:00Z",exit="2025-05-02T16:00:00Z")
        x=m.overlaps([a],[b])
        self.assertEqual(x["simultaneousOpenTradePairs"],1)
        self.assertEqual(x["overlapExamples"][0]["overlapHours"],1)
    def test_quarter_removal_catches_concentrated_profit(self):
        a=self.trade(R=3.)
        b=self.trade(entry="2025-07-02T10:00:00Z",exit="2025-07-02T15:00:00Z",
                     R=-1.)
        f=m.fragility([a,b])
        self.assertLess(f["netR25WithoutBestQuarter"],0)
        self.assertEqual(f["tradedQuarters"],2)
    def test_risk_bound_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"RISK"):
            m.ret(self.trade(risk=.05),25)
    def test_immutable_untested_forward(self):
        self.assertEqual(m.PERIODS,("2022_2024","2024_2026"))
        self.assertEqual(m.COINS,("BTCUSDT","SOLUSDT"))
        self.assertEqual(m.COSTS,(9,25,50))
        self.assertEqual(str(m.INPUT),"forward/v92_full_interactions_20261113/historical.json")

if __name__=="__main__":
    unittest.main()
