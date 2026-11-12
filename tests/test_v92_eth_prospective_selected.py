"""ETH V9.2 source provenance, no-lookahead, shared paper portfolio regression."""
import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from v7_forward_observer import iso
from v92_eth_prospective_selected import (
    FIRST_ETH, REQUESTED_ETH,MODE as ETH_HOUR, BOOK as ETH_COMPONENT,
    verify_eth_v92_source,load_hours,entry_evidence,eth_component
)
from v92_third_paper_aggregate import build as combined_build, MODE as COMBINED_MODE
from v92_prospective_selected import BOOK as CORE_MODE

def base_v91(t=FIRST_ETH):
    return {
      "mode":"V91_ETH_PROSPECTIVE_4H_RETEST_IMMUTABLE_PAPER_SHADOW",
      "symbol":"ETHUSDT","originalV7Reference":"ETHUSDT_PERP.A",
      "verifiedSourceAndExactV7Replay":True,
      "noBackfill":True,"noBrokerOrders":True,"noUserNotifications":True,
      "independentBinanceMarketTruthEstablished":False,
      "sourceIntegrity":{k:{"verified":True} for k in
                         ("1hour","4hour","daily")},
      "targetClosed1HUTC":iso(t),"capturedAtUTC":iso(t+1600)
    }

def base_v7(t=FIRST_ETH):
    return {
      "status":"VERIFIED_PAPER_OBSERVATION",
      "mode":"ETH_V7_INDEPENDENT_PAPER_FORWARD_NO_ORDERS",
      "symbol":"ETHUSDT_PERP.A","brokerOrders":False,
      "paperForwardObservation":True,"productionSystemModified":False,
      "dataSource":"Coinalyze ETHUSDT_PERP.A / Binance perpetual read-only API",
      "targetClosed1HUTC":iso(t),"observedAtUTC":iso(t+1500)
    }

def core():
    return {
      "mode":CORE_MODE,"virtualInitialUSDT":1000,
      "targetVirtualRiskUSDTPerTrade":100,
      "firstEligible1HCloseUTC":"2026-11-12T11:00:00Z",
      "noBrokerOrders":True,"noUserNotifications":True,
      "noActualExchangeExecutionOrFill":True,
      "historicalPlus836USDNotTransferredHere":True,
      "V7V91CurrentPaperAccountsUnchanged":True,
      "savedDistinctVerifiedHours":0,
      "lastDistinctVerifiedClosed1HUTC":None,
      "stateBySymbol":{"BTCUSDT":{},"SOLUSDT":{}},
      "closedEligiblePaperTrades":0,
      "netRealizedPaperR9BpsPerSide":0,
      "validatedProspectivePaperLedger":[]
    }

def eth():
    return {
      "mode":ETH_COMPONENT,"asset":"ETHUSDT",
      "firstEligible1HCloseUTC":"2026-11-12T12:00:00Z",
      "noBrokerOrders":True,"noUserNotifications":True,
      "separateETHStartingCapitalNotAllocated":True,
      "ETHmax4hPaperEngineSameAsV91NoCandleVeto":True,
      "noRealExchangeOrProvenExecutableFills":True,
      "originalV7V91AndBTCSOLV92Unchanged":True,
      "savedDistinctVerifiedETHHours":0,
      "lastVerifiedETHCloseUTC":None,
      "closedEligiblePaperTrades":0,
      "netPaperR9BpsSide":0,
      "verifiedProspectivePaperLedger":[],
      "stateETH":{"state":"ETH_WAIT","lastClosedUTC":None},
    }

def hour(t):
    return {
       "mode":ETH_HOUR,
       "symbol":"ETHUSDT",
       "targetClosed1HUTC":iso(t),
       "capturedAtUTC":iso(t+1600),
       "verifiedSourceAndExactV7AndV91Replay":True,
       "noBrokerOrders":True,
       "noUserNotifications":True,
       "selectedV92":{
           "newWatchAtThisClose":[],
           "paperTradeExitsObservedAtThisClose":[],
           "currentPaperState":{
              "activeBOSWatch":None,
              "pendingNextOpenPaperEntry":None,
              "openHypotheticalPosition":None}},
       "ethReversalPatternRecognition1H4H":{}
    }

