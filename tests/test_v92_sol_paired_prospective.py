"""Paired prospective SOL paper control/filter tests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from v92_sol_paired_prospective import (
    ARMS, build, score, trade_evidence, key_of
)
from v92_prospective_selected import FIRST, MODE, path_at, iso


def pending():
    return {"side":"bullish","watchKnownUTC":FIRST-3600,
            "retestKnownUTC":FIRST,"stop":99.0}


def trade(exit_close):
    return {"watchKnownUTC":FIRST-3600,"retestKnownUTC":FIRST,
            "entryOpenUTC":FIRST,"exitKnownUTC":exit_close,
            "entry":100.0,"risk":1.0,"stop":99.0,"side":"bullish",
            "exitReason":"TP1_COMPLETE","netRIllustrative":1.0}


def state(p=None, exits=None):
    return {"currentPaperState":{"pendingNextOpenPaperEntry":p},
            "paperTradeExitsObservedAtThisClose":exits or []}


def snapshot(t, *, baseline_pending=None, selected_pending=None,
             baseline_exits=None, selected_exits=None, evaluation=None):
    return {
      "mode":MODE,"targetClosed1HUTC":iso(t),
      "capturedAtUTC":iso(t+900),
      "sourceV7AndV91RecomputedExactMatch":True,
      "noBrokerOrders":True,
      "assets":{"SOLUSDT":{
        "originalV91":state(baseline_pending,baseline_exits),
        "selectedV92":state(selected_pending,selected_exits),
        "currentCloseRetestEvaluation":evaluation or {},
      }},
    }


class V92SOLPairedProspectiveTests(unittest.TestCase):
    def test_score_reports_net_and_stress_metrics(self):
        result=score([
          {"exitUTC":"a","entryUTC":"a","netR9Bps":1.0,"netR25Bps":.68},
          {"exitUTC":"b","entryUTC":"b","netR9Bps":-0.5,"netR25Bps":-.82},
        ])
        self.assertEqual(result["trades"],2)
        self.assertEqual(result["wins"],1)
        self.assertEqual(result["netR"],.5)
        self.assertEqual(result["stressNetR"],-.14)
        self.assertEqual(result["maxDrawdownR"],.5)

    def test_trade_requires_same_arm_precommitted_retest(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            snap=snapshot(FIRST,baseline_pending=pending(),
                          selected_pending=None)
            path=path_at(folder,FIRST)
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(snap))
            with patch("v92_sol_paired_prospective.verified_first_commit",
                       return_value=FIRST+905):
                self.assertTrue(trade_evidence(folder,trade(FIRST+3600),
                                               "originalV91").startswith("PRECOMMITTED"))
                self.assertEqual(
                  trade_evidence(folder,trade(FIRST+3600),"selectedV92"),
                  "NO_PRECOMMITTED_PENDING_RETEST_IN_selectedV92")

    def test_build_compares_control_to_filtered_arm_and_counts_direct_veto(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            retest=snapshot(
              FIRST,baseline_pending=pending(),selected_pending=None,
              evaluation={"candidateRetestAtThisClose":True,
                          "directCurrentFilterVeto":True,
                          "currentPatternWarnings":[{"name":"BULLISH_STAR","tf":"1H"}]})
            exit_=snapshot(
              FIRST+3600,baseline_exits=[trade(FIRST+3600)],
              selected_exits=[])
            for obj in (retest,exit_):
                p=path_at(folder,int(obj["targetClosed1HUTC"].replace("Z","+00:00").replace("T"," ").replace("-","-",1)[:0] or FIRST))
            # Use exact timestamp-derived filenames for immutable hourly snapshots.
            path_at(folder,FIRST).write_text(json.dumps(retest))
            path_at(folder,FIRST+3600).write_text(json.dumps(exit_))
            def commit_time(path):
                obj=json.loads(Path(path).read_text())
                return int(obj["targetClosed1HUTC"].replace("Z","+00:00")[:19].replace("T"," ").replace("-","-",1) and
                           (FIRST if obj["targetClosed1HUTC"]==iso(FIRST) else FIRST+3600))+905
            with patch("v92_sol_paired_prospective.verified_first_commit",
                       side_effect=commit_time):
                result=build(folder)
            self.assertEqual(result["arms"]["V91_UNFILTERED_CONTROL"]["trades"],1)
            self.assertEqual(result["arms"]["V92_STAR_HARAMI_SWEEP_FILTER"]["trades"],0)
            self.assertEqual(result["directRetestAudit"]["directFilterVetoes"],1)
            self.assertEqual(result["directRetestAudit"]["warningCounts"],
                             {"BULLISH_STAR_1H":1})
            self.assertEqual(result["researchDecision"],
                             "INSUFFICIENT_PROSPECTIVE_SAMPLE")
            self.assertTrue(result["noBrokerOrders"])

    def test_uncommitted_or_after_exit_retest_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            path=path_at(folder,FIRST)
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(snapshot(FIRST,baseline_pending=pending())))
            with patch("v92_sol_paired_prospective.verified_first_commit",
                       return_value=FIRST+3601):
                self.assertEqual(
                  trade_evidence(folder,trade(FIRST+3600),"originalV91"),
                  "RETEST_NOT_GIT_SEALED_BEFORE_EXIT")


if __name__=="__main__":
    unittest.main()
