"""V9.1 closed-hour retest-quality and historical-paper safety tests."""
import unittest
from v91_retest_full_replay import strong_retest, metrics, STRONG_RETEST, VARIANTS

HOUR=3600
START=1760000400  # aligned 1h? calculate via floor in fixture below


def candle_history(n=40, bearish=False):
    first=1735689600
    bars=[{"t":first+i*HOUR,"o":100.,"h":101.,"l":99.,"c":100.,"v":100.}
          for i in range(n)]
    if bearish:
        bars[-1].update(o=100.,h=100.2,l=98.5,c=98.8,v=130.)
        a={"side":"bearish","level":99.7,"knownUTC":bars[-1]["t"]}
    else:
        bars[-1].update(o=100.,h=101.5,l=99.8,c=101.2,v=130.)
        a={"side":"bullish","level":100.3,"knownUTC":bars[-1]["t"]}
    return bars,a


class TestV91Retest(unittest.TestCase):
    def test_strong_long_and_short_only_closed_retest(self):
        for side in [False,True]:
            rows,active=candle_history(bearish=side)
            decision=strong_retest(rows,active,rows[-1])
            self.assertTrue(decision["passed"], decision)
            self.assertTrue(decision["features"]["noFutureEntryCandleUsed"])

    def test_weak_body_and_low_volume_are_rejected(self):
        bars,active=candle_history()
        bars[-1]["c"]=100.45
        d=strong_retest(bars,active,bars[-1])
        self.assertFalse(d["passed"])
        self.assertIn("V91_DIRECTIONAL_BODY_WEAK",d["reasons"])
        bars,active=candle_history()
        bars[-1]["v"]=20.
        d=strong_retest(bars,active,bars[-1])
        self.assertIn("V91_RETEST_VOLUME_BELOW_PRIOR20",d["reasons"])

    def test_future_bar_cannot_influence_score(self):
        bars,active=candle_history()
        first=strong_retest(bars,active,bars[-1])
        future=dict(bars[-1],t=bars[-1]["t"]+HOUR,c=100.,o=100.)
        self.assertTrue(first["passed"])
        self.assertFalse(strong_retest(bars+[future],active,bars[-1])["passed"])
        modified=dict(bars[-1],t=bars[-1]["t"]+HOUR)
        self.assertFalse(strong_retest(bars,active,modified)["passed"])

    def test_gap_and_same_hour_are_invalid(self):
        bars,active=candle_history()
        bars[-2]["t"]-=HOUR
        self.assertFalse(strong_retest(bars,active,bars[-1])["passed"])
        bars,active=candle_history()
        active["knownUTC"]=bars[-1]["t"]+HOUR
        self.assertFalse(strong_retest(bars,active,bars[-1])["passed"])

    def test_registered_nonoptimized_four_fixed_variants(self):
        self.assertEqual(VARIANTS["V7_ORIGINAL"],(6,False))
        self.assertEqual(VARIANTS["V91_RETEST_MAX4H"],(4,False))
        self.assertEqual(VARIANTS["V91_STRONG_RETEST"],(6,True))
        self.assertEqual(VARIANTS["V91_MAX4H_AND_STRONG"],(4,True))
        self.assertEqual(STRONG_RETEST["minDirectionalCloseLocation"],.60)

    def test_cost_stress_and_win_metrics(self):
        from v91_retest_full_replay import START
        report={"status":"PAPER_BACKTEST_NOT_LIVE",
          "trades":[{"entryOpenUTC":START+3600,"exitKnownUTC":START+7200,
                     "entry":100.,"risk":1.,"netRIllustrative":0.82}],
          "alertsCount":1,"qualityGateRejectedBOS":0,
          "qualityGateRejectedRetest":0,"retestExpiredCount":0,
          "riskRuleRejected":0,"unresolvedPositionExcluded":False}
        m,_=metrics(report)
        self.assertEqual(m["trades"],1)
        self.assertEqual(m["totalNetR9bpsSide"],.82)
        self.assertEqual(m["totalNetR25bpsSide"],.50)


if __name__=="__main__":
    unittest.main()
