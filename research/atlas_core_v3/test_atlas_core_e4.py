"""E4 trade-fill and shared-risk negative controls; NO INTERNET in unit tests."""
from __future__ import annotations

from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from math import isclose

from research.atlas_core_v3 import atlas_core_e4 as m

def trade(side="bullish",entry=100.,stop=95.,start=0,
          exit_ts=3600,exit_reason="STOP_FIRST_OR_AFTER_TP",
          gross=-1.):
    risk=abs(entry-stop)
    sign=1 if side=="bullish" else -1
    targets=[entry+sign*risk*n for n in (1,2,3)]
    return {
        "side":side,"entry":entry,"stop":stop,"risk":risk,
        "targets":targets,"entryOpenUTC":start,
        "exitKnownUTC":exit_ts,"exitReason":exit_reason,
        "realizedR":gross,
        "netRIllustrative":gross-2*9/10000*entry/risk,
    }

def candle(ts,op=100.,hi=101.,lo=99.,close=100.):
    return {"t":ts,"o":op,"h":hi,"l":lo,"c":close,"v":100.}

def event(symbol,entry,end,netR=1.,price=100.,risk=1.):
    return {
        "symbol":symbol,"entryEpoch":entry,"exitEpoch":end,
        "netR":netR,"entry":price,"risk":risk,
    }