class TestETHV92(unittest.TestCase):
    def test_eth_source_window_allows_last_minute_but_never_rollover(self):
        self.assertTrue(verify_eth_v92_source(
            base_v91(),base_v7(),FIRST_ETH,FIRST_ETH+3599))
        with self.assertRaisesRegex(ValueError,"NOT_CURRENT"):
            verify_eth_v92_source(
                base_v91(),base_v7(),FIRST_ETH,FIRST_ETH+3600)

    def test_eth_first_allowed_later_than_request(self):
        self.assertTrue(REQUESTED_ETH<FIRST_ETH)
        self.assertEqual(FIRST_ETH%3600,0)

    def test_verified_both_sources_at_current_hour(self):
        self.assertTrue(verify_eth_v92_source(
            base_v91(),base_v7(),FIRST_ETH,FIRST_ETH+1800))
        with self.assertRaisesRegex(ValueError,"NOT_CURRENT"):
            verify_eth_v92_source(
                base_v91(),base_v7(),FIRST_ETH,FIRST_ETH+4000)
        with self.assertRaisesRegex(ValueError,"NOT_CURRENT"):
            verify_eth_v92_source(
                base_v91(),base_v7(),FIRST_ETH,FIRST_ETH+250)

    def test_no_historical_eth_backfill(self):
        before=FIRST_ETH-3600
        with self.assertRaisesRegex(ValueError,"RETROACTIVE"):
            verify_eth_v92_source(
                base_v91(before),base_v7(before),before,before+1800)

    def test_missing_or_malformed_v91_source_rejected(self):
        for key in ("verifiedSourceAndExactV7Replay",
                    "noBrokerOrders","noUserNotifications"):
            x=base_v91();x[key]=False
            with self.assertRaisesRegex(ValueError,"UNVERIFIED"):
                verify_eth_v92_source(x,base_v7(),FIRST_ETH,FIRST_ETH+1800)
        x=base_v91();x["sourceIntegrity"]["4hour"]["verified"]=False
        with self.assertRaisesRegex(ValueError,"UNVERIFIED"):
            verify_eth_v92_source(x,base_v7(),FIRST_ETH,FIRST_ETH+1800)

    def test_spot_wrong_symbol_and_invalid_v7_never_accepted(self):
        for key,val in (
            ("symbol","BTCUSDT_PERP.A"),
            ("paperForwardObservation",False),
            ("brokerOrders",True),
            ("dataSource","ETHUSDT spot")):
            original=base_v7();original[key]=val
            with self.assertRaisesRegex(ValueError,"MISSING_ORIGINAL"):
                verify_eth_v92_source(
                    base_v91(),original,FIRST_ETH,FIRST_ETH+1800)

    def test_git_prior_commit_is_required_when_source_path_supplied(self):
        with self.assertRaisesRegex(ValueError,"PRIOR_GIT_COMMIT"):
            verify_eth_v92_source(
                base_v91(),base_v7(),FIRST_ETH,FIRST_ETH+1800,
                source_path="/missing/file",source_repo=".")

    def test_no_fake_eth_trades_when_initial_ledger_empty(self):
        report=eth_component({},Path("/nonexistent"))
        self.assertEqual(report["savedDistinctVerifiedETHHours"],0)
        self.assertEqual(report["closedEligiblePaperTrades"],0)
        self.assertEqual(report["netPaperR9BpsSide"],0)
        self.assertTrue(report["separateETHStartingCapitalNotAllocated"])
        self.assertTrue(report["ETHmax4hPaperEngineSameAsV91NoCandleVeto"])

    def test_eth_immutable_hour_requirements(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            f=p/"2026-11-12T12-00Z.json"
            f.write_text(__import__("json").dumps(hour(FIRST_ETH)))
            d=load_hours(p)
            self.assertEqual(len(d),1)
            with self.assertRaisesRegex(ValueError,"OVERWRITE"):
                load_hours(p,current=hour(FIRST_ETH))

    def test_unsealed_exit_not_counted(self):
        trade={
          "watchKnownUTC":FIRST_ETH-3600,
          "retestKnownUTC":FIRST_ETH,
          "entryOpenUTC":FIRST_ETH,
          "exitKnownUTC":FIRST_ETH+3600,
          "entry":2000,"stop":1980,"risk":20,
          "side":"bullish","netRIllustrative":1}
        x=hour(FIRST_ETH+3600)
        x["selectedV92"]["paperTradeExitsObservedAtThisClose"]=[trade]
        with tempfile.TemporaryDirectory() as td:
            report=eth_component({FIRST_ETH+3600:x},Path(td))
            self.assertEqual(report["closedEligiblePaperTrades"],0)
            self.assertEqual(
                report["excludedUnsealedETHExits"][0]["reason"],
                "ETH_V92_MISSING_ORIGINALLY_GIT_SEALED_RETEST")

    def test_three_assets_share_one_initial_1000(self):
        merged=combined_build(core(),eth())
        self.assertEqual(merged["mode"],COMBINED_MODE)
        self.assertEqual(merged["assets"],["BTCUSDT","ETHUSDT","SOLUSDT"])
        self.assertEqual(merged["virtualPaperEquityUSDT"],1000)
        self.assertEqual(merged["closedEligiblePaperTrades"],0)
        self.assertTrue(merged["sharedSingleVirtualPortfolioNotThreeTimes1000"])
        self.assertEqual(merged["perAssetScores"]["ETHUSDT"]["closedEligiblePaperTrades"],0)

    def test_missing_eth_component_safe_awaiting_first_hour(self):
        merged=combined_build(core())
        self.assertEqual(merged["virtualPaperEquityUSDT"],1000)
        self.assertEqual(merged["sourceETHVerifiedClosedHours"],0)

    def test_eth_one_real_precommitted_paper_R_100_not_1000_extra(self):
        x=eth()
        x["verifiedProspectivePaperLedger"]=[{
           "symbol":"ETHUSDT","entryUTC":iso(FIRST_ETH),
           "exitUTC":iso(FIRST_ETH+3600),"side":"bullish",
           "netR9Bps":1.5,"netR25Bps":1.2,
           "notVerifiedExecutableRealFill":True}]
        x["closedEligiblePaperTrades"]=1
        x["netPaperR9BpsSide"]=1.5
        merged=combined_build(core(),x)
        self.assertEqual(merged["virtualPaperEquityUSDT"],1150)
        self.assertEqual(merged["virtualPaperPnLUSDT"],150)
        self.assertEqual(merged["closedEligiblePaperTrades"],1)

    def test_fake_eth_or_double_counted_capital_is_rejected(self):
        x=eth()
        x["separateETHStartingCapitalNotAllocated"]=False
        with self.assertRaisesRegex(ValueError,"ETH_COMPONENT_UNVERIFIED"):
            combined_build(core(),x)
        x=eth();x["netPaperR9BpsSide"]=1000
        with self.assertRaisesRegex(ValueError,"LEDGER_AGGREGATE_MISMATCH"):
            combined_build(core(),x)

    def test_pre_eth_start_trade_rejected(self):
        x=eth()
        x["verifiedProspectivePaperLedger"]=[{
           "symbol":"ETHUSDT","entryUTC":iso(FIRST_ETH-3600),
           "exitUTC":iso(FIRST_ETH+3600),"side":"bullish",
           "netR9Bps":1,"netR25Bps":.8,
           "notVerifiedExecutableRealFill":True}]
        x["closedEligiblePaperTrades"]=1
        x["netPaperR9BpsSide"]=1
        with self.assertRaisesRegex(ValueError,"NONCAUSAL"):
            combined_build(core(),x)

if __name__=="__main__":unittest.main()
