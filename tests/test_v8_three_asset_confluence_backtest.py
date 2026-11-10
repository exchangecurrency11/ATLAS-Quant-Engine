"""V8 3-asset paper research regression: causal timing and sizing."""
import unittest
from v8_three_asset_confluence_backtest import (
    fib_levels, matches_candle_pattern, metrics, zone_overlap, signal,
    START_EQUITY_USDT, RISK_HARD_CAP_USDT, ISOLATED_LEVERAGE, SPLIT
)
from backtest_retest_long_v4 import reaction_confirmed, assess_candle

class RiskAndCausalTests(unittest.TestCase):
    def test_fib_382_618_levels_and_direction(self):
        candles=[{"o":100,"h":110,"l":90,"c":100} for _ in range(60)]
        self.assertAlmostEqual(fib_levels(candles,"bullish")[0],97.64)
        self.assertAlmostEqual(fib_levels(candles,"bullish")[1],102.36)
        self.assertAlmostEqual(fib_levels(candles,"bearish")[0],97.64)
        self.assertAlmostEqual(fib_levels(candles,"bearish")[1],102.36)
        self.assertTrue(zone_overlap(98,99,97.64,102.36))
        self.assertFalse(zone_overlap(80,85,97.64,102.36))

    def test_candlestick_engulfing_and_pinbar_detection(self):
        prev={"o":101,"c":99,"h":102,"l":98}
        engulf={"o":98.5,"c":101.5,"h":102,"l":98}
        self.assertTrue(matches_candle_pattern(prev,engulf,"bullish",1.0))
        self.assertFalse(matches_candle_pattern(prev,engulf,"bearish",1.0))
        pin={"o":100.1,"c":100.8,"h":100.9,"l":97.0}
        self.assertTrue(matches_candle_pattern(prev,pin,"bullish",2.0))

    def test_retest_is_after_bos_and_next_open_only(self):
        # Base engine: a BOS watch never qualifies as same-bar retest.
        prev={"c":102}
        retest={"o":100,"h":101,"l":98,"c":100.5}
        self.assertFalse(reaction_confirmed("bullish",retest,prev,100))
        confirmed={"o":99,"h":102,"l":98,"c":101.5}
        self.assertTrue(reaction_confirmed("bullish",confirmed,{"c":100.5},100))

    def test_stop_first_worst_case_same_hour(self):
        pos={"side":"bullish","entry":100,"stop":99,"targets":[101,102,103],
             "targetCount":0,"realizedR":0.0}
        closed,why=assess_candle(pos,{"h":104,"l":98,"c":103})
        self.assertTrue(closed)
        self.assertTrue(why.startswith("STOP"))
        self.assertEqual(pos["realizedR"],-1.0)

    def test_isolated_risk_cap_including_assumed_roundtrip_cost(self):
        start=1_000_000
        trade={"entryOpenUTC":start+3600,"exitKnownUTC":start+7200,
               "entry":100,"stop":99,"side":"bullish",
               "netRIllustrative":-1-0.18,"exitReason":"STOP"}
        m=metrics([trade],start,start+10000)
        self.assertEqual(m["trades"],1)
        self.assertLessEqual(-m["netPnLUSDT"],RISK_HARD_CAP_USDT+0.00002)
        self.assertLessEqual(m["tradesDetail"][0]["illustrativeInitialMarginUSDT"],
                             START_EQUITY_USDT)
        self.assertTrue(m["hypotheticalEndUSDT"]<100)

    def test_notional_cap_enforced_when_stop_extremely_tight(self):
        start=1_000_000
        trade={"entryOpenUTC":start+3600,"exitKnownUTC":start+7200,
               "entry":100,"stop":99.999,"side":"bullish",
               "netRIllustrative":-1-180,"exitReason":"STOP"}
        m=metrics([trade],start,start+10000)
        qty=m["tradesDetail"][0]["hypotheticalQty"]
        self.assertLessEqual(qty*100,ISOLATED_LEVERAGE*START_EQUITY_USDT+0.001)

    def test_empty_trades_not_fake_winning_strategy(self):
        m=metrics([],0,1_000_000)
        self.assertEqual(m["trades"],0)
        self.assertIsNone(m["winRatePct"])
        self.assertIsNone(m["profitFactor"])
        self.assertEqual(m["netPnLUSDT"],0)

if __name__=="__main__":
    unittest.main()
