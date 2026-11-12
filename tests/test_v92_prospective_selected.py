"""V9.2 prospective third independent book: never backfill or infer fills."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from v92_prospective_selected import (
 FIRST,USER_REQUEST,MODE,BOOK,INITIAL,RISK,
 verify_source,account,load_all,evidence_for_entry,state_of,md,
 current_close_retest_evaluation
)
from v7_forward_observer import iso

def mk_state(pending=None,position=None):
    return {
       "newWatchAtThisClose":[],
       "paperTradeExitsObservedAtThisClose":[],
       "currentPaperState":{
          "pendingNextOpenPaperEntry":pending,
          "openHypotheticalPosition":position,
          "activeBOSWatch":None}}

def hour(t,*,trade=None):
    return {
       "mode":MODE,"targetClosed1HUTC":iso(t),
       "capturedAtUTC":iso(t+1800),"noBrokerOrders":True,
       "sourceV7AndV91RecomputedExactMatch":True,
       "assets":{
           x:{"selectedV92":{
                **mk_state(),
                "paperTradeExitsObservedAtThisClose":
                   [trade] if trade is not None and x=="SOLUSDT" else [],
                },
              "recentPatternObservations":{}}
           for x in ("BTCUSDT","SOLUSDT")}
    }

def reference(t=FIRST):
    return {"mode":"V91_PROSPECTIVE_4H_RETEST_IMMUTABLE_PAPER_SHADOW",
            "targetClosed1HUTC":iso(t),
            "capturedAtUTC":iso(t+1450),
            "sourceVerifiedSameHour":True,
            "V7SnapshotAndIndependentRecomputeExactMatch":True,
            "priceAndVolumeValidatedAgainstOriginalV7For1H4HDaily":True,
            "noBrokerOrders":True,"noNotifications":True,
            "assets":{"BTCUSDT":{},"SOLUSDT":{}}}

def original(t=FIRST):
    return {"status":"VERIFIED_PAPER_OBSERVATION",
            "brokerOrders":False,"targetClosed1HUTC":iso(t),
            "observedAtUTC":iso(t+1200),
            "results":{"BTCUSDT_PERP.A":{},"SOLUSDT_PERP.A":{}}}

class V92ForwardTests(unittest.TestCase):
    def test_current_source_window_allows_last_minute_but_never_rollover(self):
        self.assertTrue(verify_source(reference(),original(),target=FIRST,now=FIRST+3599))
        with self.assertRaisesRegex(ValueError,"OUTSIDE_CURRENT"):
            verify_source(reference(),original(),target=FIRST,now=FIRST+3600)

    def test_current_sol_opposing_star_sweep_is_logged_as_direct_veto(self):
        base=1794009600
        bars=[{"t":base+i*3600,"o":100.,"h":102.,"l":98.,
               "c":100.,"v":1000.} for i in range(27)]
        bars.extend([
          {"t":base+27*3600,"o":99.,"h":100.,"l":94.,"c":95.,"v":1000.},
          {"t":base+28*3600,"o":95.,"h":96.,"l":88.,"c":94.8,"v":1000.},
          {"t":base+29*3600,"o":95.,"h":102.,"l":94.,"c":101.,"v":1000.},
        ])
        target=bars[-1]["t"]+3600
        pending={"side":"bearish","watchKnownUTC":target-7200,
                 "retestKnownUTC":target,"stop":103.}
        result=current_close_retest_evaluation(
          "SOLUSDT",bars,[],target,
          {"pendingNextOpenPaperEntry":pending},
          {"pendingNextOpenPaperEntry":None})
        self.assertTrue(result["candidateRetestAtThisClose"])
        self.assertTrue(result["directCurrentFilterVeto"])
        self.assertEqual(result["currentPatternWarnings"][0]["name"],
                         "MORNING_STAR")
        self.assertTrue(result["currentPatternWarnings"][0]
                        ["prior20LiquiditySweepAndReentry"])

    def test_current_btc_star_is_observation_only_not_a_veto(self):
        base=1794009600
        bars=[{"t":base+i*3600,"o":100.,"h":102.,"l":98.,
               "c":100.,"v":1000.} for i in range(27)]
        bars.extend([
          {"t":base+27*3600,"o":99.,"h":100.,"l":94.,"c":95.,"v":1000.},
          {"t":base+28*3600,"o":95.,"h":96.,"l":88.,"c":94.8,"v":1000.},
          {"t":base+29*3600,"o":95.,"h":102.,"l":94.,"c":101.,"v":1000.},
        ])
        target=bars[-1]["t"]+3600
        pending={"side":"bearish","watchKnownUTC":target-7200,
                 "retestKnownUTC":target,"stop":103.}
        result=current_close_retest_evaluation(
          "BTCUSDT",bars,[],target,
          {"pendingNextOpenPaperEntry":pending},
          {"pendingNextOpenPaperEntry":dict(pending)})
        self.assertTrue(result["candidateRetestAtThisClose"])
        self.assertFalse(result["directCurrentFilterVeto"])
        self.assertTrue(result["selectedRetestMatchesBaseline"])

    def test_no_baseline_retest_means_no_current_veto_count(self):
        target=1794009600+30*3600
        result=current_close_retest_evaluation(
          "SOLUSDT",[],[],target,
          {"pendingNextOpenPaperEntry":None},
          {"pendingNextOpenPaperEntry":None})
        self.assertFalse(result["candidateRetestAtThisClose"])
        self.assertFalse(result["directCurrentFilterVeto"])

    def test_request_and_first_eligible_only_later_hour(self):
        self.assertLess(USER_REQUEST,FIRST)
        self.assertEqual(FIRST%3600,0)
        self.assertEqual(INITIAL,1000)
        self.assertEqual(RISK,100)

    def test_original_v91_and_v7_seal_only_current(self):
        self.assertTrue(verify_source(reference(),original(),
                     target=FIRST,now=FIRST+1800))
        with self.assertRaisesRegex(ValueError,"OUTSIDE_CURRENT"):
            verify_source(reference(),original(),
                     target=FIRST,now=FIRST+4000)
        with self.assertRaisesRegex(ValueError,"OUTSIDE_CURRENT"):
            verify_source(reference(),original(),
                     target=FIRST,now=FIRST+500)

    def test_source_parity_missing_cannot_paper_capture(self):
        for key in ("sourceVerifiedSameHour",
                    "V7SnapshotAndIndependentRecomputeExactMatch",
                    "priceAndVolumeValidatedAgainstOriginalV7For1H4HDaily"):
            ref=reference();ref[key]=False
            with self.assertRaisesRegex(ValueError,"SEALED_V91_SOURCE"):
                verify_source(ref,original(),target=FIRST,now=FIRST+1800)
        ref=reference();ref["noBrokerOrders"]=False
        with self.assertRaisesRegex(ValueError,"SEALED_V91_SOURCE"):
            verify_source(ref,original(),target=FIRST,now=FIRST+1800)

    def test_time_mismatched_v7_forbidden(self):
        orig=original(FIRST+3600)
        with self.assertRaisesRegex(ValueError,"ORIGINAL_V7_SOURCE"):
            verify_source(reference(),orig,target=FIRST,now=FIRST+1800)

    def test_unproven_external_git_commit_rejected(self):
        with self.assertRaisesRegex(ValueError,"NOT_SEALED"):
            verify_source(reference(),original(),
               target=FIRST,now=FIRST+1800,
               v91_source_file="absent.json",v91_repo=".")

    def test_empty_book_has_no_retrospective_profit(self):
        book=account({},Path("does_not_exist"))
        self.assertEqual(book["mode"],BOOK)
        self.assertEqual(book["virtualEquityUSDT"],1000)
        self.assertEqual(book["virtualRealizedPnLUSDT"],0)
        self.assertEqual(book["closedEligiblePaperTrades"],0)
        self.assertIsNone(book["winRatePct"])
        self.assertTrue(book["historicalPlus836USDNotTransferredHere"])
        self.assertTrue(book["noBrokerOrders"])
        self.assertTrue(book["V7V91CurrentPaperAccountsUnchanged"])
        self.assertIn("GERÇEK EMİR",md(book))

    def test_no_backfill_and_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            saved=hour(FIRST)
            (folder/(iso(FIRST).replace(":","-")+".json")).write_text(
              json.dumps(saved))
            # The stored filename must exactly match the declared source hour.
            with self.assertRaisesRegex(ValueError,"UNVERIFIED_SNAPSHOT"):
                load_all(folder)
            (folder/(iso(FIRST).replace(":","-")+".json")).unlink()
            correct=folder/("2026-11-12T11-00Z.json")
            correct.write_text(json.dumps(saved))
            got=load_all(folder)
            self.assertEqual(len(got),1)
            with self.assertRaisesRegex(ValueError,"OVERWRITE"):
                load_all(folder,current=saved)

    def test_missing_precommitted_retest_is_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            book=account({FIRST:hour(FIRST)},Path(tmp))
            self.assertEqual(book["closedEligiblePaperTrades"],0)
            trade={"watchKnownUTC":FIRST-3600,
                   "retestKnownUTC":FIRST,
                   "entryOpenUTC":FIRST,
                   "exitKnownUTC":FIRST+3600,
                   "entry":100,"risk":1,"stop":99,
                   "side":"bullish","netRIllustrative":1}
            x=hour(FIRST+3600,trade=trade)
            book=account({FIRST:hour(FIRST),FIRST+3600:x},Path(tmp))
            self.assertEqual(book["closedEligiblePaperTrades"],0)
            self.assertEqual(book["excludedUnsealedOrUnprovenExits"]["SOLUSDT"][0]["reason"],
                             "NO_PREVIOUSLY_CAPTURED_RETEST_HOUR")

    def test_future_exit_cannot_be_assigned_before_actual_close(self):
        bad={"watchKnownUTC":FIRST-3600,
              "retestKnownUTC":FIRST,
              "entryOpenUTC":FIRST,
              "exitKnownUTC":FIRST+7200,
              "entry":100,"risk":1,"stop":99,
              "side":"bullish","netRIllustrative":1}
        with tempfile.TemporaryDirectory() as tmp:
            snap=hour(FIRST+3600,trade=bad)
            with self.assertRaisesRegex(ValueError,"V91_FUTURE_OR_STALE_EXIT"):
                account({FIRST+3600:snap},Path(tmp))

    def test_precommitted_one_r_maps_to_one_hundred_dollars(self):
        trade={"watchKnownUTC":FIRST-3600,
               "retestKnownUTC":FIRST,
               "entryOpenUTC":FIRST,
               "exitKnownUTC":FIRST+3600,
               "entry":100,"risk":1,"stop":99,
               "side":"bullish","exitReason":"TP3_COMPLETE",
               "netRIllustrative":1}
        with tempfile.TemporaryDirectory() as tmp:
            with patch("v92_prospective_selected.evidence_for_entry",
                       return_value="PRECOMMITTED_V92_RETEST_BEFORE_PAPER_EXIT"):
                snap1=hour(FIRST)
                snap2=hour(FIRST+3600,trade=trade)
                book=account({FIRST:snap1,FIRST+3600:snap2},Path(tmp))
            self.assertEqual(book["virtualEquityUSDT"],1100)
            self.assertEqual(book["closedEligiblePaperTrades"],1)
            self.assertEqual(book["wins"],1)
            self.assertEqual(book["winRatePct"],100)
            self.assertEqual(book["targetVirtualRiskUSDTPerTrade"],100)
            self.assertTrue(book["noActualExchangeExecutionOrFill"])

    def test_never_add_exits_that_precede_first_hour(self):
        trade={"watchKnownUTC":FIRST-2*3600,
               "retestKnownUTC":FIRST-3600,
               "entryOpenUTC":FIRST-3600,
               "exitKnownUTC":FIRST+3600,
               "entry":100,"risk":1,"stop":99,
               "side":"bullish","netRIllustrative":1}
        with tempfile.TemporaryDirectory() as tmp:
            book=account(
                {FIRST+3600:hour(FIRST+3600,trade=trade)},Path(tmp))
            self.assertEqual(book["closedEligiblePaperTrades"],0)
            self.assertEqual(book["virtualEquityUSDT"],1000)
            self.assertEqual(book["excludedUnsealedOrUnprovenExits"]["SOLUSDT"][0]["reason"],
                             "BEFORE_V92_FORWARD_START")

if __name__=="__main__":
    unittest.main()
