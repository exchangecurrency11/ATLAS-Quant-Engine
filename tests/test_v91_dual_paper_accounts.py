"""Two separate paper accounts must not fabricate overnight entries or fills."""
import copy
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path

from v91_dual_paper_accounts import build, verified_ledger, latest_hour_records, coverage_audit
from v91_prospective_retest import MODE as BTC_MODE, path_at
from v91_eth_prospective_retest import MODE as ETH_MODE

def iso(t):return datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def epoch(s):return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp())
START=epoch("2026-11-12T08:44:55Z")
FIRST=epoch("2026-11-12T09:00:00Z")

def config():
    return {
      "mode":"V7_VS_V91_PROSPECTIVE_SEPARATE_PAPER_ACCOUNTS",
      "requestedAtUTC":iso(START),
      "firstEligible1HCloseUTC":iso(FIRST),
      "initialVirtualCapitalUSDTPerAccount":1000.0,
      "fixedPaperRiskUSDTPerEligibleTrade":100.0,
      "noLiveOrders":True,"noRetroactiveExecution":True,
      "userExplicitlyRequested10PctRiskOnlyInVirtualPaper":True,
      "noNewNotifications":True,
      "V7ProductionAndExistingV91TradingRulesUnchanged":True}

def state():
    return {"activeBOSWatch":None,
            "pendingNextOpenPaperEntry":None,"openHypotheticalPosition":None}

def events():
    return {"newWatchAtThisClose":[],"paperTradeExitsObservedAtThisClose":[],
            "currentPaperState":state()}

def hour(t):
    return {
       "mode":BTC_MODE,"targetClosed1HUTC":iso(t),
       "capturedAtUTC":iso(t+19*60),
       "noBrokerOrders":True,"noNotifications":True,
       "V7SnapshotAndIndependentRecomputeExactMatch":True,
       "sourceVerifiedSameHour":True,
       "priceAndVolumeValidatedAgainstOriginalV7For1H4HDaily":True,
       "assets":{coin:{"originalV7":events(),"max4hRetest":events()}
                 for coin in ("BTCUSDT","SOLUSDT")}}

def score():
    return {
      "mode":"V91_PROSPECTIVE_CAUSAL_PAPER_SCOREBOARD",
      "noBrokerOrders":True,"noNotifications":True,
      "realTimeExecutableEntryCountProven":0,
      "noBackfilledOrPostSelectedTrades":True,
      "tradeLedger":{coin:{model:[] for model in ("V7_ORIGINAL","V91_RETEST_MAX4H")}
                     for coin in ("BTCUSDT","SOLUSDT")}}

