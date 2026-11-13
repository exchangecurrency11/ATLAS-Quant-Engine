#!/usr/bin/env python3
"""Unit tests for research-only, four-mode candle ablation."""
import unittest
from collections import Counter
from unittest.mock import patch

from v92_four_candle_models_20261113 import (
    PERIODS, PATTERNS, MODES, epoch, opposite, matched_patterns,
    new_gate, paired_deltas, parity_check, trade_key, trade_summary
)

def demo_trade(ts, r):
    return {
        "watchKnownUTC":ts-7200,
        "retestKnownUTC":ts-3600,
        "entryOpenUTC":ts,
        "exitKnownUTC":ts+3600,
        "side":"bullish",
        "entry":100., "stop":99., "risk":1.,
        "netRIllustrative":r, "exitReason":"TIME_EXIT_AT_CLOSE",
    }

def pattern(direction="bearish", confirmed="1970-01-01T03:00:00Z"):
    return {
        "direction":direction,"confirmedUTC":confirmed,
        "family":"ENGULFING","tf":"1H",
        "prior20LiquiditySweepAndReentry":True,
        "internalHikkakeFalseBreakConfirmed":False,
    }

class TestFixedRules(unittest.TestCase):
    def test_frozen_period_boundaries(self):
        self.assertEqual(PERIODS["2022_2024"]["count1H"],21216)
        self.assertEqual(PERIODS["2024_2026"]["count1H"],17520)
        self.assertEqual(len(PERIODS["2022_2024"]["months"]),29)
        self.assertEqual(len(PERIODS["2024_2026"]["months"]),24)
        self.assertEqual(sum(len(p["months"])*3 for p in PERIODS.values()),159)
        self.assertEqual(epoch("2026-10-01T00:00:00Z"),
                         1790812800)
        self.assertEqual(opposite("bullish"),"bearish")
        self.assertEqual(opposite("bearish"),"bullish")
        self.assertEqual(len(MODES),4)
        self.assertEqual(PATTERNS,{
            "STAR","HARAMI_CONFIRMED","ENGULFING","HIKKAKE_CONFIRMED"
        })

    @patch("v92_four_candle_models_20261113.warnings_at_retest")
    def test_opposing_requires_sweep_and_same_side_does_not(self,func):
        func.return_value=[]
        matched_patterns([{"t":7200}],[],10800,"bullish",
                         "opposing",strict_sweep=True)
        self.assertEqual(func.call_args.args[3],"bullish")
        self.assertTrue(func.call_args.kwargs["require_sweep"])
        matched_patterns([{"t":7200}],[],10800,"bullish","same")
        self.assertEqual(func.call_args.args[3],"bearish")
        self.assertFalse(func.call_args.kwargs["require_sweep"])

    @patch("v92_four_candle_models_20261113.warnings_at_retest")
    def test_future_pattern_fails_closed(self,func):
        func.return_value=[pattern(confirmed="1970-01-01T03:00:01Z")]
        with self.assertRaisesRegex(ValueError,"FUTURE_PATTERN_LEAK"):
            matched_patterns([{"t":7200}],[],10800,
                             "bullish","opposing")

    @patch("v92_four_candle_models_20261113.matched_patterns")
    def test_C_blocks_qualified_opposing_pattern(self,match):
        match.return_value=[pattern()]
        audit=Counter()
        res=new_gate("BTCUSDT","C_OPPOSING_CONTEXT_VETO",[],audit)(
            [{"t":7200}],{"knownUTC":3600,"side":"bullish"},{"t":7200})
        self.assertFalse(res["passed"])
        self.assertEqual(audit["additionalCContextVetoes"],1)
        self.assertTrue(match.call_args.kwargs["strict_sweep"])

    @patch("v92_four_candle_models_20261113.matched_patterns")
    def test_D_requires_confirmation(self,match):
        match.return_value=[]
        audit=Counter()
        res=new_gate("ETHUSDT","D_SAME_DIRECTION_CONFIRM",[],audit)(
            [{"t":7200}],{"knownUTC":3600,"side":"bearish"},{"t":7200})
        self.assertFalse(res["passed"])
        self.assertEqual(audit["DNoConfirmRejected"],1)
        match.return_value=[pattern(direction="bearish")]
        res2=new_gate("ETHUSDT","D_SAME_DIRECTION_CONFIRM",[],audit)(
            [{"t":7200}],{"knownUTC":3600,"side":"bearish"},{"t":7200})
        self.assertTrue(res2["passed"])
        self.assertEqual(audit["DConfirmationAccepted"],1)

    @patch("v92_four_candle_models_20261113.strict_sol_original")
    @patch("v92_four_candle_models_20261113.matched_patterns")
    def test_original_SOL_veto_is_preserved_in_D_and_C(self,match,orig):
        match.return_value=[pattern(direction="bullish")]
        orig.return_value=[pattern()]
        for mode in ("A_BASELINE","C_OPPOSING_CONTEXT_VETO",
                     "D_SAME_DIRECTION_CONFIRM"):
            audit=Counter()
            res=new_gate("SOLUSDT",mode,[],audit)(
                [{"t":7200}],{"knownUTC":3600,"side":"bullish"},
                {"t":7200})
            self.assertFalse(res["passed"])
            self.assertEqual(audit["originalV92SolVetoes"],1)

    def test_missed_winners_and_avoided_losers_paired(self):
        old=[demo_trade(14400,1.2),demo_trade(28800,-1.1)]
        new=[demo_trade(28800,-1.1),demo_trade(43200,0.25)]
        x=paired_deltas(old,new)
        self.assertEqual(x["baselineWinnersRemoved"],1)
        self.assertEqual(x["baselineLosersRemoved"],0)
        self.assertEqual(x["additionalTradesVsBaseline"],1)
        self.assertAlmostEqual(x["additionalNetR9Bps"],.25)
        self.assertEqual(len(x["removedBaselineTradeKeys"]),1)

    def test_baseline_parity_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"PARITY_FAILED"):
            parity_check("2024_2026","SOLUSDT",{
                "trades":999,"totalNetR9BpsPerSide":4.26,
                "totalNetR25BpsPerSideStress":2.41,
            })

    def test_trade_evidence_cost_25bps_greater_than_9bps(self):
        t=demo_trade(14400,1.0)
        x=trade_summary(t)
        self.assertLess(x["netR25Bps"],x["netR9Bps"])
        self.assertEqual(x["stopDistancePercent"],1.)

if __name__=="__main__":
    unittest.main()
