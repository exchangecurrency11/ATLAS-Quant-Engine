"""V9.2 Stable fail-closed policies: risk, provenance, gaps, parity, replay."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from v92_stable_hardening import (
    BTC_SOL_FIRST, ETH_FIRST, POLICY, ASSETS, seconds, stamp, hour_file,
    risk_gate, exact_events, valid_position, coverage, read_hourly,
    parity_one_hour, audit,
)

def empty_event():
    return {
      "newWatchAtThisClose": [],
      "paperTradeExitsObservedAtThisClose": [],
      "currentPaperState":{"activeBOSWatch":None,
                           "pendingNextOpenPaperEntry":None,
                           "openHypotheticalPosition":None},
      "diagnosticTotalRollingWindowAlerts":0,
      "diagnosticTotalRollingWindowClosedTrades":0,
    }

def example_position():
    entry=100.0; risk=1.0
    return {"side":"bullish","entry":entry,"stop":99.0,"risk":risk,
            "targets":[101.0,102.0,103.0],
            "watchKnownUTC":3000,"retestKnownUTC":6000,
            "entryOpenUTC":6000}

class RiskTests(unittest.TestCase):
    def test_10_usdt_budget_roundtrip_stress_included(self):
        r=risk_gate("SOLUSDT","bullish",100.0,99.0,verified=True,
                    precommitted=True,hour_synchronized=True)
        self.assertTrue(r["allowed"])
        self.assertEqual(r["reservedStopAndCostUSDT"],10.0)
        self.assertAlmostEqual(r["quantityHypothetical"],10.0/1.5,places=8)
        self.assertLess(r["notionalUSDT"],1000)
        self.assertTrue(r["notExecutableOrder"])

    def test_combined_risk_rejects_third_position(self):
        a=risk_gate("BTCUSDT","bearish",100,101,verified=True,
                    precommitted=True,hour_synchronized=True)
        b=risk_gate("ETHUSDT","bullish",100,99,already_reserved=10,
                    already_notional=a["notionalUSDT"],
                    verified=True,precommitted=True,hour_synchronized=True)
        c=risk_gate("SOLUSDT","bullish",100,99,already_reserved=20,
                    already_notional=a["notionalUSDT"]+b["notionalUSDT"],
                    verified=True,precommitted=True,hour_synchronized=True)
        self.assertTrue(a["allowed"] and b["allowed"])
        self.assertFalse(c["allowed"])
        self.assertEqual(c["reason"],"COMBINED_RISK_CAP_EXCEEDED")

    def test_unknown_or_wrong_stop_never_admitted(self):
        for side,entry,stop in (("bullish",100,None),("bullish",100,101),
                                ("bearish",100,99),("bullish",100,100),
                                ("bullish",100,float("nan")),
                                ("bullish",100,float("inf"))):
            with self.subTest(side=side,entry=entry,stop=stop):
                self.assertFalse(risk_gate("SOLUSDT",side,entry,stop,
                                 verified=True,precommitted=True,
                                 hour_synchronized=True)["allowed"])

    def test_fail_closed_on_missing_hour_no_precommit_and_unknown_exposure(self):
        flags=[(False,True,True),(True,False,True),(True,True,False)]
        for verified,precommitted,synchronized in flags:
            self.assertFalse(risk_gate("SOLUSDT","bullish",100,99,
                 verified=verified,precommitted=precommitted,
                 hour_synchronized=synchronized)["allowed"])
        self.assertEqual(risk_gate("SOLUSDT","bullish",100,99,
                         already_reserved=float("nan"),
                         verified=True,precommitted=True,
                         hour_synchronized=True)["reason"],
                         "UNKNOWN_PRIOR_PORTFOLIO_EXPOSURE")

    def test_stop_gap_caution_not_claimed_guarantee(self):
        self.assertTrue(POLICY["noRealOrders"])
        self.assertEqual(POLICY["maxRiskUSDTPerPosition"],10.0)
        self.assertEqual(POLICY["maxCombinedOpenRiskUSDT"],20.0)

    def test_position_stop_tp_and_causality_parity(self):
        x=example_position()
        self.assertTrue(valid_position(x,"SOLUSDT"))
        for mutation in (
            lambda z:z["targets"].__setitem__(1,102.5),
            lambda z:z.__setitem__("stop",100.5),
            lambda z:z.__setitem__("retestKnownUTC",999999),
            lambda z:z.__setitem__("entry",float("nan")),
        ):
            y=copy.deepcopy(x);mutation(y)
            with self.assertRaises(ValueError):
                valid_position(y,"SOLUSDT")

class DataAndParityTests(unittest.TestCase):
    def test_gap_reporting_is_exact_and_does_not_fake_fill(self):
        t=seconds(BTC_SOL_FIRST)
        x={t:{},t+3600:{},t+3*3600:{}}
        z=coverage(x,BTC_SOL_FIRST,t+3*3600)
        self.assertEqual(z["saved"],3)
        self.assertEqual(z["missingHoursUTC"],[stamp(t+2*3600)])
        self.assertEqual(z["consecutiveRecentHours"],1)
        self.assertEqual(z["expected"],4)

    def test_reject_repeated_wrong_named_or_retroactively_captured_hours(self):
        start=seconds(BTC_SOL_FIRST)
        base={"mode":"V92_SELECTED_CANDLE_IMMUTABLE_HOURLY_FORWARD_PAPER_ONLY",
              "targetClosed1HUTC":stamp(start),
              "capturedAtUTC":"2026-11-12T11:30:00Z",
              "noBrokerOrders":True,"noUserNotifications":True,
              "sourceVerifiedSameHour":True,
              "sourceV7AndV91RecomputedExactMatch":True}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/hour_file(start)
            p.write_text(json.dumps(base))
            self.assertEqual(len(read_hourly(d,BTC_SOL_FIRST,base["mode"],"CORE")),1)
            changed=dict(base,capturedAtUTC="2026-11-12T14:00:00Z")
            p.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,"RETROACTIVE"):
                read_hourly(d,BTC_SOL_FIRST,base["mode"],"CORE")
            changed=dict(base,sourceV7AndV91RecomputedExactMatch=False)
            p.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,"PARITY"):
                read_hourly(d,BTC_SOL_FIRST,base["mode"],"CORE")
            p.rename(Path(d)/"wrong.json")
            with self.assertRaisesRegex(ValueError,"STORED_HOUR"):
                read_hourly(d,BTC_SOL_FIRST,base["mode"],"CORE")

    def test_exact_original_v7_v91_compares_all_strategy_fields(self):
        baseline=empty_event()
        self.assertTrue(exact_events(baseline,copy.deepcopy(baseline),"BTC"))
        changed=copy.deepcopy(baseline)
        changed["currentPaperState"]["pendingNextOpenPaperEntry"]={"stop":99.0}
        with self.assertRaisesRegex(ValueError,"REPLAY_MISMATCH"):
            exact_events(baseline,changed,"BTC")

    def test_complete_three_asset_source_parity_with_prior_references(self):
        t=seconds(ETH_FIRST)
        e=empty_event()
        c={
          "assets":{},
          "originalV7_1H4HDailyCandleParity":{},
        }
        for sym in ("BTCUSDT","SOLUSDT"):
            c["assets"][sym]={
              "originalV7":copy.deepcopy(e),
              "originalV91":copy.deepcopy(e),
              "selectedV92":copy.deepcopy(e),
              "currentCloseRetestEvaluation":{
                "baselineRetestPresent":False,"selectedRetestPresent":False,
                "directCurrentFilterVeto":False,
                "downstreamStateDivergence":False},
              "recentPatternObservations":{
                "1H":{"lastClosedCandleUTC":stamp(t)},
                "4H":{"lastClosedCandleUTC":stamp((t//14400)*14400)}}
            }
            c["originalV7_1H4HDailyCandleParity"][sym]={
              k:{"closedCandleUTC":close,"allOHLCVFieldsWithinIntegrityTolerances":True}
              for k,close in (("1hour",stamp(t)),
                              ("4hour",stamp((t//14400)*14400)),
                              ("daily",stamp((t//86400)*86400)))}
        eth={
          "originalV7":copy.deepcopy(e),
          "originalV91":copy.deepcopy(e),
          "selectedV92":copy.deepcopy(e),
          "sourceIntegrity":{
              k:{"closeUTC":close,"verified":True}
              for k,close in (("1hour",stamp(t)),
                              ("4hour",stamp((t//14400)*14400)),
                              ("daily",stamp((t//86400)*86400)))},
          "ethReversalPatternRecognition1H4H":{
            "1H":{"lastCompletedCandleCloseUTC":stamp(t)},
            "4H":{"lastCompletedCandleCloseUTC":stamp((t//14400)*14400)}},
        }
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);v91=root/"v91";v7=root/"v7"
            def add(base,relative,doc):
                p=base/relative/hour_file(t)
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text(json.dumps({"targetClosed1HUTC":stamp(t),**doc}))
            add(v91,"forward/v91_prospective_retest/hourly",
                {"sourceVerifiedSameHour":True,
                 "V7SnapshotAndIndependentRecomputeExactMatch":True,
                 "assets":{s:{"max4hRetest":e} for s in ("BTCUSDT","SOLUSDT")}})
            add(v7,"forward/snapshots",
                {"status":"VERIFIED_PAPER_OBSERVATION",
                 "results":{s+"_PERP.A":{"V7_signal_filter":e}
                            for s in ("BTCUSDT","SOLUSDT")}})
            add(v91,"forward/v91_eth_prospective_retest/hourly",
                {"verifiedSourceAndExactV7Replay":True,"max4hRetest":e})
            add(v7,"forward/eth/snapshots",
                {"status":"VERIFIED_PAPER_OBSERVATION",
                 "results":{"ETHUSDT_PERP.A":{"V7_signal_filter":e}}})
            res=parity_one_hour(t,c,eth,v91,v7)
            self.assertEqual(len(res),3)
            self.assertTrue(all(z["storedBacktestParity"] for z in res))
            # Deliberately change 4H ETH timestamp: cannot claim same 4H.
            eth["sourceIntegrity"]["4hour"]["closeUTC"]=stamp(t-4*3600)
            with self.assertRaisesRegex(ValueError,"ALIGNMENT"):
                parity_one_hour(t,c,eth,v91,v7)

    def test_stale_incomplete_latest_hour_blocks_new_admission(self):
        t=seconds(ETH_FIRST)
        def cc(h):
            return {"targetClosed1HUTC":stamp(h),
                    "assets":{s:{"selectedV92":empty_event()}
                              for s in ("BTCUSDT","SOLUSDT")}}
        def ee(h):
            return {"targetClosed1HUTC":stamp(h),
                    "selectedV92":empty_event()}
        core={t-3600:cc(t-3600),t:cc(t),t+7200:cc(t+7200)}
        eth={t:ee(t),t+7200:ee(t+7200)}
        with patch("v92_stable_hardening.parity_one_hour") as p:
            p.side_effect=lambda hour,*args:[
                {"timeUTC":stamp(hour),"symbol":s} for s in ASSETS]
            x=audit(core,eth,"dummy_v91","dummy_v7")
        self.assertEqual(x["coverage"]["BTC_SOL"]["missingHoursUTC"],
                         [stamp(t+3600)])
        self.assertEqual(x["coverage"]["ETH"]["missingHoursUTC"],
                         [stamp(t+3600)])
        self.assertEqual(x["matchedVerifiedHours"],2)
        self.assertFalse(x["newEntryAdmissionReadiness"])

if __name__=="__main__":
    unittest.main(verbosity=2)
