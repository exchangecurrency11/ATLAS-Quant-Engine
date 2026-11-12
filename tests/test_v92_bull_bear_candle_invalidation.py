"""V9.2 dual-direction star/false-breakout detection regression safety."""
import copy
import unittest

from v92_bull_bear_candle_invalidation import (
    HOUR,FOUR,candle_star,opposite_warning,gated_retest_factory,metrics
)
from collections import Counter

BASE=1794009600  # aligned UTC candle boundary

def history(interval, side, *, fake_sweep=True):
    # Twenty-seven prior 24/7 perpetual candles, then a three-bar star.
    history=[{"t":BASE+i*interval,"o":100.,"h":102.,"l":98.,
              "c":100.,"v":1000.} for i in range(27)]
    if side=="bearish":
        history[-5]["c"]=100.
        a={"o":101.,"h":106.,"l":100.,"c":105.}
        b={"o":105.,"h":(112. if fake_sweep else 107.),
           "l":104.,"c":105.2}
        c={"o":105.,"h":106.,"l":98.,"c":99.}
    else:
        a={"o":99.,"h":100.,"l":94.,"c":95.}
        b={"o":95.,"h":96.,"l":(88. if fake_sweep else 94.),
           "c":94.8}
        c={"o":95.,"h":102.,"l":94.,"c":101.}
    for i,source in enumerate((a,b,c)):
        history.append({**source,"t":BASE+(27+i)*interval,"v":1000.})
    return history

class V92ReversalTests(unittest.TestCase):
    def test_evening_star_bearish_and_false_breakout_confirmed(self):
        candles=history(HOUR,"bearish")
        result=candle_star(candles,len(candles)-1,HOUR)
        self.assertEqual(result["name"],"EVENING_STAR")
        self.assertEqual(result["direction"],"bearish")
        self.assertTrue(result["fakeBreakoutPrior20SweepAndReentry"])
        self.assertTrue(result["cryptoNoGapRequired"])
        self.assertTrue(result["notAnEntrySignal"])

    def test_morning_star_bullish_mirrored_and_false_breakout(self):
        candles=history(HOUR,"bullish")
        result=candle_star(candles,len(candles)-1,HOUR)
        self.assertEqual(result["name"],"MORNING_STAR")
        self.assertEqual(result["direction"],"bullish")
        self.assertTrue(result["fakeBreakoutPrior20SweepAndReentry"])

    def test_non_sweep_star_warning_exists_but_strict_gate_ignores(self):
        c=history(HOUR,"bearish",fake_sweep=False)
        p=candle_star(c,len(c)-1,HOUR)
        self.assertIsNotNone(p)
        self.assertFalse(p["fakeBreakoutPrior20SweepAndReentry"])
        at=c[-1]["t"]+HOUR
        early=opposite_warning(c,[],at,"bullish",require_fake_break=False)
        strict=opposite_warning(c,[],at,"bullish",require_fake_break=True)
        self.assertEqual(len(early),1)
        self.assertEqual(strict,[])

    def test_bearish_pattern_only_invalidates_existing_bullish_setup(self):
        c=history(HOUR,"bearish")
        at=c[-1]["t"]+HOUR
        self.assertEqual(len(opposite_warning(c,[],at,"bullish")),1)
        self.assertEqual(opposite_warning(c,[],at,"bearish"),[])

    def test_bullish_pattern_only_invalidates_existing_bearish_setup(self):
        c=history(HOUR,"bullish")
        at=c[-1]["t"]+HOUR
        self.assertEqual(len(opposite_warning(c,[],at,"bearish")),1)
        self.assertEqual(opposite_warning(c,[],at,"bullish"),[])

    def test_strict_retest_veto_at_current_closed_1h_is_causal(self):
        c=history(HOUR,"bearish")
        ev=Counter();ev["examples"]=[]
        gate=gated_retest_factory([],True,ev)
        ans=gate(c,{"side":"bullish"},c[-1])
        self.assertFalse(ans["passed"])
        self.assertIn("V92_OPPOSITE_CLOSED_EVENING_STAR",ans["reasons"][0])
        self.assertEqual(ev["oppositePatternVetoCount"],1)
        self.assertEqual(ev["EVENING_STAR_1H"],1)

    def test_future_4h_pattern_must_not_be_used(self):
        h1=history(HOUR,"bullish")
        h4=history(FOUR,"bearish")
        at=h1[-1]["t"]+HOUR
        # None of the recent 4H end stamps should have closed at current 1H time.
        results=opposite_warning(h1,h4,at,"bullish",require_fake_break=True)
        self.assertEqual(results,[])

    def test_asof_not_matching_hour_rejected(self):
        c=history(HOUR,"bearish")
        with self.assertRaisesRegex(ValueError,"NOT_CLOSED"):
            opposite_warning(c,[],c[-1]["t"],"bullish")
        with self.assertRaisesRegex(ValueError,"INVALID_ACTIVE_SIDE"):
            opposite_warning(c,[],c[-1]["t"]+HOUR,"unknown")

    def test_gapped_or_malformed_1h_rejected(self):
        c=history(HOUR,"bearish")
        c[-3]["t"]+=30
        with self.assertRaisesRegex(ValueError,"GAPPED"):
            candle_star(c,len(c)-1,HOUR)
        c=history(HOUR,"bearish")
        c[-1]["h"]=80
        with self.assertRaisesRegex(ValueError,"INVALID_OHLCV"):
            candle_star(c,len(c)-1,HOUR)

    def test_malformed_star_rejected_not_fabricated(self):
        c=history(HOUR,"bearish")
        c[-2]["c"]=110
        c[-2]["h"]=112
        self.assertIsNone(candle_star(c,len(c)-1,HOUR))
        self.assertIsNone(candle_star(c,10,HOUR))

    def test_paper_trade_outcome_metrics_not_treated_as_live(self):
        state={"status":"PAPER_BACKTEST_NOT_LIVE","trades":[],
               "alertsCount":0,"qualityGateRejectedRetest":0,
               "retestExpiredCount":0,"unresolvedPositionExcluded":False}
        result=metrics(state,0,100000)
        self.assertEqual(result["trades"],0)
        self.assertIsNone(result["winRatePct"])
        self.assertEqual(result["totalNetR9BpsPerSide"],0)
        state["status"]="REAL_ORDER_EXECUTED"
        with self.assertRaisesRegex(ValueError,"INVALID_SEQUENTIAL"):
            metrics(state,0,100000)

if __name__=="__main__": unittest.main()
