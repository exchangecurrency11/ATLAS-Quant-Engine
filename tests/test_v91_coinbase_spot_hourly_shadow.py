import unittest
from research.v91_coinbase_spot_hourly_shadow import (
    build_snapshot, compare_venue_returns, fetch_closed_spot
)

T=1794416400
O=T+1500

def spot(open_value=100,close_value=101):
    return {"status":"VALID_COINBASE_SPOT_CLOSED_1H","httpCode":200,
     "candle":{"openTimeUTC":"2026-11-11T16:00:00Z","closeTimeUTC":"2026-11-11T17:00:00Z",
               "open":open_value,"high":102,"low":99,"close":close_value,
               "spotBaseVolume":100}}

def reference(close_time="2026-11-11T17:00:00Z"):
    return {"status":"V9_HOURLY_OBSERVATION_VERIFIED_PAPER_CONTEXT_ONLY",
            "closed1HUTC":close_time,"assets":{
                a+"USDT":{"1H":{"closedAtUTC":close_time,"OHLCV":{
                    "open":200,"high":205,"low":195,"close":202,"volume":15000
                }}} for a in ("BTC","ETH","SOL")}}

class Checks(unittest.TestCase):
    def test_same_hour_different_market_returns_only(self):
        r=build_snapshot(T,O,{a:spot() for a in ("BTC","ETH","SOL")},reference())
        self.assertTrue(r["successAllThreeCoinbaseSpotClosed1H"])
        self.assertTrue(r["allThreeSameHourV9Comparisons"])
        for a in ("BTC","ETH","SOL"):
            c=r["assets"][a]["sameHourSpotVsPerpetualContext"]
            self.assertAlmostEqual(c["coinbaseSpot1HReturnBps"],100)
            self.assertAlmostEqual(c["coinalyzePerpetual1HReturnBps"],100)
            self.assertTrue(c["sameHourlyCandleDirection"])
            self.assertTrue(c["notDirectPriceOrVolumeParity"])
            self.assertTrue(c["notAnEntryFilterOrSignal"])
        self.assertTrue(r["noIndependentLiveBinancePerpetualOHLCParity"])
        self.assertTrue(r["noEntrySignalOrVeto"])
        self.assertTrue(r["originalV7Unmodified"])
        self.assertTrue(r["noNotifications"])
    def test_no_reference_never_means_fake_parity(self):
        r=build_snapshot(T,O,{a:spot() for a in ("BTC","ETH","SOL")})
        self.assertTrue(r["successAllThreeCoinbaseSpotClosed1H"])
        self.assertFalse(r["allThreeSameHourV9Comparisons"])
        self.assertEqual(r["coinalyzeComparisonStatus"],"V9_REFERENCE_UNAVAILABLE")
    def test_stale_reference_not_compared(self):
        r=build_snapshot(T,O,{a:spot() for a in ("BTC","ETH","SOL")},
                         reference("2026-11-11T16:00:00Z"))
        self.assertFalse(r["allThreeSameHourV9Comparisons"])
    def test_coinbase_403_not_construed_as_success(self):
        bad={"status":"HTTP_UNAVAILABLE","httpCode":403}
        r=build_snapshot(T,O,{a:bad for a in ("BTC","ETH","SOL")},reference())
        self.assertFalse(r["successAllThreeCoinbaseSpotClosed1H"])
        self.assertFalse(r["allThreeSameHourV9Comparisons"])
    def test_missing_asset_not_fabricated(self):
        r=build_snapshot(T,O,{"BTC":spot(),"ETH":spot()},reference())
        self.assertEqual(r["assets"]["SOL"]["coinbaseSpotClosed1H"]["status"],
                         "MISSING_COINBASE_SPOT")
        self.assertFalse(r["successAllThreeCoinbaseSpotClosed1H"])
    def test_invalid_reference_close_not_counted(self):
        x=reference()
        x["assets"]["SOLUSDT"]["1H"]["closedAtUTC"]="2026-11-11T16:00:00Z"
        r=build_snapshot(T,O,{a:spot() for a in ("BTC","ETH","SOL")},x)
        self.assertFalse(r["allThreeSameHourV9Comparisons"])

if __name__=="__main__":unittest.main()
