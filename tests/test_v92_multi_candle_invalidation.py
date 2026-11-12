"""Symmetric V9.2 Harami/Engulfing/Hikkake validation and no-lookahead."""
import copy
import unittest
from collections import Counter
from v92_multi_candle_invalidation import (
    HOUR,FOUR,FAMILIES,RETEST_MODES,
    pattern_at,warnings_at_retest,make_retest_gate,
    sweep_before,all_patterns_at
)

BASE=1794009600  # UTC-aligned for 1H and 4H

def bar(index,interval=HOUR, **updates):
    b={"t":BASE+index*interval,"o":100.,"h":101.,
       "l":99.,"c":100.,"v":1000.}
    b.update(updates)
    return b

def synthetic(family,side,interval=HOUR):
    rows=[bar(i,interval) for i in range(40)]
    if family=="HARAMI_CONFIRMED":
        rows[35]["c"]=100.8 if side=="bullish" else 99.2
        rows[39]["c"]=99.2 if side=="bullish" else 100.8
        if side=="bullish":
            rows.extend([
                bar(40,interval,o=101,h=102,l=94,c=95),
                bar(41,interval,o=96,c=97,h=98,l=95),
                bar(42,interval,o=97,c=100,h=101,l=96)])
        else:
            rows.extend([
                bar(40,interval,o=95,h=102,l=94,c=101),
                bar(41,interval,o=100,c=99,h=101,l=98),
                bar(42,interval,o=99,c=96,h=100,l=95)])
    elif family=="ENGULFING":
        rows[35]["c"]=100.8 if side=="bullish" else 99.2
        rows[39]["c"]=99.2 if side=="bullish" else 100.8
        if side=="bullish":
            rows.extend([
                bar(40,interval,o=100,c=99,h=100.5,l=98.5),
                bar(41,interval,o=98.5,c=101.5,h=102,l=98)])
        else:
            rows.extend([
                bar(40,interval,o=99,c=100,h=100.5,l=98.5),
                bar(41,interval,o=100.5,c=98.5,h=101,l=98)])
    elif family=="HIKKAKE_CONFIRMED":
        rows.append(bar(40,interval,o=100,h=105,l=95,c=100))
        rows.append(bar(41,interval,o=100,h=103,l=97,c=100))
        if side=="bullish":
            rows.append(bar(42,interval,o=99,h=102,l=94,c=96))
            rows.append(bar(43,interval,o=99,h=105,l=97,c=104))
        else:
            rows.append(bar(42,interval,o=102,h=106,l=98,c=104))
            rows.append(bar(43,interval,o=102,h=104,l=94,c=96))
    else:raise ValueError(family)
    return rows