class TestE4ExecutionModel(TestCase):

    def test_pinned_e3_unmodified(self):
        self.assertEqual(len(m.ensure_sealed_sources()[2]),10)

    def test_legacy_zero_cost_stop_first_when_tp_same_bar(self):
        t=trade()
        path=[candle(0,100,116,94,99)]
        r=m.reference_ideal_parity(t,path)
        self.assertEqual(r["grossR"],-1.)
        self.assertEqual(r["gapStopCount"],0)
        self.assertEqual(r["fills"][0]["type"],"STOP_FIRST")

    def test_long_stop_gap_is_worse_than_stop_and_legacy(self):
        t=trade(exit_ts=7200)
        path=[candle(0),candle(3600,90,92,89,90)]
        ideal=m.simulate_trade(t,path,m.IDEAL)
        gap=m.simulate_trade(t,path,m.Scenario("gap",0,0,0,0))
        self.assertAlmostEqual(ideal["grossR"],-1)
        self.assertAlmostEqual(gap["grossR"],-2)
        self.assertEqual(gap["gapStopCount"],1)
        self.assertAlmostEqual(gap["gapStopPenaltyR"],1.)

    def test_short_stop_gap_is_worse_than_stop(self):
        t=trade(side="bearish",stop=105.,exit_ts=7200)
        path=[candle(0),candle(3600,110,111,109,110)]
        x=m.simulate_trade(t,path,m.Scenario("gap",0,0,0,0))
        self.assertAlmostEqual(x["grossR"],-2)
        self.assertEqual(x["gapStopCount"],1)

    def test_target_first_then_later_stop_preserves_partial_sizing(self):
        t=trade(exit_ts=7200,gross=-1/3)
        path=[candle(0,100,106,99,105),candle(3600,100,102,94,96)]
        x=m.reference_ideal_parity(t,path)
        self.assertAlmostEqual(x["grossR"],-1/3,places=7)
        self.assertEqual([i["type"] for i in x["fills"]],["TP1","STOP_FIRST"])
        self.assertAlmostEqual(sum(i["positionFractionClosed"] for i in x["fills"]),1)

    def test_full_tp1_tp2_tp3_one_bar_exact_2R(self):
        t=trade(exit_reason="TP3_COMPLETE",gross=2)
        path=[candle(0,100,116,99,114)]
        x=m.reference_ideal_parity(t,path)
        self.assertAlmostEqual(x["grossR"],2)
        self.assertEqual([i["type"] for i in x["fills"]],["TP1","TP2","TP3"])

    def test_24_hour_time_exit_on_close(self):
        t=trade(exit_ts=24*3600,exit_reason="TIME_EXIT_AT_CLOSE",gross=.2)
        path=[candle(i*3600,100,102,98,(101 if i==23 else 100))
              for i in range(24)]
        x=m.reference_ideal_parity(t,path)
        self.assertAlmostEqual(x["grossR"],.2)
        self.assertEqual(x["fills"][-1]["type"],"24H_CLOSE")

    def test_adverse_funding_on_fixed_eight_hour_boundaries(self):
        t=trade(exit_ts=9*3600)
        path=[candle(i*3600) for i in range(8)]
        path.append(candle(8*3600,100,101,94,95))
        x=m.simulate_trade(t,path,m.Scenario("funding",0,0,0,1))
        self.assertAlmostEqual(x["adverseFundingCashPerUnit"],.02,places=8)
        self.assertAlmostEqual(x["netR"],-1.004,places=6)
        self.assertEqual(m.funding_events_at_open(0,0,3600),True)
        self.assertEqual(m.funding_events_at_open(8*3600,0,8*3600),False)

    def test_positive_commissions_and_slippage_reduce_netR(self):
        t=trade(exit_reason="TP3_COMPLETE",gross=2)
        path=[candle(0,100,116,99,114)]
        results=[m.simulate_trade(t,path,s) for s in m.SCENARIOS]
        self.assertGreater(results[0]["netR"],results[1]["netR"])
        self.assertGreater(results[1]["netR"],results[2]["netR"])
        self.assertTrue(all(r["commissionCashPerUnit"]>0 for r in results))
        self.assertTrue(all(r["grossR"]<=2 for r in results))

    def test_negative_scenario_cost_rejected(self):
        with self.assertRaisesRegex(ValueError,"E4_NEGATIVE"):
            m.Scenario("invalid",-1,0,0,0)

    def test_nan_scenario_cost_rejected(self):
        with self.assertRaisesRegex(ValueError,"E4_NEGATIVE"):
            m.Scenario("invalid",float("nan"),0,0,0)

    def test_more_than_24_hour_trade_refused(self):
        t=trade(exit_ts=25*3600)
        with self.assertRaisesRegex(ValueError,"E4_TRADE_TIME_INVALID"):
            m.simulate_trade(t,[candle(i*3600) for i in range(25)],m.IDEAL)

    def test_candle_gap_detected_fail_closed(self):
        t=trade(exit_ts=7200)
        with self.assertRaisesRegex(ValueError,"E4_GAPPED"):
            m.simulate_trade(t,[candle(0),candle(7200)],m.IDEAL)

    def test_bad_ohlc_rejected(self):
        t=trade()
        with self.assertRaisesRegex(ValueError,"E4_MALFORMED_CANDLE"):
            m.simulate_trade(t,[candle(0,100,99,101,100)],m.IDEAL)

    def test_exit_reason_drift_cannot_pass(self):
        t=trade(exit_reason="TP3_COMPLETE",gross=2)
        with self.assertRaisesRegex(ValueError,"E4_ENGINE_EXIT"):
            m.simulate_trade(t,[candle(0,100,101,94,95)],m.IDEAL)

    def test_stop_and_target_tamper_detected(self):
        t=trade()
        t["targets"][1]+=1
        with self.assertRaisesRegex(ValueError,"E4_INCONSISTENT_THREE_TARGETS"):
            m.simulate_trade(t,[candle(0,100,101,94,95)],m.IDEAL)

    def test_no_fake_execution_observation(self):
        x=m.simulate_trade(trade(),[candle(0,100,101,94,95)],m.SCENARIOS[0])
        self.assertFalse(x["wasObservedRealFill"])
        self.assertFalse(x["observedFundingRatesAvailable"])

