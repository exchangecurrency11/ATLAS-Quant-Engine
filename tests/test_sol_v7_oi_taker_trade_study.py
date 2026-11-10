"""Point-in-time SOL V7 OI/taker study safeguards and feature matching."""
import unittest
from sol_v7_oi_taker_trade_study import feature_at_known_close,source_paths,summarize,matched_rows

T=1794085200  # 2026-11-07T21:00:00Z
H=3600
M=300

class SolV7FeatureTests(unittest.TestCase):
    def fixture(self):
        oi={
            T-M:{"oi":1100,"oiUSDT":100000,"availableAfterUTC":"2026-11-07T21:00:00Z"},
            T-H-M:{"oi":1000,"oiUSDT":90000,"availableAfterUTC":"2026-11-07T20:00:00Z"},
            T-4*H-M:{"oi":800,"oiUSDT":75000,"availableAfterUTC":"2026-11-07T17:00:00Z"},
            T:{"oi":999999,"oiUSDT":9999999,"availableAfterUTC":"2026-11-07T21:05:00Z"}, # future!
        }
        h={T-H:{"v":100,"takerBuyBase":35,"takerSellBase":65}}
        return oi,h

    def test_oi_not_allowed_to_look_ahead(self):
        oi,h=self.fixture()
        f=feature_at_known_close(T,"bearish",oi,h,{})
        self.assertEqual(f["oi1hPct"],10.0)
        self.assertEqual(f["oi4hPct"],37.5)
        self.assertEqual(f["takerSignedPressure1h"],0.3)
        self.assertEqual(f["takerBuyShare1h"],0.35)
        self.assertIsNone(f["lastKnownFundingRate"])
        self.assertEqual(f["OI5mAvailableAfterUTC"],"2026-11-07T21:00:00Z")

    def test_taker_direction_reverses_for_long(self):
        oi,h=self.fixture()
        f=feature_at_known_close(T,"bullish",oi,h,{})
        self.assertEqual(f["takerSignedPressure1h"],-0.3)

    def test_missing_oi_stays_missing_not_flat(self):
        oi,h=self.fixture()
        oi.pop(T-H-M)
        f=feature_at_known_close(T,"bearish",oi,h,{})
        self.assertIsNone(f["oi1hPct"])
        self.assertEqual(f["oiCoverageLast4h"],2)

    def test_future_funding_is_excluded(self):
        oi,h=self.fixture()
        # Settlement stamped at the exact signal time is not guaranteed
        # available; +60s delay must prevent hindsight.
        ff={"2026-11":[
            {"t":T-8*H,"intervalHours":8,"rate":0.0001,
             "closeUTC":"2026-11-07T13:00:00Z"},
            {"t":T,"intervalHours":8,"rate":0.8,
             "closeUTC":"2026-11-07T21:00:00Z"}]}
        f=feature_at_known_close(T,"bearish",oi,h,ff)
        self.assertEqual(f["lastKnownFundingRate"],0.0001)

    def test_source_paths_include_forward_events(self):
        p=source_paths({"V7_signal_gate":[]},extra_times=[T])
        names=[x[2] for x in p]
        self.assertTrue(any("SOLUSDT-metrics-2026-11-07.zip" in s for s in names))
        self.assertTrue(any("SOLUSDT-1h-2026-11-06.zip" in s for s in names))

    def test_original_paper_outcome_is_not_affected_by_features(self):
        oi,h=self.fixture()
        fake={"V7_signal_gate":[{
            "watchKnownUTC":T,"entryOpenUTC":T+H,"exitKnownUTC":T+2*H,
            "side":"bearish","netRIllustrative":-1.2482,
        }]}
        r=matched_rows(fake,oi,h,{})
        self.assertEqual(r["V7_signal_gate"]["all"]["trades"],1)
        self.assertEqual(r["V7_signal_gate"]["negativeOrFlat"]["trades"],1)
        self.assertEqual(r["V7_signal_gate"]["positive"]["trades"],0)


if __name__=="__main__":
    unittest.main()
