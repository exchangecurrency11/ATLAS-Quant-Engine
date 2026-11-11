"""V9 V7+ full historical sequential paper strategy profit backtest integrity."""
import unittest
from unittest.mock import patch
from v9_v7_full_profit_backtest import (
 gate_at_bos,original_prediction_map,metrics,cost_adjust,
 VARIANTS,FOUR,HOUR,PERIOD_START,AS_OF)


def predictions(start,side="bullish"):
    row={"direction":side,"probGreen":.8 if side=="bullish" else .2,
         "originalDecisionUTC":start-300,"target4HStartUTC":start,
         "target4HEndUTC":start+FOUR,"fold":"2026-Q3"}
    return {"BTCUSDT":{start:row},"SOLUSDT":{start:row}}


class TradeFirstProfitBacktestTests(unittest.TestCase):
    def test_gate_never_creates_trade_if_v7_original_filter_rejects(self):
        start=PERIOD_START+8*FOUR
        events={"checkedV7QualifyingBOS":0,
            "rejectedNoV9PrestartForecast":0,
            "rejectedDirectionalDisagreement":0,"V9DirectionAlignedV7BOS":0}
        fn=gate_at_bos("SOLUSDT",predictions(start),predictions(start),
                      "V9_94_DIRECTION_GATE",events)
        bars=[{"t":start+HOUR,"c":100,"v":10}]
        with patch("v9_v7_full_profit_backtest.evaluate_bos_quality",
                   return_value={"passed":False,"reasons":["ORIGINAL_V7_FAILED"]}):
            x=fn(bars,{"direction":"bullish"},{})
        self.assertEqual(x["reasons"],["ORIGINAL_V7_FAILED"])
        self.assertEqual(events["checkedV7QualifyingBOS"],0)

    def test_v9_presealed_direction_cannot_make_new_v7_bos(self):
        start=PERIOD_START+8*FOUR
        events={"checkedV7QualifyingBOS":0,
            "rejectedNoV9PrestartForecast":0,
            "rejectedDirectionalDisagreement":0,"V9DirectionAlignedV7BOS":0}
        fn=gate_at_bos("SOLUSDT",predictions(start),predictions(start),
                      "V9_94_DIRECTION_GATE",events)
        bar=[{"t":start+HOUR,"c":100,"v":10}]
        with patch("v9_v7_full_profit_backtest.evaluate_bos_quality",
                   return_value={"passed":True,"reasons":[]}):
            accept=fn(bar,{"direction":"bullish"},{})
            refuse=fn(bar,{"direction":"bearish"},{})
        self.assertTrue(accept["passed"])
        self.assertFalse(refuse["passed"])
        self.assertEqual(events["checkedV7QualifyingBOS"],2)
        self.assertEqual(events["V9DirectionAlignedV7BOS"],1)
        self.assertEqual(events["rejectedDirectionalDisagreement"],1)

    def test_missing_record_never_fabricated_as_green_or_red(self):
        start=PERIOD_START+8*FOUR
        events={"checkedV7QualifyingBOS":0,
            "rejectedNoV9PrestartForecast":0,
            "rejectedDirectionalDisagreement":0,"V9DirectionAlignedV7BOS":0}
        fn=gate_at_bos("SOLUSDT",{"SOLUSDT":{}},{"SOLUSDT":{}},
                      "V9_94_DIRECTION_GATE",events)
        with patch("v9_v7_full_profit_backtest.evaluate_bos_quality",
                   return_value={"passed":True,"reasons":[]}):
            x=fn([{"t":start+HOUR}],{"direction":"bullish"},{})
        self.assertFalse(x["passed"])
        self.assertEqual(events["rejectedNoV9PrestartForecast"],1)

    def test_prediction_requires_strict_before_future_4h_start(self):
        start=PERIOD_START+8*FOUR
        j={"targetStartUTC":"2024-10-02T08:00:00Z",
           "decisionUTC":"2024-10-02T08:01:00Z",
           "modelPgreen":0.8,"fold":"2024-H2"}
        with self.assertRaisesRegex(ValueError,"NOT_PREDICTED_PRE_TARGET"):
            original_prediction_map({"BTCUSDT":[j],"SOLUSDT":[]})

    def test_cost_stress_25bps_worse_than_9bps_for_identical_paper_trade(self):
        t={"entry":100.,"risk":2.,"netRIllustrative":.7}
        self.assertAlmostEqual(cost_adjust(t,9),.7)
        self.assertAlmostEqual(cost_adjust(t,25),.54)

    def test_full_sequential_paper_trade_metrics_not_closed_color(self):
        t={"side":"bullish","watchKnownUTC":PERIOD_START+HOUR,
           "retestKnownUTC":PERIOD_START+2*HOUR,
           "entryOpenUTC":PERIOD_START+3*HOUR,
           "exitKnownUTC":PERIOD_START+4*HOUR,
           "entry":100.,"risk":2.,"netRIllustrative":.7}
        report={"status":"PAPER_BACKTEST_NOT_LIVE","trades":[t],
                "alertsCount":1,"qualityGateRejectedBOS":0,
                "qualityGateRejectedRetest":0,"retestExpiredCount":0,
                "riskRuleRejected":0,"unresolvedPositionExcluded":False}
        out=metrics(report)
        self.assertEqual(out["V7paperClosedTrades"],1)
        self.assertAlmostEqual(out["averageNetR9BpsPerSide"],.7)
        self.assertAlmostEqual(out["averageNetR25BpsPerSideStress"],.54)
        self.assertTrue(out["tradeRetestWasObservedBeforeEntry"])

if __name__=="__main__":
    unittest.main()