class TestE4Portfolio(TestCase):

    def test_two_cross_asset_positions_count_as_shared_risk(self):
        items=[
            event("BTCUSDT",3600,10800,1,100,1),
            event("SOLUSDT",7200,14400,-1,100,1),
        ]
        out=m.position_budget_portfolio(items,"unit-test")
        self.assertEqual(out["tradesAccepted"],2)
        self.assertEqual(out["tradesRejectedByBudget"],0)
        self.assertEqual(out["maxConcurrentAcceptedPositions"],2)
        self.assertAlmostEqual(out["maxStopRiskFractionVsRealizedEquity"],.01)
        self.assertAlmostEqual(out["endingRealizedCashUSDT"],10000)
        self.assertTrue(out["maxRealizedOnlyDrawdownPct"]>0)

    def test_exit_before_entry_equal_timestamp_releases_budget(self):
        items=[
            event("BTCUSDT",3600,7200,-1,100,1),
            event("BTCUSDT",7200,10800,1,100,1),
        ]
        out=m.position_budget_portfolio(items,"unit-test")
        self.assertEqual(out["tradesAccepted"],2)
        self.assertEqual(out["maxConcurrentAcceptedPositions"],1)

    def test_one_trade_too_levered_is_rejected(self):
        out=m.position_budget_portfolio([
            event("BTCUSDT",3600,7200,1,100,.01)
        ],"unit-test")
        self.assertEqual(out["tradesAccepted"],0)
        self.assertEqual(out["tradesRejectedByBudget"],1)
        self.assertEqual(out["endingRealizedCashUSDT"],10000)

    def test_trade_cannot_exceed_gross_notional_limit(self):
        out=m.position_budget_portfolio([
            event("BTCUSDT",3600,7200,.5,100,1),
            event("SOLUSDT",4200,7800,-1,100,1),
        ],"unit-test")
        self.assertLessEqual(out["maxGrossNotionalToRealizedEquity"],1.5+1e-6)

    def test_loss_beyond_one_r_visible_not_silently_capped(self):
        out=m.position_budget_portfolio([
            event("BTCUSDT",3600,7200,-2.5,100,1),
        ],"unit-test")
        self.assertEqual(out["acceptedTradesBelowMinusOneR"],1)
        self.assertLess(out["endingRealizedCashUSDT"],10000.)

    def test_duplicate_asset_time_rejected(self):
        rows=[event("BTCUSDT",3600,7200),event("BTCUSDT",3600,10800)]
        with self.assertRaisesRegex(ValueError,"E4_DUPLICATE_ASSET_ENTRY"):
            m.position_budget_portfolio(rows,"unit-test")

    def test_overlapping_same_asset_positions_rejected(self):
        rows=[event("BTCUSDT",3600,10800),event("BTCUSDT",7200,14400)]
        with self.assertRaisesRegex(ValueError,"E4_SAME_ASSET_OVERLAPPING"):
            m.position_budget_portfolio(rows,"unit-test")

    def test_reject_invalid_total_risk_budget(self):
        with self.assertRaisesRegex(ValueError,"E4_INVALID_PORTFOLIO"):
            m.position_budget_portfolio([],"unit-test",total_risk_fraction=0)

    def test_no_real_broker_account_claimed(self):
        out=m.position_budget_portfolio([event("BTCUSDT",3600,7200)],"unit-test")
        self.assertTrue(out["notActualExchangeAccount"])
        self.assertFalse(out["equityIncludesOpenPositionMarkToMarket"])
        self.assertFalse(out["liquidationAndCrossMarginModeled"])

    def test_risk_capped_when_both_coin_slots_are_open(self):
        rows=[
            event("BTCUSDT",3600,10800,1,100,1),
            event("SOLUSDT",7200,14400,1,100,1),
            event("ETHUSDT",8000,15000,1,100,1),
        ]
        r=m.position_budget_portfolio(rows,"unit-test")
        self.assertEqual(r["tradesAccepted"],2)
        self.assertEqual(r["tradesRejectedByBudget"],1)

    def test_e4_worker_count_refuses_download_when_invalid(self):
        with self.assertRaisesRegex(ValueError,"E4_WORKER_LIMIT"):
            m.model_all(7)

if __name__=="__main__":
    import unittest
    unittest.main()
