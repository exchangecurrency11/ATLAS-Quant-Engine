#!/usr/bin/env python3
"""Tests for isolated V9.2 historical filter ablation. No production edits."""
import unittest
from collections import Counter
from math import sin
from unittest.mock import patch

import backtest_retest_long_v4 as original
from download_binance_um_history import aggregate
from signal_quality_v7 import evaluate_bos_quality
from v92_filter_ablation_20261113 import (
    ABLATIONS,ONE_BY_ONE,PAIRS,EXPECTED_PREVIOUS,CONTROL_REQUIREMENTS,
    fork_source,instrumentation,paired,valid_baseline_period,
    followup_shortlist
)

def _trade(ts,r):
    return {"entryOpenUTC":ts,"side":"bullish",
            "exitKnownUTC":ts+3600,
            "netRIllustrative":r}


class TestStrictAblation(unittest.TestCase):
    def test_exact_original_source_pattern_freezes_without_mutation(self):
        before=original.replay_pair.__code__.co_code
        fork=fork_source()
        self.assertIn("def replay_pair(",fork)
        self.assertIn("_momentum_possible(ind)",fork)
        self.assertEqual(before,original.replay_pair.__code__.co_code)
        self.assertNotIn("_momentum_possible",original.replay_pair.__code__.co_names)

    def test_pre_registered_preset_count_and_mandatory_spine(self):
        self.assertEqual(len(ABLATIONS),19)
        self.assertEqual(len(ONE_BY_ONE),14)
        self.assertEqual(len(PAIRS),4)
        self.assertEqual(len(EXPECTED_PREVIOUS),6)
        self.assertEqual(len(CONTROL_REQUIREMENTS),8)
        self.assertTrue(all(len(ABLATIONS[x])==1 for x in ONE_BY_ONE))
        self.assertTrue(all(len(ABLATIONS[x])==2 for x in PAIRS))

    def test_momentum_disabled_per_side(self):
        cache={"indicators":{},"bias":{},"structures":{}}
        engine,_=instrumentation("NO_1H_RSI_DIRECTION",
                                 symbol="BTCUSDT",four=[],cache=cache)
        side=engine.__globals__["_momentum_side"]
        self.assertTrue(side({"RSI14":70,"hist":-2},"bearish"))
        self.assertFalse(side({"RSI14":20,"hist":-2},"bullish"))
        base,_=instrumentation("BASELINE",symbol="BTCUSDT",
                               four=[],cache=cache)
        self.assertFalse(base.__globals__["_momentum_side"](
            {"RSI14":70,"hist":-2},"bearish"))

    def test_htf_single_dimension_removal_not_both(self):
        cache={"indicators":{},"bias":{},"structures":{}}
        e,_=instrumentation("NO_4H_TREND_ALIGNMENT",
                             symbol="ETHUSDT",four=[],cache=cache)
        f=e.__globals__["_htf_side"]
        self.assertTrue(f(["mixed","bearish"],"bearish"))
        self.assertFalse(f(["bearish","bullish"],"bearish"))
        e2,_=instrumentation("PAIR_NO_4H_AND_DAILY",
                             symbol="ETHUSDT",four=[],cache=cache)
        self.assertTrue(e2.__globals__["_htf_side"](
            ["mixed","mixed"],"bullish"))

    def test_baseline_original_quality_matches_default(self):
        cache={"indicators":{},"bias":{},"structures":{}}
        e,quality=instrumentation("BASELINE",
                                 symbol="SOLUSDT",four=[],cache=cache)
        window=[{"t":i*3600,"o":100.,"h":102.,"l":98.,
                 "c":100.,"v":100.} for i in range(50)]
        window[-1].update(o=101.,c=102.,h=104.,v=200.)
        bos={"event":"BOS","direction":"bullish",
             "brokenLevel":100.,"at":window[-1]["t"]}
        ind={"EMA20":100.,"RSI14":55.,"hist":.3}
        self.assertEqual(quality(window,bos,ind),
                         evaluate_bos_quality(window,bos,ind))

    def test_retest_relaxation_never_disables_touch_and_structure_close(self):
        cache={"indicators":{},"bias":{},"structures":{}}
        e,_=instrumentation("NO_RETEST_CANDLE_COLOR",
                             symbol="BTCUSDT",four=[],cache=cache)
        decision=e.__globals__["reaction_confirmed"]
        prev={"c":104}
        self.assertTrue(decision(
            "bullish",{"l":99,"h":110,"c":105,"o":106},prev,100))
        self.assertFalse(decision(
            "bullish",{"l":101,"h":110,"c":105,"o":106},prev,100))
        self.assertFalse(decision(
            "bullish",{"l":99,"h":110,"c":99.5,"o":99.},prev,100))

    def test_research_risk_bounds_preserve_stop_validity(self):
        cache={"indicators":{},"bias":{},"structures":{}}
        e,_=instrumentation("RISK_STOP_MAX_6PCT_NOT_4PCT",
                             symbol="BTCUSDT",four=[],cache=cache)
        init=e.__globals__["init_position"]
        pending={"side":"bullish","stop":95.}
        self.assertIsNotNone(init(pending,100.,18000))
        self.assertIsNone(init({"side":"bullish","stop":101.},
                               100.,18000))
        baseline,_=instrumentation("BASELINE",symbol="BTCUSDT",
                                   four=[],cache=cache)
        self.assertIsNone(baseline.__globals__["init_position"](
            pending,100.,18000))

    def test_paired_trade_changes_and_nonsimilar_kept_fail(self):
        old=[_trade(3600,1.5),_trade(7200,-1.0)]
        new=[_trade(7200,-1.0),_trade(10800,.8)]
        d=paired(old,new)
        self.assertEqual(d["baselineWinnersLost"],1)
        self.assertEqual(d["baselineLosersAvoided"],0)
        self.assertEqual(d["newTrades"],1)
        self.assertEqual(d["newWinners"],1)
        with self.assertRaisesRegex(ValueError,"SHARED_ENTRY_PNL_DRIFT"):
            paired(old,[_trade(7200,-.9)])

    def test_all_baseline_refs_required(self):
        score={"trades":10,"netR9Bps":-4.265784,
               "netR25Bps":-7.701252}
        self.assertTrue(valid_baseline_period(
            "2022_2024","BTCUSDT",score))
        self.assertFalse(valid_baseline_period(
            "2022_2024","BTCUSDT",{
                **score,"trades":9}))

    def test_fork_identical_reference_replay_on_synthetic_closed_bars(self):
        # Real time-aligned 1H, 4H, 1D series. Baseline synthetic parity
        # is checked BEFORE official six historical baseline checks.
        bars=[]
        for i in range(1752):
            base=100+0.025*i+3*sin(i/19)
            bars.append({
                "t":i*3600,"o":base-0.1,
                "h":base+0.6,"l":base-0.7,
                "c":base+.1,"v":100+(i%13)*10.})
        four=aggregate(bars,14400)
        daily=aggregate(bars,86400)
        end=bars[-1]["t"]+3600
        baseline=original.replay_pair(
            bars,four,daily,as_of=end,retest_hours=4,
            bos_quality_filter=evaluate_bos_quality)
        cache={"indicators":{},"bias":{},"structures":{}}
        engine,quality=instrumentation(
            "BASELINE",symbol="BTCUSDT",four=four,cache=cache)
        fork=engine(bars,four,daily,as_of=end,retest_hours=4,
                    bos_quality_filter=quality)
        self.assertEqual(baseline["alerts"],fork["alerts"])
        self.assertEqual(baseline["trades"],fork["trades"])
        self.assertEqual(baseline["qualityGateRejectedBOS"],
                         fork["qualityGateRejectedBOS"])

if __name__=="__main__":
    unittest.main()
