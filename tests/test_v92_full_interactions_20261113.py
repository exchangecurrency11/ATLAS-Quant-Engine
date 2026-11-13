"""Unit tests for isolated full-factorial V9.2 research only."""
import unittest
import v92_full_interactions_20261113 as v
import v92_filter_ablation_20261113 as old

class TestFullResearch(unittest.TestCase):
    def test_full_pair_count_and_safety_classification(self):
        self.assertEqual(len(v.SINGLE_GATES),14)
        self.assertEqual(len(v.SIGNAL_GATES),12)
        self.assertEqual(len(v.PAIRS),91)
        self.assertEqual(len(v.MULTI),6)
        self.assertEqual(len(v.VARIANTS),112)
        self.assertEqual(sum(not v.RISK_GATES.intersection(v.VARIANTS[x])
                             for x in v.PAIRS),66)
        self.assertEqual(sum(bool(v.RISK_GATES.intersection(v.VARIANTS[x]))
                             for x in v.PAIRS),25)
        self.assertEqual(sum(v.applicable("BTCUSDT",x) for x in v.PAIRS),78)
        self.assertEqual(sum(v.applicable("SOLUSDT",x) for x in v.PAIRS),91)
    def test_old_variant_names_and_required_backbone(self):
        self.assertEqual(v.VARIANTS["BASELINE"],())
        self.assertEqual(len(old.CONTROL_REQUIREMENTS),8)
        for key,val in old.ABLATIONS.items():
            self.assertEqual(set(v.VARIANTS[key]),set(val))
        for name in v.MULTI:
            self.assertNotIn("trend1d",v.VARIANTS[name])
            self.assertFalse(v.RISK_GATES.intersection(v.VARIANTS[name]))
    def test_9_and_25bps_risk_normalization(self):
        trades=[{"netRIllustrative":r,"entry":100.,"risk":2.,
                 "entryOpenUTC":(i+1)*3600,"side":"bullish"}
                for i,r in enumerate((1.,-1.,2.))]
        x=v.compact_metrics(trades,9)
        y=v.compact_metrics(trades,25)
        self.assertAlmostEqual(x["netR"],2.)
        self.assertAlmostEqual(y["netR"],1.52)
        self.assertEqual(x["trades"],3)
        self.assertAlmostEqual(x["maxDrawdownR"],1.)
        self.assertGreater(y["maxDrawdownR"],x["maxDrawdownR"])
    def test_no_future_daily_leak(self):
        daily=[{"t":i*86400,"c":100.+i} for i in range(70)]
        cache={"indicators":{(0,86400,55):{
            "EMA20":100.,"EMA50":100.,"RSI14":60.,"hist":2.}}}
        trade={"entryOpenUTC":55*86400+3600,"side":"bullish"}
        closes=[b["t"]+86400 for b in daily]
        trend,vol=v.trade_regime(trade,daily,cache,closes)
        self.assertEqual(trend,"bull")
        self.assertIn(vol,("high","low"))
        self.assertEqual(v.trade_regime({**trade,"entryOpenUTC":53*86400},
                                        daily,cache,closes)[0],"insufficient")
    def test_3_month_bootstrap_is_deterministic(self):
        delta={"2022-10":1.,"2023-04":-2.}
        x=v.bootstrap_delta_25(delta,"2022-10-01T00:00:00Z",11)
        self.assertEqual(x,v.bootstrap_delta_25(delta,"2022-10-01T00:00:00Z",11))
        self.assertLessEqual(x[0],x[1])
    def test_original_replay_source_not_overwritten(self):
        self.assertIn("_momentum_possible",old.fork_source())
        self.assertEqual(v.VARIANTS["BASELINE"],())
        self.assertNotIn("_momentum_possible",old.original.replay_pair.__code__.co_names)

if __name__=="__main__":
    unittest.main()
