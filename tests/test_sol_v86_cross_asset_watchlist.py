"""V8.6 three-asset watchlist data integrity, no invented ETH/TradingView numbers."""
import copy
import unittest
from sol_v86_cross_asset_watchlist import (
    extract_main,extract_eth,validate_timestamp_and_candles,regime,normalized)

UTC="2026-11-10T20:00:00Z"
DAY="2026-11-10T00:00:00Z"

def candle(price):
    return {"open":price,"high":price+4,
            "low":price-4,"close":price,"volume":100}

def tf(price,rsi4=35,rsi_daily=35):
    return {
      "1hour":{"closeUTC":UTC,"candle":candle(price),
               "indicators":{"RSI14":39,"EMA20":price+2,"EMA50":price+4}},
      "4hour":{"closeUTC":UTC,"candle":candle(price),
               "indicators":{"RSI14":rsi4,"EMA20":price+2,"EMA50":price+4}},
      "daily":{"closeUTC":DAY,"candle":candle(price+8),
               "indicators":{"RSI14":rsi_daily,"EMA20":price+20,"EMA50":price+30}}}


class ThreeAssetAuditTests(unittest.TestCase):
    def test_cross_asset_same_4h_close_strict(self):
        records={"BTCUSDT_PERP.A":tf(73000),
                 "ETHUSDT_PERP.A":tf(2050),
                 "SOLUSDT_PERP.A":tf(83)}
        self.assertEqual(validate_timestamp_and_candles(records),UTC)
        bad=copy.deepcopy(records)
        bad["ETHUSDT_PERP.A"]["4hour"]["closeUTC"]="2026-11-10T16:00:00Z"
        with self.assertRaisesRegex(ValueError,"DIFFERENT_TIMES"):
            validate_timestamp_and_candles(bad)

    def test_1h_4h_close_match_required(self):
        r={"BTCUSDT_PERP.A":tf(73000),
           "ETHUSDT_PERP.A":tf(2050),
           "SOLUSDT_PERP.A":tf(83)}
        r["ETHUSDT_PERP.A"]["1hour"]["candle"]["close"]=1900
        with self.assertRaisesRegex(ValueError,"PRICE_MISMATCH"):
            validate_timestamp_and_candles(r)

    def test_eth_verified_snapshot_cannot_fake_realtime(self):
        source={"status":"VERIFIED_PAPER_OBSERVATION",
                "symbol":"ETHUSDT_PERP.A",
                "paperForwardObservation":True,"brokerOrders":False,
                "crossTimeframeOHLCVVerifiedLast5":{"1H_matches_4H":5,"1H_matches_daily":5},
                "dataSource":"Coinalyze ETHUSDT_PERP.A / Binance perpetual",
                "marketContext":{"ETHUSDT_PERP.A":{"timeframes":{
                    key:{"closeTimeUTC":item["closeUTC"],"candle":item["candle"],
                         "indicators":item["indicators"]}
                    for key,item in tf(2050).items()}}}}
        data=extract_eth(source)
        self.assertEqual(set(data),{"1hour","4hour","daily"})
        source["crossTimeframeOHLCVVerifiedLast5"]["1H_matches_4H"]=0
        with self.assertRaisesRegex(ValueError,"NOT_CONFIRMED"):
            extract_eth(source)

    def test_oversold_ETH_and_SOL_no_chase_short(self):
        ctx=regime("ETH",tf(2050,28.9,34))
        self.assertEqual(ctx["state"],"FALLING_TREND_WITH_BOUNCE_RISK")
        self.assertEqual(ctx["decision"],"WAIT_NO_CHASE_SHORT")
        self.assertFalse(ctx["independentClosed1HEntrySignalVerified"])

    def test_bitcoin_bear_trend_only_a_watch(self):
        ctx=regime("BTC",tf(73000,35.3,37.2))
        self.assertEqual(ctx["state"],"FALLING_TREND_CONTINUATION_WATCH")
        self.assertEqual(ctx["decision"],"WAIT_FOR_SEPARATE_1H_BOS_RETEST")

    def test_SOL_SMA_cannot_mismatch_4H_perpetual_price(self):
        shadow={"status":"RESEARCH_SNAPSHOT_NO_ORDERS",
                "symbol":"SOLUSDT_PERP.A",
                "readOnlyMarketContext":{"4HCloseUTC":UTC,
                    "4HClose":85,
                    "4HSMA100":94,"4HSMA200":100,
                    "dailySMA100":99,"dailySMA200":89,
                    "4HSMA100AboveSMA200":False,"dailySMA100AboveSMA200":True}}
        with self.assertRaisesRegex(ValueError,"MISALIGNED"):
            regime("SOL",tf(82.9,30.5,27.2),shadow)


if __name__=="__main__":
    unittest.main()