class DualPaperTests(unittest.TestCase):
    def test_missing_hours_are_reported_not_backfilled(self):
        records={FIRST:hour(FIRST),FIRST+2*3600:hour(FIRST+2*3600)}
        audit=coverage_audit(records,FIRST,FIRST+2*3600)
        self.assertEqual(audit["expectedHours"],3)
        self.assertEqual(audit["savedExpectedHours"],2)
        self.assertEqual(audit["missingHourCount"],1)
        self.assertEqual(audit["missingHoursUTC"],[iso(FIRST+3600)])
        self.assertTrue(audit["noBackfill"])

    def test_eth_lag_is_reported_against_shared_latest_hour(self):
        records={FIRST:hour(FIRST),FIRST+3600:hour(FIRST+3600)}
        audit=coverage_audit(records,FIRST,FIRST+3*3600)
        self.assertEqual(audit["savedExpectedHours"],2)
        self.assertEqual(audit["missingHourCount"],2)
        self.assertEqual(audit["lagHours"],2)

    def test_btc_sol_source_uses_its_real_no_notifications_schema(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            path_at(root,FIRST).write_text(json.dumps(hour(FIRST)))
            records=latest_hour_records(root,BTC_MODE,first_utc=FIRST,
                                        asset_refs={"BTCUSDT","SOLUSDT"})
            self.assertEqual(list(records),[FIRST])

    def test_eth_source_uses_its_separate_no_user_notifications_schema(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            h={"mode":ETH_MODE,"symbol":"ETHUSDT",
               "targetClosed1HUTC":iso(FIRST),"capturedAtUTC":iso(FIRST+19*60),
               "noBrokerOrders":True,"noUserNotifications":True,
               "verifiedSourceAndExactV7Replay":True,
               "sourceIntegrity":{k:{"verified":True} for k in ("1hour","4hour","daily")},
               "crossTimeframeOHLCV":{"1H_matches_4H":5,"1H_matches_daily":5}}
            path_at(root,FIRST).write_text(json.dumps(h))
            records=latest_hour_records(root,ETH_MODE,first_utc=FIRST,
                                        asset_refs={"ETHUSDT"})
            self.assertEqual(list(records),[FIRST])

    def test_btc_sol_source_cannot_substitute_eth_notification_field(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);h=hour(FIRST)
            h.pop("noNotifications")
            h["noUserNotifications"]=True
            path_at(root,FIRST).write_text(json.dumps(h))
            with self.assertRaisesRegex(ValueError,"UNVERIFIED"):
                latest_hour_records(root,BTC_MODE,first_utc=FIRST,
                                    asset_refs={"BTCUSDT","SOLUSDT"})

    def test_btc_sol_source_requires_full_ohlcv_parity_flag(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);h=hour(FIRST)
            h["priceAndVolumeValidatedAgainstOriginalV7For1H4HDaily"]=False
            path_at(root,FIRST).write_text(json.dumps(h))
            with self.assertRaisesRegex(ValueError,"PARITY_UNVERIFIED"):
                latest_hour_records(root,BTC_MODE,first_utc=FIRST,
                                    asset_refs={"BTCUSDT","SOLUSDT"})

    def test_eth_source_cannot_substitute_btc_sol_notification_field(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            h={"mode":ETH_MODE,"symbol":"ETHUSDT",
               "targetClosed1HUTC":iso(FIRST),"capturedAtUTC":iso(FIRST+19*60),
               "noBrokerOrders":True,"noNotifications":True,
               "verifiedSourceAndExactV7Replay":True}
            path_at(root,FIRST).write_text(json.dumps(h))
            with self.assertRaisesRegex(ValueError,"UNVERIFIED"):
                latest_hour_records(root,ETH_MODE,first_utc=FIRST,
                                    asset_refs={"ETHUSDT"})

    def test_start_flat_even_when_old_night_source_exists(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            path_at(root,FIRST-3600).write_text(json.dumps(hour(FIRST-3600)))
            p=build(config(),root,score())
            self.assertIsNone(p["lastCapturedEligibleBTCandSOLHourUTC"])
            self.assertFalse(p["ETHAddedOnlyIfIndependentV7ParityVerified"])
            for name in ("V7_ORIGINAL","V91_RETEST_MAX4H"):
                a=p["accounts"][name]
                self.assertEqual(a["virtualEquityUSDT"],1000)
                self.assertEqual(a["closedEligiblePaperTrades"],0)
                self.assertEqual(a["perAssetLatestState"]["BTCUSDT"]["status"],
                                 "NO_ELIGIBLE_CAPTURE_AFTER_START")
            self.assertTrue(p["nightBeforeRequestRetrospectiveOnlyNoOrders"])

    def test_two_accounts_wait_on_current_no_BOS_retest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            path_at(root,FIRST).write_text(json.dumps(hour(FIRST)))
            p=build(config(),root,score())
            self.assertEqual(p["lastCapturedEligibleBTCandSOLHourUTC"],iso(FIRST))
            for account in p["accounts"].values():
                self.assertEqual(account["perAssetLatestState"]["SOLUSDT"]["status"],
                                 "FLAT_NO_CONFIRMED_TRADE")
                self.assertEqual(account["closedEligiblePaperTrades"],0)
                self.assertEqual(account["brokerOrders"],0)

    def test_rejected_backdated_faux_trade(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            path_at(root,FIRST).write_text(json.dumps(hour(FIRST)))
            sc=score()
            sc["tradeLedger"]["BTCUSDT"]["V7_ORIGINAL"].append({
                "entryUTC":iso(FIRST-3600),"exitUTC":iso(FIRST),"side":"bearish",
                "netR9Bps":5,"netR25Bps":4})
            p=build(config(),root,sc)
            self.assertEqual(p["accounts"]["V7_ORIGINAL"]["virtualRealizedPnlUSDT"],0)

    def test_matched_prospective_exit_virtual_r_bookkeeping_only(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            t=FIRST+7200
            entry=FIRST
            x=hour(t)
            trade={"entryOpenUTC":entry,"exitKnownUTC":t,"side":"bearish",
                   "netRIllustrative":1.5}
            x["assets"]["SOLUSDT"]["max4hRetest"]["paperTradeExitsObservedAtThisClose"]=[trade]
            path_at(root,t).write_text(json.dumps(x))
            sc=score()
            sc["tradeLedger"]["SOLUSDT"]["V91_RETEST_MAX4H"].append({
                "entryUTC":iso(entry),"exitUTC":iso(t),"side":"bearish",
                "netR9Bps":1.5,"netR25Bps":.85})
            p=build(config(),root,sc)
            self.assertEqual(p["accounts"]["V7_ORIGINAL"]["virtualEquityUSDT"],1000)
            self.assertEqual(p["accounts"]["V91_RETEST_MAX4H"]["virtualEquityUSDT"],1150)
            self.assertEqual(p["accounts"]["V91_RETEST_MAX4H"]["closedEligiblePaperTrades"],1)
            self.assertEqual(p["accounts"]["V91_RETEST_MAX4H"]["virtualRealizedPnlUSDT"],150)
            self.assertEqual(p["accounts"]["V91_RETEST_MAX4H"]["realExecutableFillsVerified"],0)

    def test_forged_ledger_without_matching_source_exit_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            t=FIRST+7200
            path_at(root,t).write_text(json.dumps(hour(t)))
            sc=score()
            sc["tradeLedger"]["SOLUSDT"]["V91_RETEST_MAX4H"].append({
                "entryUTC":iso(FIRST),"exitUTC":iso(t),"side":"bearish",
                "netR9Bps":2,"netR25Bps":1.5})
            with self.assertRaisesRegex(ValueError,"NOT_MATCHED"):
                build(config(),root,sc)

    def test_source_claims_or_dates_invalid_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);wrong=hour(FIRST);wrong["noBrokerOrders"]=False
            path_at(root,FIRST).write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError,"UNVERIFIED"):
                build(config(),root,score())
            wrong=hour(FIRST);wrong["capturedAtUTC"]=iso(FIRST+3600)
            path_at(root,FIRST).write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError,"UNVERIFIED"):
                build(config(),root,score())

    def test_config_can_never_enable_live_orders_or_prior_entry(self):
        with tempfile.TemporaryDirectory() as d:
            z=config();z["noLiveOrders"]=False
            with self.assertRaisesRegex(ValueError,"UNSAFE"):
                build(z,d,score())
            z=config();z["firstEligible1HCloseUTC"]=iso(FIRST-3600)
            with self.assertRaisesRegex(ValueError,"RETROACTIVE"):
                build(z,d,score())

    def test_explicit_high_risk_opt_in_and_strict_ten_percent_ceiling(self):
        with tempfile.TemporaryDirectory() as d:
            z=config()
            z["userExplicitlyRequested10PctRiskOnlyInVirtualPaper"]=False
            with self.assertRaisesRegex(ValueError,"HIGH_RISK"):
                build(z,d,score())
            z=config()
            z["fixedPaperRiskUSDTPerEligibleTrade"]=101
            with self.assertRaisesRegex(ValueError,"INVALID_FIXED_RISK"):
                build(z,d,score())

    def test_user_requested_capital_risk_is_not_compounded_to_real_orders(self):
        with tempfile.TemporaryDirectory() as d:
            out=build(config(),d,score())
            for a in out["accounts"].values():
                self.assertEqual(a["virtualInitialUSDT"],1000)
                self.assertEqual(a["virtualPaperRiskPerTradeUSDT"],100)
                self.assertEqual(a["riskPctOfInitialCapital"],10)
                self.assertTrue(a["riskPerTradeIsHighAndNotRecommendedForLive"])
                self.assertEqual(a["brokerOrders"],0)
            self.assertTrue(out["riskSizingIsFixedPaper100USDTPerRNotRealPositionFill"])

    def test_incomplete_trade_account_does_not_imply_executable_fill(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);h=hour(FIRST)
            h["assets"]["BTCUSDT"]["max4hRetest"]["currentPaperState"]["pendingNextOpenPaperEntry"]={"side":"bullish"}
            path_at(root,FIRST).write_text(json.dumps(h))
            out=build(config(),root,score())
            m=out["accounts"]["V91_RETEST_MAX4H"]
            self.assertEqual(m["perAssetLatestState"]["BTCUSDT"]["status"],
                             "RETEST_PENDING_UNEXECUTED")
            self.assertEqual(m["closedEligiblePaperTrades"],0)
            self.assertEqual(m["realExecutableFillsVerified"],0)

if __name__=="__main__":unittest.main()
