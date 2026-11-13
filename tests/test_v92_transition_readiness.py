"""Manual-only V7 -> V9.2 handover readiness test; synthetic assertions."""
import copy
import unittest
from v92_transition_readiness import evaluate

def fixtures(n=0):
    audit={
      "mode":"V92_STABLE_SHADOW_HARDENING_ONLY",
      "parityErrors":[],
      "matchedVerifiedHours":168,
      "matchedAssetChecks":504,
      "latestCommonHourUTC":"2026-11-13T00:00:00Z",
      "coverage":{"BTC_SOL":{"consecutiveRecentHours":168},
                  "ETH":{"consecutiveRecentHours":168}},
      "tradeEntryStopTPParityOnLiveTradeProven":True,
      "actualObservedExitEvents":50,
      "policy":{"maxRiskUSDTPerPosition":10.0,
                "maxCombinedOpenRiskUSDT":20.0},
      "newCappedBookPolicyNotAppliedToLegacyV92":True,
      "legacyV92RiskUSDTUnchanged":100,
      "missingHourNotBackfilled":True,
      "noRetroactiveTradesOrRewrittenCandles":True,
      "newBrokerOrders":False,
    }
    paper={
      "mode":"V92_BTC_ETH_SOL_SINGLE_THIRD_1000USDT_PROSPECTIVE_PAPER_ACCOUNT",
      "assets":["BTCUSDT","ETHUSDT","SOLUSDT"],
      "virtualInitialUSDT":1000,
      "noBrokerOrders":True,"noUserNotifications":True,
      "closedEligiblePaperTrades":n,"wins":n//2,"losses":n-n//2,
      "forwardOnlyPrecommittedPaperLedger":[{} for _ in range(n)],
      "netRealizedPaperR9BpsSide":2,
      "virtualPaperPnLStress25BpsUSDT":5,
      "lastCapturedBTCandSOLHourUTC":"2026-11-13T00:00:00Z",
      "lastCapturedETHHourUTC":"2026-11-13T00:00:00Z",
      "simultaneousAssetsDoNotHaveTotalRiskCap":False,
      "fixedVirtualStopRiskUSDTPerTrade":10,
      "verifiedCombinedOpenRiskCapUSDT":20,
      "originalV7V91AndOtherV92BooksUnchanged":True,
      "noHistorical836USDBackfilledIntoThisAccount":True,
      "missingHistoryAndNoGitSealedRetestExcluded":True,
    }
    return audit,paper

class MigrationReadinessTests(unittest.TestCase):
    def test_current_uncapped_zero_trade_book_not_ready(self):
        a,p=fixtures()
        a["tradeEntryStopTPParityOnLiveTradeProven"]=False
        a["actualObservedExitEvents"]=0
        a["coverage"]["ETH"]["consecutiveRecentHours"]=9
        p["simultaneousAssetsDoNotHaveTotalRiskCap"]=True
        p["fixedVirtualStopRiskUSDTPerTrade"]=100
        p.pop("verifiedCombinedOpenRiskCapUSDT")
        out=evaluate(a,p)
        self.assertEqual(out["status"],"CONTINUE_V7_V92_PARALLEL_PAPER")
        self.assertFalse(out["approvedToChangeProduction"])
        self.assertFalse(out["autoDisableV7"])
        self.assertIn("forwardTradeSampleAtLeast50",out["blockingChecks"])
        self.assertIn("riskCapAppliedToActualForwardPaperBook",out["blockingChecks"])

    def test_all_gates_only_enable_manual_review_never_switch(self):
        a,p=fixtures(50)
        out=evaluate(a,p)
        self.assertEqual(out["status"],"ELIGIBLE_FOR_MANUAL_HANDOVER_REVIEW")
        self.assertEqual(out["migrationPhase"],"MANUAL_REVIEW_ONLY")
        self.assertFalse(out["autoPromotion"])
        self.assertFalse(out["autoDisableV7"])
        self.assertFalse(out["approvedToChangeProduction"])
        self.assertFalse(out["noBrokerOrders"] is False)

    def test_lag_or_stress_loss_blocks(self):
        a,p=fixtures(50)
        p["lastCapturedETHHourUTC"]="2026-11-12T23:00:00Z"
        p["virtualPaperPnLStress25BpsUSDT"]=-5
        out=evaluate(a,p)
        self.assertIn("sameLatestSealedHour",out["blockingChecks"])
        self.assertIn("positiveRiskAndCostStressedPaperResults",out["blockingChecks"])

    def test_mismatched_ledger_rejected(self):
        a,p=fixtures(50)
        p["forwardOnlyPrecommittedPaperLedger"]=[]
        with self.assertRaisesRegex(ValueError,"LEDGER_COUNT_PARITY"):
            evaluate(a,p)

    def test_untrusted_trade_or_order_source_rejected(self):
        a,p=fixtures()
        p["noBrokerOrders"]=False
        with self.assertRaisesRegex(ValueError,"SAFETY_CONTRACT"):
            evaluate(a,p)

if __name__=="__main__":
    unittest.main()
