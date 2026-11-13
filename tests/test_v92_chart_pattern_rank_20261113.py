#!/usr/bin/env python3
"""Causal 4H graph-pattern research-only validation tests."""
import unittest
from unittest.mock import patch
from collections import Counter

from v92_chart_pattern_rank_20261113 import (
    FAMILIES,COOLDOWN_BARS,PERIODS,OVERLAY_MAX_AGE_4H,
    _swing_marks,detect_at,detect_all,urchin_eval,wilson_lower,
    score_events,choose_training_families,ClosedEventLookup,
    overlay_gate,FOUR,HOUR,STANDALONE_STOP_ATR,
)

def bars(n=100,start=0):
    result=[]
    for j in range(n):
        result.append({
            "t":start+j*FOUR,
            "o":100.,"h":101.,"l":99.,"c":100.,"v":100.,
        })
    return result


class TestChartPatternCausality(unittest.TestCase):
    def test_no_future_pivot_used(self):
        x=bars(110)
        x[62]["l"]=95.;x[73]["l"]=95.25
        x[68]["h"]=103.;x[57]["c"]=103.
        x[85].update(o=100.,h=105.,l=99.,c=104.)
        full=detect_at(x,85,_swing_marks(x))
        prefix=detect_at(x[:86],85,_swing_marks(x[:86]))
        self.assertEqual(full,prefix)
        names=[e["family"] for e in full]
        self.assertIn("DOUBLE_BOTTOM",names)
        for e in full:
            self.assertEqual(e["knownUTC"],86*FOUR)
            self.assertTrue(e["pivotHas2RightBarConfirmation"])

    def test_pivot_requires_two_right_candles(self):
        x=bars(90)
        x[80]["h"]=111.
        marks=_swing_marks(x)
        self.assertTrue(marks[0][80])
        y=x[:82]
        self.assertFalse(_swing_marks(y)[0][80])

    def test_1R_hit_24h_is_not_live_signal_and_stop_first(self):
        x=bars()
        event={"index":70,"family":"BULL_FLAG","side":"bullish",
               "confirmed4HCloseUTC":"1970-01-12T20:00:00Z",
               "ATR14_4H":1.}
        x[71].update(o=100.,l=98.,h=102.,c=100.)
        z=urchin_eval(event,x,99*FOUR)
        self.assertEqual(z["exitReason"],"STOP_FIRST")
        self.assertFalse(z["targetHitBeforeStop"])
        self.assertLess(z["netR25Bps"],z["netR9Bps"])
        self.assertEqual(STANDALONE_STOP_ATR,1.5)

    def test_target_first_requires_no_stop_collision(self):
        x=bars()
        event={"index":70,"family":"BEAR_FLAG","side":"bearish",
               "confirmed4HCloseUTC":"dummy","ATR14_4H":1.}
        x[71].update(o=100.,l=97.,h=101.,c=99.)
        z=urchin_eval(event,x,99*FOUR)
        self.assertEqual(z["exitReason"],"TARGET_FIRST")
        self.assertTrue(z["targetHitBeforeStop"])

    def test_end_of_series_does_not_fake_future_winner(self):
        x=bars()
        event={"index":96,"family":"BEAR_FLAG","side":"bearish",
               "confirmed4HCloseUTC":"dummy","ATR14_4H":1.}
        self.assertIsNone(urchin_eval(event,x,99*FOUR))

    def test_lookup_ignores_future_and_stale_confirmations(self):
        e=[
            {"family":"BULL_FLAG","side":"bullish","knownUTC":100*FOUR},
            {"family":"DOUBLE_TOP","side":"bearish","knownUTC":110*FOUR},
            {"family":"BULL_FLAG","side":"bullish","knownUTC":120*FOUR},
        ]
        lookup=ClosedEventLookup(e)
        same,opp=lookup.at(112*FOUR,"bearish",{"BULL_FLAG","DOUBLE_TOP"})
        self.assertEqual([x["family"] for x in same],["DOUBLE_TOP"])
        self.assertEqual([x["family"] for x in opp],["BULL_FLAG"])
        self.assertEqual(lookup.at(90*FOUR,"bullish",FAMILIES),([],[]))
        self.assertEqual(lookup.at(140*FOUR,"bullish",FAMILIES),([],[]))
        self.assertEqual(OVERLAY_MAX_AGE_4H,12)

    def test_early_only_train_selection(self):
        scores={f:{"signalsWith24hOutcome":0,"netR25Bps":0.,
                   "hitRatePct":None,"wilsonLower95Pct":None}
                for f in FAMILIES}
        scores["DOUBLE_BOTTOM"].update(
            signalsWith24hOutcome=40,netR25Bps=3.2,
            hitRatePct=60.,wilsonLower95Pct=45.)
        scores["BULL_FLAG"].update(
            signalsWith24hOutcome=12,netR25Bps=1.2,
            hitRatePct=66.67,wilsonLower95Pct=38.)
        scores["DOUBLE_TOP"].update(
            signalsWith24hOutcome=50,netR25Bps=-2.,
            hitRatePct=78.,wilsonLower95Pct=60.)
        chosen=choose_training_families(scores)
        self.assertEqual(chosen["selectedExploratory"],
                         ["DOUBLE_BOTTOM","BULL_FLAG"])
        self.assertEqual(chosen["qualifyingUnderConservativeSampleGate"],
                         ["DOUBLE_BOTTOM"])
        self.assertTrue(chosen["selectionMadeOnlyUsing2022_2024"])

    def test_zero_samples_no_fake_high_rank(self):
        self.assertEqual(wilson_lower(0,0),0.)
        self.assertLess(wilson_lower(1,1),.25)
        self.assertTrue(0<wilson_lower(60,100)<.60)

    @patch("v92_chart_pattern_rank_20261113.make_selective_gate")
    def test_SOL_v92_original_veto_precedes_selected(self,original):
        original.return_value=lambda one,active,retest: {
            "passed":False,"reasons":["ORIGINAL"]}
        lookup=ClosedEventLookup([])
        audit=Counter()
        f=overlay_gate("SOLUSDT","C_SELECTED_OPPOSITE_VETO",[],
                       lookup,{"DOUBLE_TOP"},audit)
        t=6*HOUR
        z=f([{"t":t-HOUR}],{"knownUTC":t-2*HOUR,"side":"bullish"},
            {"t":t-HOUR})
        self.assertFalse(z["passed"])
        self.assertEqual(audit["originalV92SolVeto"],1)

    def test_fixed_two_time_blocks_and_families(self):
        self.assertEqual(sum(len(x["months"])*3 for x in PERIODS.values()),159)
        self.assertEqual(len(FAMILIES),9)
        self.assertEqual(COOLDOWN_BARS,6)


if __name__=="__main__":
    unittest.main()
