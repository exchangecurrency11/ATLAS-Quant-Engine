"""Precommitted V9.2 high-profile reversal shortlist and research-only safety tests."""
import unittest
from collections import Counter
from v92_selected_reversal_patterns import (
    RESEARCH_QUALIFICATION,STRATEGY,soldier_crow,make_selective_gate)
from v92_multi_candle_invalidation import all_patterns_at
from v92_bull_bear_candle_invalidation import HOUR,FOUR
BASE=1794009600

def bar(index,interval=HOUR,**kw):
    d={"t":BASE+interval*index,"o":100.,"h":101.,
       "l":99.,"c":100.,"v":1000.}
    d.update(kw)
    return d

def three(side,interval=HOUR):
    x=[bar(i,interval) for i in range(40)]
    if side=="bullish":
        x[35]["c"]=102.
        x[35]["h"]=103.
        x[39]["c"]=99.
        x.extend([
            bar(40,interval,o=99,h=103,l=98,c=102),
            bar(41,interval,o=101,h=104,l=100,c=103),
            bar(42,interval,o=102,h=105,l=101,c=104)])
    else:
        x[35]["c"]=99.
        x[39]["c"]=102.
        x[39]["h"]=103.
        x.extend([
            bar(40,interval,o=102,h=103,l=98,c=99),
            bar(41,interval,o=100,h=101,l=97,c=98),
            bar(42,interval,o=99,h=100,l=96,c=97)])
    return x

def star_reversal(side):
    x=[bar(i) for i in range(27)]
    # prior20 levels high=102, low=98 -> fake breakout.
    for b in x:
        b["h"]=102.;b["l"]=98.
    if side=="bearish":
        x.extend([
            bar(27,o=101.,h=106.,l=100.,c=105.),
            bar(28,o=105.,h=112.,l=104.,c=105.2),
            bar(29,o=105.,h=106.,l=98.,c=99.)])
    else:
        x.extend([
            bar(27,o=99.,h=100.,l=94.,c=95.),
            bar(28,o=95.,h=96.,l=88.,c=94.8),
            bar(29,o=95.,h=102.,l=94.,c=101.)])
    return x

class V92SelectiveReversalTests(unittest.TestCase):
    def test_selected_families_are_only_star_and_confirmed_harami(self):
        p=RESEARCH_QUALIFICATION
        self.assertEqual(p["selectedPatternFamilies"],
                         ["STAR","HARAMI_CONFIRMED"])
        self.assertEqual(p["eligibleOnlyOn"],"SOLUSDT")
        self.assertTrue(p["requirePrior20HighLowSweepAndReentry"])
        self.assertFalse(p["isStatisticallyValidatedHighSuccessRate"])
        self.assertEqual(p["HIKKAKE_CONFIRMED"],"OBSERVE_ONLY")
        self.assertEqual(p["ENGULFING"],"OBSERVE_ONLY")
        self.assertIn("SHADOW_ONLY",STRATEGY)

    def test_soldiers_and_crows_symmetry(self):
        for side,name in (("bullish","THREE_WHITE_SOLDIERS"),
                          ("bearish","THREE_BLACK_CROWS")):
            d=three(side)
            x=soldier_crow(d,len(d)-1,HOUR)
            self.assertIsNotNone(x)
            self.assertEqual(x["name"],name)
            self.assertEqual(x["direction"],side)
            self.assertTrue(x["researchWatchOnly"])
            self.assertTrue(x["noAutoVeto"])

    def test_no_two_candle_soldier_signal(self):
        d=three("bullish")
        self.assertIsNone(soldier_crow(d,len(d)-2,HOUR))

    def test_fully_closed_4h_candle_can_be_observed(self):
        d=three("bearish",FOUR)
        x=soldier_crow(d,len(d)-1,FOUR)
        self.assertEqual(x["name"],"THREE_BLACK_CROWS")

    def test_unconfirmed_wrong_color_crow_rejected(self):
        d=three("bearish")
        d[-1]["o"]=96.
        d[-1]["c"]=97.
        self.assertIsNone(soldier_crow(d,len(d)-1,HOUR))

    def test_gap_in_data_rejected(self):
        d=three("bullish")
        d[-1]["t"]+=50
        with self.assertRaisesRegex(ValueError,"GAPPED"):
            soldier_crow(d,len(d)-1,HOUR)

    def test_sol_veto_bearish_morningstar(self):
        d=star_reversal("bullish")
        assert any(p["name"]=="MORNING_STAR" for p in
                   all_patterns_at(d,len(d)-1,HOUR))
        at=d[-1]["t"]+HOUR
        ev=Counter();ev["examples"]=[]
        gate=make_selective_gate("SOLUSDT",[],"SELECTED_SOL_STRICT_SWEEP",ev)
        x=gate(d,{"side":"bearish"},d[-1])
        self.assertFalse(x["passed"])
        self.assertEqual(ev["vetoes"],1)

    def test_sol_veto_bullish_eveningstar(self):
        d=star_reversal("bearish")
        at=d[-1]["t"]+HOUR
        ev=Counter();ev["examples"]=[]
        gate=make_selective_gate("SOLUSDT",[],"SELECTED_SOL_STRICT_SWEEP",ev)
        x=gate(d,{"side":"bullish"},d[-1])
        self.assertFalse(x["passed"])
        self.assertEqual(ev["vetoes"],1)

    def test_btc_even_strong_reversal_is_observation_only(self):
        d=star_reversal("bearish")
        ev=Counter();ev["examples"]=[]
        gate=make_selective_gate("BTCUSDT",[],"SELECTED_SOL_STRICT_SWEEP",ev)
        x=gate(d,{"side":"bullish"},d[-1])
        self.assertTrue(x["passed"])
        self.assertEqual(ev["vetoes"],0)
        self.assertEqual(ev["opposingSelectedPatternsObserved"],1)

    def test_sol_same_side_does_not_invalidate(self):
        d=star_reversal("bearish")
        ev=Counter();ev["examples"]=[]
        gate=make_selective_gate("SOLUSDT",[],"SELECTED_SOL_STRICT_SWEEP",ev)
        self.assertTrue(gate(d,{"side":"bearish"},d[-1])["passed"])

    def test_observe_mode_never_invalidates_any_position(self):
        d=star_reversal("bullish")
        ev=Counter();ev["examples"]=[]
        gate=make_selective_gate("SOLUSDT",[],"OBSERVE_ONLY",ev)
        x=gate(d,{"side":"bearish"},d[-1])
        self.assertTrue(x["passed"])
        self.assertEqual(ev["opposingSelectedPatternsObserved"],1)

    def test_unknown_variant_rejected(self):
        with self.assertRaisesRegex(ValueError,"UNKNOWN_MODE"):
            make_selective_gate("SOLUSDT",[],"FITTED_TO_HISTORY",Counter())
if __name__=="__main__":
    unittest.main()
