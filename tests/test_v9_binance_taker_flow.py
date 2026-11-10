"""V9: binance taker flow is point-in-time, no zero-fills, no fake tick-CVD."""
import copy
import unittest
from v9_binance_taker_flow import closed_taker_features, HOUR


def candle(i,buy_share=.6,vol=100):
    return {"t":i*HOUR,"o":100.,"h":101.,"l":99.,"c":100.,
            "v":vol,"qv":100.*vol,"trades":10,
            "tbv":vol*buy_share,"tbq":100.*vol*buy_share}


class V9FlowTests(unittest.TestCase):
    def test_buys_and_sells_cvd_from_closed_hours(self):
        rows=[candle(i,.5) for i in range(24)]+[candle(i,.6) for i in range(24,48)]
        p=closed_taker_features(rows,48*HOUR,hours=24,baseline_hours=24)
        self.assertAlmostEqual(p["takerBuyBase"],1440)
        self.assertAlmostEqual(p["takerSellBaseDerived"],960)
        self.assertAlmostEqual(p["rollingCVDBaseApprox"],480)
        self.assertAlmostEqual(p["buyShare"],.6)
        self.assertAlmostEqual(p["rollingCVDPctOfVolume"],20)
        self.assertAlmostEqual(p["averageHourlyVolumeRelativeToPreviousWindow"],1)
        self.assertEqual(p["completedTrades"],240)
        self.assertTrue(p["paperOnly"])

    def test_future_candles_do_not_change_as_of(self):
        rows=[candle(i) for i in range(60)]
        a=closed_taker_features(rows,48*HOUR)
        altered=copy.deepcopy(rows)
        for r in altered[48:]:
            r["tbv"]=0
            r["tbq"]=0
            r["v"]=100000
            r["qv"]=10000000
            r["trades"]=999999
        self.assertEqual(a,closed_taker_features(altered,48*HOUR))

    def test_reject_missing_taker_fields_not_assumed_zero(self):
        rows=[candle(i) for i in range(48)]
        del rows[33]["tbv"]
        with self.assertRaisesRegex(ValueError,"FLOW_REQUIRED_FIELD_MISSING"):
            closed_taker_features(rows,48*HOUR)

    def test_reject_single_missing_1h_candle(self):
        rows=[candle(i) for i in range(49) if i!=25]
        with self.assertRaisesRegex(ValueError,"FLOW_HOURLY_HISTORY_HAS_GAP"):
            closed_taker_features(rows,49*HOUR)

    def test_reject_stale_latest(self):
        rows=[candle(i) for i in range(48)]
        with self.assertRaisesRegex(ValueError,"STALE"):
            closed_taker_features(rows,49*HOUR)

    def test_reject_duplicate_and_unsorted(self):
        rows=[candle(i) for i in range(48)]
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            closed_taker_features(rows+[candle(10)],48*HOUR)

    def test_reject_units_and_volume(self):
        rows=[candle(i) for i in range(48)]
        rows[-1]["tbv"]=101
        with self.assertRaisesRegex(ValueError,"OUTSIDE_TOTAL"):
            closed_taker_features(rows,48*HOUR)
        rows[-1]["tbv"]=60
        rows[-1]["qv"]=2
        with self.assertRaisesRegex(ValueError,"OUTSIDE_TOTAL"):
            closed_taker_features(rows,48*HOUR)

    def test_no_inference_if_non_hourly_cutoff(self):
        rows=[candle(i) for i in range(48)]
        with self.assertRaisesRegex(ValueError,"EXACT_HOURLY"):
            closed_taker_features(rows,48*HOUR+30)

    def test_accurate_downward_taker_pressure_not_predictive_approval(self):
        rows=[candle(i,.5) for i in range(24)]+[candle(i,.2) for i in range(24,48)]
        p=closed_taker_features(rows,48*HOUR)
        self.assertAlmostEqual(p["buyShare"],.2)
        self.assertAlmostEqual(p["rollingCVDPctOfVolume"],-60)
        self.assertFalse(p["marketOrderBookKnown"])
        self.assertFalse(p["realOrderIntentProven"])


if __name__=="__main__":
    unittest.main()
