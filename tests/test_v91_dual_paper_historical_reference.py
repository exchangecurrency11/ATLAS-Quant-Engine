"""Historical BTC/SOL full archive virtual 1000 USDT ledger safety checks."""
import copy
import json
import unittest
from pathlib import Path

from v91_dual_paper_historical_reference import MODE, history_paper_book

ROOT=Path(__file__).resolve().parents[1]
REPLAY=ROOT/"forward/v91_retest_full_replay/compare.json"
CONF=ROOT/"forward/v91_dual_paper_accounts/config.json"

class HistoricalVirtualAccountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=json.loads(CONF.read_text())
        cls.replay=json.loads(REPLAY.read_text())

    def test_all_archived_sequential_trades_reconcile_with_original_replay(self):
        result=history_paper_book(self.config,self.replay)
        self.assertEqual(result["mode"],MODE)
        self.assertEqual(result["sourceArchiveStartUTC"],"2024-10-01T00:00:00Z")
        self.assertEqual(result["sourceArchiveEndExclusiveUTC"],"2026-10-01T00:00:00Z")
        v7=result["accounts"]["V7_ORIGINAL"]
        v91=result["accounts"]["V91_RETEST_MAX4H"]
        self.assertEqual(v7["totalClosedHistoricalReplayedTrades"],20)
        self.assertEqual(v91["totalClosedHistoricalReplayedTrades"],14)
        self.assertEqual(v7["wins"],11)
        self.assertEqual(v91["wins"],8)
        self.assertAlmostEqual(v7["netR9Bps"],6.5246,places=3)
        self.assertAlmostEqual(v91["netR9Bps"],7.2169,places=3)
        self.assertAlmostEqual(v7["virtualEndingBalanceUSDT"],1652.46,delta=.04)
        self.assertAlmostEqual(v91["virtualEndingBalanceUSDT"],1721.69,delta=.04)
        self.assertEqual(v7["initialVirtualUSDT"],1000)
        self.assertEqual(v91["fixedTargetRiskPerTradeUSDT"],100)
        self.assertEqual(v91["riskPctOfInitialBalance"],10)
        self.assertTrue(result["noBrokerOrders"])
        self.assertTrue(result["resultsNOTIndependentlyValidatedProspectively"])
        self.assertTrue(result["notForwardAccountBalances"])
        self.assertTrue(result["ETHHistoricalTwoYearArchiveNotAvailableForEqualComparison"])
        for account in (v7,v91):
            self.assertEqual(len(account["replayedClosedTrades"]),
                             len(account["virtualEquityCurveAtExits"]))
            for trade in account["replayedClosedTrades"]:
                self.assertTrue(trade["notAnExecutedTrade"])
                self.assertGreater(trade["illustrativeQuantityFor100USDTStopRisk"],0)
                self.assertGreater(trade["notionalRequiredUSDTNoLeverageOrMarginAssumed"],0)

    def test_reject_unverified_or_retroactively_selected_archive(self):
        replay=copy.deepcopy(self.replay)
        replay["historicalPeriodPreviouslyInspected"]=False
        with self.assertRaisesRegex(ValueError,"NOT_VERIFIED"):
            history_paper_book(self.config,replay)
        replay=copy.deepcopy(self.replay)
        replay["originalV7BaselineVerifiedAgainstPublishedQualityBacktest"]=False
        with self.assertRaisesRegex(ValueError,"NOT_VERIFIED"):
            history_paper_book(self.config,replay)

    def test_reject_falsified_wins_and_pnl(self):
        replay=copy.deepcopy(self.replay)
        row=next(x for x in replay["tradesAudit"] if x["variant"]=="V7_ORIGINAL")
        row["netR9bps"]+=1
        with self.assertRaisesRegex(ValueError,"DIVERGES"):
            history_paper_book(self.config,replay)

    def test_capital_risk_can_never_permit_live_trades(self):
        conf=copy.deepcopy(self.config)
        conf["noLiveOrders"]=False
        with self.assertRaisesRegex(ValueError,"UNSAFE"):
            history_paper_book(conf,self.replay)
        conf=copy.deepcopy(self.config)
        conf["fixedPaperRiskUSDTPerEligibleTrade"]=120
        with self.assertRaisesRegex(ValueError,"CAPITAL_RISK_INVALID"):
            history_paper_book(conf,self.replay)

    def test_trade_cannot_exceed_4h_retest_window(self):
        replay=copy.deepcopy(self.replay)
        row=next(x for x in replay["tradesAudit"]
                 if x["variant"]=="V91_RETEST_MAX4H")
        row["retestDelayHours"]=6
        with self.assertRaisesRegex(ValueError,"TIME_OR_RETEST_RULE"):
            history_paper_book(self.config,replay)

if __name__=="__main__":unittest.main()
