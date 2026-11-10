"""Causal Daily+4H broad-zone historical study regression tests."""
import copy
import unittest

from sol_v81_historical_wide_zone_study import (
    select_box_at_cutoff,identify_first_break,examine_after_break,
    independent_events,safe_summary,WIDTH_RATIO,SECS4,DAY,
)


def bar(t,o,h,l,c,v=100):
    return {"t":t,"o":o,"h":h,"l":l,"c":c,"v":v}


def history(days=38):
    four=[]
    daily=[]
    for d in range(days):
        for j in range(6):
            t=d*DAY+j*SECS4
            price=95.0+(0.12 if (d+j)%2 else -0.12)
            four.append(bar(t,price,price+1,price-1,price,100))
        daily.append(bar(d*DAY,95,97,93,95,600))
    return four,daily


class CausalWideZoneTests(unittest.TestCase):
    def test_synthetic_daily_and_4h_cluster_creates_band(self):
        f,d=history()
        t=34*DAY
        z=select_box_at_cutoff(f,d,t)
        self.assertIsNotNone(z)
        self.assertFalse(z["manualZoneAnchorUsed"])
        self.assertEqual(z["dailyCandlesUsed"],28)
        self.assertEqual(z["fourHourCandlesUsed"],168)
        self.assertEqual(z["dataLatest4HCloseAtCreationUTC"],
                         "1970-02-04T00:00:00Z")
        self.assertAlmostEqual(z["high"]/z["low"]-1,WIDTH_RATIO,5)

    def test_future_prices_cannot_change_frozen_rectangle(self):
        f,d=history()
        frozen=34*DAY
        baseline=select_box_at_cutoff(f,d,frozen)
        later_f=copy.deepcopy(f)
        later_d=copy.deepcopy(d)
        for candle in later_f:
            if candle["t"]+SECS4>frozen:
                candle["c"]*=2
        for candle in later_d:
            if candle["t"]+DAY>frozen:
                candle["c"]*=3
        checked=select_box_at_cutoff(later_f,later_d,frozen)
        self.assertEqual(baseline,checked)

    def test_break_never_precedes_freeze(self):
        f,d=history()
        z=select_box_at_cutoff(f,d,34*DAY)
        for i in range(36*6,37*6):
            f[i]=bar(f[i]["t"],94,95,90,91)
        idx=identify_first_break(f,z)
        self.assertIsNotNone(idx)
        self.assertGreaterEqual(f[idx]["t"],z["frozenTs"])
        self.assertLess(f[idx]["c"],z["low"])

    def test_touch_then_bearish_reject_and_six_hour_future_metric(self):
        f,d=history(45)
        z=select_box_at_cutoff(f,d,34*DAY)
        br=36*6
        f[br]=bar(f[br]["t"],94,95,90,89)
        f[br+1]=bar(f[br+1]["t"],94,95,88,89.5)
        # A prior break that is detected even with follow-through to come.
        point=identify_first_break(f,z)
        self.assertEqual(point,br)
        o=examine_after_break(f,z,point)
        self.assertEqual(o["state"],"BEARISH_RETEST_REJECTION")
        self.assertEqual(o["retestTs"],f[br+1]["t"]+SECS4)
        self.assertLess(o["retestTs"]-o["breakTs"],2*SECS4)
        self.assertIsNotNone(o["next6AfterBreakPct"])

    def test_reclaim_is_not_bearish_retest(self):
        f,d=history(45)
        z=select_box_at_cutoff(f,d,34*DAY)
        br=36*6
        f[br]=bar(f[br]["t"],94,95,90,89)
        f[br+1]=bar(f[br+1]["t"],99,106,98,105)
        result=examine_after_break(f,z,br)
        self.assertEqual(result["state"],"RECLAIMED_ABOVE_ZONE")
        self.assertIsNone(result["retestUTC"])

    def test_no_assumed_success_if_no_future_six_candles(self):
        f,d=history(35)
        z=select_box_at_cutoff(f,d,34*DAY)
        f[-1]=bar(f[-1]["t"],93,94,88,87)
        outcome=examine_after_break(f,z,len(f)-1)
        self.assertIsNone(outcome["next6AfterBreakPct"])
        self.assertTrue(outcome["next6AfterBreakUnresolved"])

    def test_zero_events_not_a_profitable_prediction(self):
        stats=safe_summary([])
        self.assertEqual(stats["cases"],0)
        self.assertIsNone(stats["breakFollowThroughDownRatePct"])
        self.assertIsNone(stats["retestFollowThroughDownRatePct"])


if __name__=="__main__":
    unittest.main()
