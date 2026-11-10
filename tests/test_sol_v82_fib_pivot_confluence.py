"""V8.2: Fibonacci/pivot causality and small-sample hit-rate guard."""
import copy
import unittest

from sol_v82_fib_pivot_confluence import (
    previous_day_pivots,frozen_confluence,wilson_lower,summarize,SECS4,DAY
)


def mkbar(t,o=100,h=103,l=97,c=100,v=100):
    return {"t":t,"o":o,"h":h,"l":l,"c":c,"v":v}


def synthetic():
    four=[mkbar(i*SECS4,h=111,l=96,c=103) for i in range(78)]
    # existing breakdown & subsequent red rejection known before entry
    for i in range(50,54):
        four[i]=mkbar(i*SECS4,o=101,h=106,l=92,c=97)
    four[54]=mkbar(54*SECS4,o=102,h=104,l=93,c=96)
    daily=[mkbar(i*DAY,o=101,h=110,l=90,c=99) for i in range(16)]
    return four,daily


class FrozenFibPivotTests(unittest.TestCase):
    def test_standard_previous_day_classic_pivots(self):
        f,d=synthetic()
        ret=f[54]
        p=previous_day_pivots(d,ret)
        self.assertEqual(p["levels"]["P"],(110+90+99)/3)
        self.assertAlmostEqual(p["levels"]["R1"],2*p["levels"]["P"]-90)
        self.assertAlmostEqual(p["levels"]["S1"],2*p["levels"]["P"]-110)
        self.assertAlmostEqual(p["levels"]["R2"],p["levels"]["P"]+20)
        self.assertAlmostEqual(p["levels"]["S2"],p["levels"]["P"]-20)
        self.assertLessEqual(p["sourceIndex"],ret["t"]//DAY-1)

    def test_unfinished_current_day_never_changes_previous_pivot(self):
        four,daily=synthetic()
        base=previous_day_pivots(daily,four[54])
        later=copy.deepcopy(daily)
        today=four[54]["t"]//DAY
        later[today]["h"]=100000
        later[today]["c"]=100000
        self.assertEqual(base,previous_day_pivots(later,four[54]))

    def test_fib_anchor_only_prebreak_and_before_retest(self):
        four,daily=synthetic()
        info=frozen_confluence(four,daily,50,54)
        self.assertAlmostEqual(info["fibAnchorSwingHighPrebreak"],111,places=4)
        self.assertAlmostEqual(info["fibAnchorSwingLowBreakToRetest"],92,places=4)
        self.assertAlmostEqual(info["fib382"],92+.382*19,places=4)
        self.assertAlmostEqual(info["fib618"],92+.618*19,places=4)
        self.assertFalse(info["MACDUsed"])
        self.assertIn(info["confluenceScore"],(0,1,2))

    def test_future_changes_cannot_change_existing_flags(self):
        four,daily=synthetic()
        baseline=frozen_confluence(four,daily,50,54)
        laterf=copy.deepcopy(four)
        laterd=copy.deepcopy(daily)
        for x in laterf[55:]:
            x["h"]*=1000
            x["l"]*=0.01
            x["c"]*=5
        for x in laterd:
            if x["t"]>=four[54]["t"]:
                x["h"]*=100
                x["c"]*=100
        self.assertEqual(baseline,frozen_confluence(laterf,laterd,50,54))

    def test_retest_has_to_follow_break_in_time(self):
        four,daily=synthetic()
        with self.assertRaisesRegex(ValueError,"INVALID_EVENT_TIMELINE"):
            frozen_confluence(four,daily,54,54)
        with self.assertRaisesRegex(ValueError,"INVALID_EVENT_TIMELINE"):
            frozen_confluence(four,daily,55,54)

    def test_zero_n_does_not_claim_success(self):
        result=summarize([])
        self.assertIsNone(result["directionHitRatePct"])
        self.assertFalse(result["meets75GoalWithMin30"])
        self.assertIsNone(wilson_lower(0,0))

    def test_75_percent_from_four_events_is_not_approved(self):
        cases=[{"future24hPct":-1.0}]*3+[{"future24hPct":1.0}]
        r=summarize(cases)
        self.assertEqual(r["directionHitRatePct"],75.0)
        self.assertEqual(r["complete24hObservations"],4)
        self.assertTrue(r["goal75ObservedInThisSample"])
        self.assertFalse(r["min30Observations"])
        self.assertFalse(r["meets75GoalWithMin30"])
        self.assertLess(r["wilson95LowerBoundPct"],50)


if __name__=="__main__":
    unittest.main()
