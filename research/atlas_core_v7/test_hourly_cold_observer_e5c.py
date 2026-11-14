"""E5-C source truth, no-backfill and no-live-signal negative controls.

Synthetic inputs are NEVER fed into actual observational run reports.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha1
from unittest import TestCase
from unittest.mock import patch
import json

from research.atlas_core_v7 import hourly_cold_observer_e5c as c

CLOSE="2026-11-14T21:00:00Z"
CAPTURE_BTC="2026-11-14T21:20:00Z"
CAPTURE_ETH="2026-11-14T21:22:00Z"
NOW="2026-11-14T21:35:00Z"
SHA_V92="a"*40
SHA_V9="b"*40
PRICES={"open":99.,"high":102.,"low":98.,"close":100.,"volume":1200.}

def enc(x):
    return (json.dumps(x,sort_keys=True,indent=2)+"\n").encode()

def state(*,watch=False,pending=False,open_pos=False):
    return {
        "newWatchAtThisClose":[{"stage":"synthetic-BOS"}] if watch else [],
        "paperTradeExitsObservedAtThisClose":[],
        "currentPaperState":{
            "activeBOSWatch":{"stage":"synthetic"} if watch else None,
            "pendingNextOpenPaperEntry":{"stage":"synthetic"} if pending else None,
            "openHypotheticalPosition":{"stage":"synthetic"} if open_pos else None,
        }
    }

def btc_source(*,watch=False,pending=False,stamp=CLOSE):
    src={
        "mode":c.ALLOWED_V92_MODES["BTC_SOL"],
        "targetClosed1HUTC":stamp,
        "capturedAtUTC":CAPTURE_BTC,
        "noBrokerOrders":True,"noUserNotifications":True,
        "noPastHourBackfill":True,
        "sourceVerifiedSameHour":True,
        "sourceV7AndV91RecomputedExactMatch":True,
        "liveBinanceExchangeParityNotIndependentlyProven":True,
        "hypotheticalEntryAtPastNextOpenNotProvenExecutable":True,
        "originalV7V91StrategyAndPortfolioUntouched":True,
        "policyFrozenAfterInspectingOldHistory":True,
        "ETHExcludedFromThisBTC_SOLCoreCapture":True,
        "assets":{},"originalV7_1H4HDailyCandleParity":{},
    }
    for asset in ("BTCUSDT","SOLUSDT"):
        src["assets"][asset]={
            "originalV7":state(),
            "originalV91":state(),
            "selectedV92":state(watch=watch if asset=="BTCUSDT" else False,
                                pending=pending if asset=="BTCUSDT" else False),
            "currentCloseRetestEvaluation":{
                "candidateRetestAtThisClose":False,
                "baselineRetestPresent":False,
                "selectedRetestPresent":False,
                "directCurrentFilterVeto":False,
            },
            "noStandaloneCandleDrivenEntry":True,
        }
        src["originalV7_1H4HDailyCandleParity"][asset]={}
        for tf,close in (("1hour",stamp),("4hour","2026-11-14T20:00:00Z"),
                         ("daily","2026-11-14T00:00:00Z")):
            src["originalV7_1H4HDailyCandleParity"][asset][tf]={
                "closedCandleUTC":close,
                "allOHLCVFieldsWithinIntegrityTolerances":True,
                "twoIndependentBinanceExchangeSourcesProven":False,
                "priceToleranceRel":.000002,
                "volumeToleranceRel":.005,
                "relativeDifferences":{
                    k:{"v7Reference":v,"reFetchedHistory":v,"relativeDifference":0}
                    for k,v in PRICES.items()
                }
            }
    return src

def eth_source(stamp=CLOSE):
    src={
        "mode":c.ALLOWED_V92_MODES["ETH"],
        "symbol":"ETHUSDT",
        "targetClosed1HUTC":stamp,
        "capturedAtUTC":CAPTURE_ETH,
        "noBrokerOrders":True,"noUserNotifications":True,
        "noRetroactiveBackfill":True,
        "verifiedSourceAndExactV7AndV91Replay":True,
        "independentBinanceTruthNotEstablished":True,
        "sameV91Max4hEntryStopTPAndExitLogic":True,
        "notNewETHTradeFromCandleAlone":True,
        "ethV92RetestVetoEnabled":False,
        "ethPatternObservationsOnly":True,
        "originalV7":state(),
        "originalV91":state(),
        "selectedV92":state(),
        "sourceIntegrity":{},
        "ethHigherTimeframeRecognition1D3D":{
            "1D":{"lastClosedCandleUTC":"2026-11-14T00:00:00Z","close":100.}
        }
    }
    for tf,close in (("1hour",stamp),("4hour","2026-11-14T20:00:00Z"),
                     ("daily","2026-11-14T00:00:00Z")):
        src["sourceIntegrity"][tf]={
            "closeUTC":close,"verified":True,
            "notIndependentBinanceExchangeTruth":True,
            "relativeDifference":{x:0 for x in PRICES}}
    return src

def v9_context(stamp=CLOSE):
    d={
      "status":"V9_HOURLY_OBSERVATION_VERIFIED_PAPER_CONTEXT_ONLY",
      "closed1HUTC":stamp,
      "observedAtUTC":"2026-11-14T21:23:00Z",
      "realOrders":False,
      "doesNotRepaintOrBackfillMissing4HForecasts":True,
      "officialNext4HColorRequiresBeforeStartRecord":True,
      "assets":{},
    }
    for symbol in ("BTCUSDT","ETHUSDT","SOLUSDT"):
        s={"contextOnlyNotANewPrestartDirectionForecast":True}
        for tf,close in (("1H",stamp),("4H","2026-11-14T20:00:00Z"),
                         ("Daily","2026-11-14T00:00:00Z")):
            s[tf]={"closedAtUTC":close,"OHLCV":dict(PRICES)}
        d["assets"][symbol]=s
    return d

def manifest(stamp="2026-11-14T21-00Z",continuous=True):
    entries=[]
    for i in range(4 if continuous else 1):
        epoch=c.strict_utc(CLOSE)-3600*i
        k=datetime.fromtimestamp(epoch,timezone.utc).strftime("%Y-%m-%dT%H-00Z")
        entries.append(k)
    return entries

def fake_fetcher(*,continuous=True,bts=None,eth=None,v9=None,corrupt_sha=False,
                 mismatched_latest_eth=False):
    bts=btc_source() if bts is None else bts
    eth=eth_source() if eth is None else eth
    v9=v9_context() if v9 is None else v9
    files={}
    for head,branch in ((SHA_V92,c.SOURCE_BRANCH_V92),(SHA_V9,c.SOURCE_BRANCH_V9)):
        from urllib.parse import quote
        files[c.API+"/branches/"+quote(branch,safe="")]=enc({"commit":{"sha":head}})
    for folder,doc in ((c.BTC_SOL_DIR,bts),(c.ETH_DIR,eth)):
        mapping=[]
        for key in manifest(continuous=continuous):
            item_path=folder+"/"+key+".json"
            source=deepcopy(doc)
            close=datetime.strptime(key,"%Y-%m-%dT%H-00Z").replace(tzinfo=timezone.utc)
            source["targetClosed1HUTC"]=close.strftime("%Y-%m-%dT%H:%M:%SZ")
            if key!=manifest()[0]:
                delta=22 if folder==c.ETH_DIR else 20
                source["capturedAtUTC"]=datetime.fromtimestamp(
                    int(close.timestamp())+delta*60,timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
            data=enc(source)
            git=c.sha_git_blob(data)
            if corrupt_sha and folder==c.ETH_DIR and key==manifest()[0]:
                git="0"*40
            mapping.append({"name":key+".json","type":"file","sha":git})
            files[c.RAW+"/"+SHA_V92+"/"+item_path]=data
        if mismatched_latest_eth and folder==c.ETH_DIR:
            mapping.pop(0)
        files[c.API+"/contents/"+folder+"?ref="+SHA_V92]=enc(mapping)
    files[c.RAW+"/"+SHA_V9+"/"+c.V9_PATH]=enc(v9)
    def get(url):
        if url not in files:
            raise AssertionError("Unexpected network read: "+url)
        return files[url]
    return get

class E5CSourceOrigin(TestCase):

    def test_https_and_hosts_locked(self):
        self.assertFalse(c._url_allowed("http://api.github.com/a"))
        self.assertFalse(c._url_allowed("https://evil.example/test"))
        self.assertFalse(c._url_allowed("https://api.github.com/x?api_key=1"))
        self.assertTrue(c._url_allowed(c.API+"/branches/abc"))
        self.assertTrue(c._url_allowed(c.API+"/contents/"+c.BTC_SOL_DIR+"?ref="+"a"*40))

    def test_other_branches_disallowed(self):
        with self.assertRaisesRegex(ValueError,"E5C_UNAPPROVED_SOURCE_BRANCH"):
            c.commit_head("main",fetch=lambda _:b"{}")

    def test_commit_pinned_source_sha_records(self):
        report=c.audit(fetch=fake_fetcher(),now_utc=NOW)
        self.assertEqual(report["sourceGitCommits"]["V92"],SHA_V92)
        self.assertEqual(report["sourceGitCommits"]["V9"],SHA_V9)
        self.assertEqual(len(report["sourceFileSHA256"]),3)

    def test_corrupt_byte_sha_blob_rejected(self):
        with self.assertRaisesRegex(ValueError,"E5C_GIT_SOURCE_BLOB_SHA1_MISMATCH"):
            c.audit(fetch=fake_fetcher(corrupt_sha=True),now_utc=NOW)

    def test_unexpected_directory_data_rejected(self):
        def err(_):
            return enc({"not":"a directory"})
        with self.assertRaisesRegex(ValueError,"E5C_NOT_A_DIRECTORY"):
            c.list_hourly(SHA_V92,c.BTC_SOL_DIR,fetch=err)

    def test_unapproved_remote_file_path_rejected(self):
        with self.assertRaisesRegex(ValueError,"E5C_HOURLY_FILE_PATH_TRAVERSAL"):
            c.read_git_blob(SHA_V92,c.BTC_SOL_DIR,{
                "file":c.BTC_SOL_DIR+"/../../secret.json",
                "gitBlobSHA1":"a"*40},fetch=lambda _:b"{}")

    def test_earlier_hour_file_tamper_rejected_not_merely_directory_present(self):
        valid=fake_fetcher()
        def changed(url):
            data=valid(url)
            if (url.endswith("/2026-11-14T20-00Z.json")
                and c.BTC_SOL_DIR in url):
                return data+b" "
            return data
        with self.assertRaisesRegex(ValueError,"E5C_GIT_SOURCE_BLOB_SHA1_MISMATCH"):
            c.audit(fetch=changed,now_utc=NOW)

    def test_latest_source_hour_drift_fails_closed(self):
        out=c.audit(fetch=fake_fetcher(mismatched_latest_eth=True),now_utc=NOW)
        self.assertEqual(out["status"],"SOURCE_HOURS_DISAGREE_FAIL_CLOSED")
        self.assertEqual(out["actualNewLiveOpportunityCount"],0)

    def test_frozen_e5a_inputs_remain_distinct_from_live(self):
        out=c.audit(fetch=fake_fetcher(),now_utc=NOW)
        self.assertEqual(out["historical51TradesCreditedToForward"],0)
        self.assertEqual(out["newForwardTradesAccrued"],0)
        self.assertEqual(out["actualNewLiveOpportunityCount"],0)
        self.assertFalse(out["realAccountExposureAvailable"])

class E5CCausalTimeliness(TestCase):

    def test_same_hour_source_with_three_asset_context_checks(self):
        d=c.audit(fetch=fake_fetcher(),now_utc=NOW)
        self.assertEqual(d["status"],"SOURCE_WITNESSES_CHECKED_OBSERVATION_ONLY")
        self.assertTrue(d["sourceIntegrityChecks"]["BTC_SOL_1H_4H_Daily_OHLCVMatches"])
        self.assertTrue(d["sourceIntegrityChecks"]["ETH_1D_CloseMatches"])
        self.assertFalse(d["sourceIntegrityChecks"]["ETH_1H_4H_FullIndependentOHLCVAvailable"])
        self.assertEqual(len(d["sourceAssetPaperObservations"]),3)

    def test_full_four_hours_proves_only_coverage_not_trade(self):
        d=c.audit(fetch=fake_fetcher(continuous=True),now_utc=NOW)
        self.assertTrue(d["consecutiveHourCoverage"]["matchedAcrossBothSources"])
        self.assertEqual(d["consecutiveHourCoverage"]["verifiedContentsWithGitBlobSHA1"],8)
        self.assertEqual(len(d["consecutiveHourCoverage"]["hourlySha256Evidence"]),8)
        self.assertFalse(d["hourlyObservationTimeliness"]["liveEntryEligible"])
        self.assertFalse(d["full3AssetLiveSourcePriceStopAndNextOpenValidated"])

    def test_missing_hours_remain_missing(self):
        d=c.audit(fetch=fake_fetcher(continuous=False),now_utc=NOW)
        self.assertFalse(d["consecutiveHourCoverage"]["matchedAcrossBothSources"])
        self.assertEqual(d["hourlyObservationTimeliness"]["status"],
                         "DELAYED_1H_OBSERVATION_NOT_AN_ENTRY")
        self.assertTrue(d["hourlyObservationTimeliness"]["historicallyMissingHoursNeverFilled"])

    def test_late_capture_not_backdated(self):
        d=c.audit(fetch=fake_fetcher(),now_utc=NOW)
        time=d["hourlyObservationTimeliness"]
        self.assertEqual(time["status"],"DELAYED_1H_OBSERVATION_NOT_AN_ENTRY")
        self.assertEqual(time["lastSourceCaptureLagMinutes"],22.)
        self.assertTrue(time["nextHourOpenAlreadyPassedByAnyPostCloseSnapshot"])
        self.assertFalse(time["entryAtExactOpeningPriceVerified"])

    def test_stale_snapshot_never_an_entry(self):
        future="2026-11-15T01:00:00Z"
        d=c.audit(fetch=fake_fetcher(),now_utc=future)
        self.assertEqual(d["hourlyObservationTimeliness"]["status"],"STALE_SOURCE_NO_ENTRY")
        self.assertFalse(d["hourlyObservationTimeliness"]["sourceHourAgeWithin90Minutes"])

    def test_future_capture_rejected(self):
        e=eth_source()
        e["capturedAtUTC"]="2026-11-15T01:00:00Z"
        with self.assertRaisesRegex(ValueError,"E5C_MALFORMED_OR_FUTURE_HOURLY_OBSERVATION"):
            c.audit(fetch=fake_fetcher(eth=e),now_utc=NOW)

    def test_target_not_equal_hour_filename_rejected(self):
        b=btc_source(stamp="2026-11-14T20:00:00Z")
        with self.assertRaisesRegex(ValueError,"E5C_FILENAME_TIMESTAMP_VS_SIGNED_CONTENT_DRIFT"):
            c.audit(fetch=fake_fetcher(bts=b),now_utc=NOW)

    def test_pending_hypothetical_entry_is_never_a_real_signal(self):
        b=btc_source(watch=True,pending=True)
        d=c.audit(fetch=fake_fetcher(bts=b),now_utc=NOW)
        self.assertEqual(d["newBOSWatchReports"],1)
        self.assertEqual(d["pendingHypotheticalPaperEntryReports"],1)
        self.assertEqual(d["actualNewLiveOpportunityCount"],0)
        for x in d["sourceAssetPaperObservations"]:
            self.assertFalse(x["sourceAnalysis"]["orderAllowed"])
            self.assertTrue(x["noExecutableEntryOrStopClaim"])

    def test_source_flags_cannot_be_silently_promoted(self):
        b=btc_source()
        b["hypotheticalEntryAtPastNextOpenNotProvenExecutable"]=False
        with self.assertRaisesRegex(ValueError,"E5C_BTC_SOL_VERIFICATION_OR_LIMITS_CHANGED"):
            c.audit(fetch=fake_fetcher(bts=b),now_utc=NOW)

    def test_hourly_v9_context_not_an_original_4h_trade_signal(self):
        v=v9_context()
        v["assets"]["BTCUSDT"]["contextOnlyNotANewPrestartDirectionForecast"]=False
        with self.assertRaisesRegex(ValueError,"E5C_V9_CONTEXT_AS_ENTRY"):
            c.audit(fetch=fake_fetcher(v9=v),now_utc=NOW)

    def test_mismatched_btc_price_relative_to_independent_context_rejected(self):
        v=v9_context()
        v["assets"]["BTCUSDT"]["1H"]["OHLCV"]["close"]=120.
        with self.assertRaisesRegex(ValueError,"E5C_V92_V9_PUBLIC_CONTEXT_OHLCV_MISMATCH"):
            c.audit(fetch=fake_fetcher(v9=v),now_utc=NOW)

    def test_eth_daily_date_drift_rejected(self):
        v=v9_context()
        v["assets"]["ETHUSDT"]["Daily"]["closedAtUTC"]="2026-11-13T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"E5C_ETH_1D_CLOSED_TIMESTAMP_DRIFT"):
            c.audit(fetch=fake_fetcher(v9=v),now_utc=NOW)

    def test_v92_source_independent_binance_claim_not_proven(self):
        b=btc_source()
        b["liveBinanceExchangeParityNotIndependentlyProven"]=False
        with self.assertRaisesRegex(ValueError,"E5C_BTC_SOL_VERIFICATION_OR_LIMITS_CHANGED"):
            c.audit(fetch=fake_fetcher(bts=b),now_utc=NOW)

    def test_ETH_is_never_a_new_candle_only_trade(self):
        e=eth_source()
        e["notNewETHTradeFromCandleAlone"]=False
        with self.assertRaisesRegex(ValueError,"E5C_ETH_VERIFICATION_OR_TRADE_CLASSIFICATION_CHANGED"):
            c.audit(fetch=fake_fetcher(eth=e),now_utc=NOW)

    def test_direct_retest_veto_and_selected_risk_conflict_rejected(self):
        b=btc_source()
        b["assets"]["SOLUSDT"]["currentCloseRetestEvaluation"]["directCurrentFilterVeto"]=True
        b["assets"]["SOLUSDT"]["currentCloseRetestEvaluation"]["selectedRetestPresent"]=True
        b["assets"]["SOLUSDT"]["currentCloseRetestEvaluation"]["baselineRetestPresent"]=True
        with self.assertRaisesRegex(ValueError,"E5C_SELECTED_RETEST_DESPITE_DIRECT_VETO"):
            c.audit(fetch=fake_fetcher(bts=b),now_utc=NOW)

    def test_original_paper_state_no_real_position_attribution(self):
        e=eth_source()
        e["selectedV92"]=state(open_pos=True)
        d=c.audit(fetch=fake_fetcher(eth=e),now_utc=NOW)
        row=next(x for x in d["sourceAssetPaperObservations"] if x["symbol"]=="ETHUSDT")
        self.assertTrue(row["sourceAnalysis"]["hypotheticalPaperPositionOpen"])
        self.assertFalse(row["sourceAnalysis"]["newLiveTradingSignal"])
        self.assertFalse(d["realAccountExposureAvailable"])

    def test_source_refuses_any_production_side_effect(self):
        d=c.audit(fetch=fake_fetcher(),now_utc=NOW)
        self.assertEqual(d["actionSafety"],c.REJECTED_LIVE_ACTIONS)
        self.assertTrue(all(d["actionSafety"].values()))
        self.assertFalse(d["independentlyExchangeVerifiedSource"])
        self.assertFalse(d["separateFrozenForwardCandidateBranchesModified"])

    def test_all_records_have_traceable_capture_timestamp(self):
        d=c.audit(fetch=fake_fetcher(),now_utc=NOW)
        for item in d["sourceAssetPaperObservations"]:
            self.assertLessEqual(c.strict_utc(item["sourceClosedHourUTC"]),
                                 c.strict_utc(item["sourceCapturedUTC"]))
            self.assertLessEqual(c.strict_utc(item["sourceCapturedUTC"]),
                                 c.strict_utc(item["observerReadUTC"]))

if __name__=="__main__":
    import unittest
    unittest.main()
