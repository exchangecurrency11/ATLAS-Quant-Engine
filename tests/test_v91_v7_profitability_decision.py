"""Strict V7/V9.1 profitability comparison: no cherry-picked upgrades."""
import copy
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path

from v91_v7_profitability_decision import (
    audit, compare_historical, publication_audit, MIN_CLOSED_FORWARD_PER_VARIANT_PER_ASSET
)

BASE=Path("forward")
HIST=BASE/"v91_retest_full_replay"/"compare.json"
PROS=BASE/"v91_prospective_retest"/"scoreboard.json"
HOUR=3600
T=int(datetime(2026,11,11,20,tzinfo=timezone.utc).timestamp())

class Decisions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.historical=json.loads(HIST.read_text())
        cls.forward=json.loads(PROS.read_text())

    def test_historical_all_trades_accounted_and_net_delta(self):
        r=compare_historical(self.historical)
        self.assertEqual(r["BTCUSDT"]["V7Historical"]["trades"],9)
        self.assertEqual(r["BTCUSDT"]["V91Historical"]["trades"],5)
        self.assertEqual(r["BTCUSDT"]["retainedSameSetups"]["trades"],5)
        self.assertEqual(r["BTCUSDT"]["removedV7Setups"]["trades"],4)
        self.assertEqual(r["BTCUSDT"]["removedV7Winners"],2)
        self.assertAlmostEqual(r["BTCUSDT"]["historicalDeltaR"],0.4374,places=4)
        self.assertEqual(r["SOLUSDT"]["V7Historical"]["trades"],11)
        self.assertEqual(r["SOLUSDT"]["V91Historical"]["trades"],9)
        self.assertEqual(r["SOLUSDT"]["retainedSameSetups"]["trades"],8)
        self.assertEqual(r["SOLUSDT"]["removedV7Setups"]["trades"],3)
        self.assertEqual(r["SOLUSDT"]["newV91Setups"]["trades"],1)
        self.assertEqual(r["SOLUSDT"]["newV91Losers"],1)
        self.assertAlmostEqual(r["SOLUSDT"]["historicalDeltaR"],0.2549,places=4)
        self.assertTrue(r["SOLUSDT"]["historicalSelectionBiasNoOutOfSampleProof"])

    def test_forged_replayed_profit_cannot_pass(self):
        h=copy.deepcopy(self.historical)
        h["results"]["SOLUSDT"]["V91_RETEST_MAX4H"]["totalNetR9bpsSide"]+=1
        with self.assertRaisesRegex(ValueError,"HISTORICAL_TRADE_LEDGER_TOTAL_MISMATCH"):
            compare_historical(h)

    def test_missing_historical_contamination_disclaimer_fails(self):
        h=copy.deepcopy(self.historical)
        h["NOTIndependentOutOfSampleOrProspective"]=False
        with self.assertRaisesRegex(ValueError,"TRAINING_CONTAMINATION"):
            compare_historical(h)

    def test_current_forward_zero_real_executable_cannot_promote(self):
        r=audit(self.historical,self.forward,
                folder=BASE/"v91_prospective_retest"/"hourly")
        self.assertEqual(r["decision"],"KEEP_V91_SILENT_SHADOW_RESEARCH_NO_PROMOTION")
        self.assertFalse(r["comparativeEdgeProven"])
        self.assertFalse(r["prospective"]["minimumSampleScreenPassedNotStatisticalProof"])
        self.assertEqual(r["prospective"]["realTimeExecutableEntryCountProven"],0)
        self.assertFalse(r["notifications"])
        self.assertFalse(r["newOrders"])
        self.assertFalse(r["v7StrategyOrProductionModified"])
        self.assertFalse(r["v91StrategyModified"])

    def test_publication_after_assumed_next_open_never_executable_proof(self):
        from datetime import datetime
        def iso(n):
            return datetime.fromtimestamp(n,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        pending={"retestKnownUTC":T}
        row=lambda p:{"currentPaperState":{"pendingNextOpenPaperEntry":p}}
        obj={"mode":"V91_PROSPECTIVE_4H_RETEST_IMMUTABLE_PAPER_SHADOW",
             "targetClosed1HUTC":iso(T),"capturedAtUTC":iso(T+34*60),
             "assets":{s:{"originalV7":row(pending if s=="SOLUSDT" else None),
                          "max4hRetest":row(pending if s=="SOLUSDT" else None)}
                       for s in ("BTCUSDT","SOLUSDT")}}
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"sample.json"
            f.write_text(json.dumps(obj))
            times=publication_audit(d)
        self.assertEqual(times["SOLUSDT"]["V7_ORIGINAL"]["recordedEntryCandidates"],1)
        self.assertEqual(times["SOLUSDT"]["V91_RETEST_MAX4H"]["assumedNextOpenBeforeResearchPublication"],1)
        self.assertEqual(times["SOLUSDT"]["V91_RETEST_MAX4H"]["publicationLagMinutes"],[34])
        self.assertEqual(times["SOLUSDT"]["V91_RETEST_MAX4H"]["unprovenRealExecution"],1)

    def test_outside_hour_or_future_retest_rejected(self):
        ts=lambda n:datetime.fromtimestamp(n,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        obj={"mode":"V91_PROSPECTIVE_4H_RETEST_IMMUTABLE_PAPER_SHADOW",
             "targetClosed1HUTC":ts(T),"capturedAtUTC":ts(T+HOUR+1),
             "assets":{}}
        with tempfile.TemporaryDirectory() as d:
            Path(d,"example.json").write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"RESEARCH_PUBLICATION_OUTSIDE_CAPTURE_HOUR"):
                publication_audit(d)

    def test_sample_floor_diagnostic_not_automatic_promotion(self):
        self.assertEqual(MIN_CLOSED_FORWARD_PER_VARIANT_PER_ASSET,20)

if __name__=="__main__": unittest.main()