class V92MultiPatternsTests(unittest.TestCase):
    def test_symmetric_harami_with_third_close_confirmation(self):
        for side in ("bullish","bearish"):
            with self.subTest(side=side):
                bars=synthetic("HARAMI_CONFIRMED",side)
                self.assertIsNone(pattern_at(bars,len(bars)-2,HOUR,"HARAMI_CONFIRMED"))
                row=pattern_at(bars,len(bars)-1,HOUR,"HARAMI_CONFIRMED")
                self.assertIsNotNone(row)
                self.assertEqual(row["name"],side.upper()+"_HARAMI_CONFIRMED")
                self.assertTrue(row["onlyClosedCandlesUsed"])
                self.assertTrue(row["signalIsNotStandaloneTrade"])

    def test_symmetric_engulfing_reversal_only_after_second_close(self):
        for side in ("bullish","bearish"):
            bars=synthetic("ENGULFING",side)
            self.assertIsNotNone(pattern_at(bars,len(bars)-1,HOUR,"ENGULFING"))
            self.assertEqual(pattern_at(bars,len(bars)-1,HOUR,"ENGULFING")["direction"],side)

    def test_symmetric_confirmed_hikkake_not_initial_false_break(self):
        for side in ("bullish","bearish"):
            bars=synthetic("HIKKAKE_CONFIRMED",side)
            self.assertIsNone(pattern_at(bars,len(bars)-2,HOUR,"HIKKAKE_CONFIRMED"))
            pattern=pattern_at(bars,len(bars)-1,HOUR,"HIKKAKE_CONFIRMED")
            self.assertEqual(pattern["direction"],side)
            self.assertTrue(pattern["internalHikkakeFalseBreakConfirmed"])

    def test_hikkake_confirmation_can_be_second_or_third_bar(self):
        for confirm_index in (44,45):
            bars=synthetic("HIKKAKE_CONFIRMED","bullish")
            bars[-1]=bar(43,c=100)
            for i in range(44,confirm_index):
                bars.append(bar(i,c=100))
            bars.append(bar(confirm_index,c=104,h=105))
            pattern=pattern_at(bars,len(bars)-1,HOUR,"HIKKAKE_CONFIRMED")
            self.assertIsNotNone(pattern)

    def test_hikkake_confirmation_expiry_and_first_confirm_only(self):
        bars=synthetic("HIKKAKE_CONFIRMED","bullish")
        bars[-1]=bar(43,c=100)
        for i in (44,45,46):
            bars.append(bar(i,c=100))
        bars.append(bar(47,c=104,h=105))
        self.assertIsNone(pattern_at(bars,len(bars)-1,HOUR,"HIKKAKE_CONFIRMED"))
        early=synthetic("HIKKAKE_CONFIRMED","bullish")
        early.append(bar(44,c=104,h=105))
        self.assertIsNone(pattern_at(early,len(early)-1,HOUR,"HIKKAKE_CONFIRMED"))

    def test_opposite_warning_rejects_wrong_trade_direction_not_same(self):
        for family in ("HARAMI_CONFIRMED","HIKKAKE_CONFIRMED","ENGULFING"):
            bars=synthetic(family,"bullish")
            t=bars[-1]["t"]+HOUR
            self.assertTrue(warnings_at_retest(
                bars,[],t,"bearish",{family}))
            self.assertEqual(warnings_at_retest(
                bars,[],t,"bullish",{family}),[])

    def test_causal_four_hour_excludes_not_yet_closed_pattern(self):
        h1=[bar(i,HOUR) for i in range(48)]
        four=synthetic("ENGULFING","bearish",FOUR)
        t=h1[-1]["t"]+HOUR
        self.assertEqual(warnings_at_retest(h1,four,t,"bullish",
                                            {"ENGULFING"}),[])
        # Once the 4H confirmation closes it may be observed; never before.

    def test_gap_or_malformed_candle_fails_closed(self):
        bars=synthetic("HIKKAKE_CONFIRMED","bearish")
        bars[-3]["t"]+=15
        with self.assertRaisesRegex(ValueError,"GAPPED"):
            pattern_at(bars,len(bars)-1,HOUR,"HIKKAKE_CONFIRMED")
        bars=synthetic("ENGULFING","bullish")
        bars[-1]["h"]=20
        with self.assertRaisesRegex(ValueError,"MALFORMED"):
            pattern_at(bars,len(bars)-1,HOUR,"ENGULFING")

    def test_harami_without_third_confirmation_rejected(self):
        x=synthetic("HARAMI_CONFIRMED","bullish")
        x[-1]["c"]=97
        self.assertIsNone(pattern_at(x,len(x)-1,HOUR,"HARAMI_CONFIRMED"))

    def test_engulfing_without_previous_trend_rejected(self):
        x=synthetic("ENGULFING","bearish")
        x[34]["c"]=100.5
        self.assertIsNone(pattern_at(x,len(x)-1,HOUR,"ENGULFING"))

    def test_sweep_requires_prior_twenty_and_reentry(self):
        x=synthetic("HIKKAKE_CONFIRMED","bullish")
        self.assertFalse(sweep_before(x,5,len(x)-1,"bullish"))
        self.assertTrue(isinstance(sweep_before(x,40,len(x)-1,"bullish"),bool))

    def test_full_combined_mode_is_same_causal_rule_never_order(self):
        a=synthetic("HIKKAKE_CONFIRMED","bearish")
        t=a[-1]["t"]+HOUR
        e=Counter()
        e["vetoExamples"]=[]
        filter_=make_retest_gate([],"ALL_REVERSALS_SWEEP_CONTEXT",e)
        result=filter_(a,{"side":"bullish"},a[-1])
        self.assertFalse(result["passed"])
        self.assertEqual(e["vetoedOriginalRetests"],1)

    def test_invalid_asof_or_mode_fails_closed(self):
        bars=synthetic("ENGULFING","bearish")
        with self.assertRaisesRegex(ValueError,"MATCHED_CLOSED_HOUR"):
            warnings_at_retest(bars,[],bars[-1]["t"],"bullish",{"ENGULFING"})
        with self.assertRaisesRegex(ValueError,"UNREGISTERED_PATTERN"):
            pattern_at(bars,len(bars)-1,HOUR,"NONE")
        with self.assertRaisesRegex(ValueError,"UNREGISTERED_RETEST_VARIANT"):
            make_retest_gate([],"NONE",Counter())

if __name__=="__main__":unittest.main()
