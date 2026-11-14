"""E5-B strict frozen retrospective-month intake negative controls.

All unit tests offline; latest.json fixtures are SYNTHETIC and NEVER
included in the real GitHub Actions report or promoted to a live entry.
"""
from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError
import json

from research.atlas_core_v6 import prospective_intake_e5b as m

ASOF="2026-12-01T00:00:00Z"
NOW="2026-12-03T12:00:00Z"
WATCH="2026-11-16T01:00:00Z"
RETEST="2026-11-16T02:00:00Z"
EXIT="2026-11-16T03:00:00Z"

def encoded(obj):
    return (json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode()

def source_packets():
    files={}
    for name,conf in m.CHANNELS.items():
        for path in (conf["specPath"],conf["preflightPath"]):
            files[(name,path)]=Path(path).read_bytes()
    return files

def add_verified_month_synthetic(files, channel, data):
    conf=m.CHANNELS[channel]
    files[(channel,conf["folder"]+"/latest.json")]=encoded(data)
    files[(channel,conf["folder"]+"/snapshots/2026-11.json")]=encoded(data)
    return files

def readfiles(files):
    def f(channel,relative,*,optional=False):
        key=(channel,relative)
        if key not in files:
            if optional:return None
            raise ValueError("TEST_EXPECTED_DOCUMENT_MISSING")
        return files[key]
    return f

def base_manifest(channel):
    p=Path(m.CHANNELS[channel]["preflightPath"])
    old=json.loads(p.read_text())
    hashes=old["archiveSHA256"] if channel=="ETH_V93_SIX_STREAM" else old["officialArchiveSHA256"]
    out=dict(hashes)
    for sym in sorted(m.ASSETS):
        out[sym+":2026-11"]="a"*64
    return out

def eth_trade():
    return {
        "side":"bullish","watchKnownUTC":WATCH,"retestKnownUTC":RETEST,
        "entryOpenUTC":RETEST,"exitKnownUTC":EXIT,
        "entry":100.,"stop":99.,"targets":[101.,102.,103.],
        "exitReason":"STOP_FIRST_OR_AFTER_TP",
        "netR9Bps":-1.18,"netR25Bps":-1.5,
    }

def btc_trade():
    return {
        "side":"bullish","watchKnownUTC":WATCH,"retestKnownUTC":RETEST,
        "entryOpenUTC":RETEST,"exitKnownUTC":EXIT,
        "exitReason":"STOP_FIRST_OR_AFTER_TP",
        "netR25Bps":-1.5,
    }

def eth_snapshot(rows=1):
    conf=m.CHANNELS["ETH_V93_SIX_STREAM"]
    spec=json.loads(Path(conf["specPath"]).read_text())
    streams={}
    for name,mode in spec["candidates"].items():
        tapes=[eth_trade()] if name=="ETH_BOS_EMA_RELAX" and rows else []
        count=len(tapes)
        r9=sum(z["netR9Bps"] for z in tapes)
        r25=sum(z["netR25Bps"] for z in tapes)
        streams[name]={
            "symbol":mode["symbol"],"mode":mode["mode"],
            "disabledGates":mode["disabledGates"],
            "closedProspectiveTrades":tapes,
            "metrics9Bps":{"trades":count,"netR":r9},
            "metrics25Bps":{"trades":count,"netR":r25},
            "openOrPendingAtLastClose":{"position":False,"pending":False},
            "isActualExecution":False,
            "noBackfilledHistoricalTrades":True,
            "unresolvedNotCredited":True,
        }
    manifest=base_manifest("ETH_V93_SIX_STREAM")
    return {
        "status":"PROSPECTIVE_MONTHLY_SHADOW_ONLY",
        "asOfExclusiveUTC":ASOF,
        "startProspectiveUTC":spec["freezeUTC"],
        "archiveSHA256":manifest,
        "verifiedArchives":len(manifest),
        "sourceHashSHA256":spec["immutableEngineHashes"],
        "neverRealOrders":True,"cannotCreditAnyPreFreezeTrade":True,
        "noExistingV7V92AccountWrites":True,"notRealtimeAlerts":True,
        "periodPreviouslyBacktestedForTraining":False,
        "reportedStreams":streams,
    }

def btc_snapshot(rows=1):
    conf=m.CHANNELS["BTC_SOL_V93_HIGH_VOL"]
    spec=json.loads(Path(conf["specPath"]).read_text())
    manifest=base_manifest("BTC_SOL_V93_HIGH_VOL")
    streams={}
    for symbol in ("BTCUSDT","SOLUSDT"):
        versions={}
        for name in ("V92_REFERENCE","HIGH_VOL_CANDIDATE"):
            tape=[btc_trade()] if (symbol=="BTCUSDT" and name=="V92_REFERENCE" and rows) else []
            n=len(tape)
            versions[name]={
                "metric":{"9":{"trades":n},"25":{"trades":n,"netR":sum(t["netR25Bps"] for t in tape)},
                          "50":{"trades":n}},
                "closedTrades":tape,"sourceOnly":True}
        streams[symbol]={"versions":versions}
    return {
        "status":"BTC_SOL_MONTH_COMPLETE_FROZEN_PROSPECTIVE",
        "freezeUTC":spec["freezeUTC"],
        "asOfExclusiveUTC":ASOF,
        "officialArchiveSHA256":manifest,
        "officialArchiveCount":len(manifest),
        "frozenSpecHashes":spec["frozenEngineHashesSHA256"],
        "independentNewFutureTradesOnly":True,
        "noHistoricalTradesCredited":True,
        "existingSixStreamV93ReferenceParity":True,
        "unresolvedPositionsNotCountedAsClosed":True,
        "realOrders":False,"notifications":False,
        "productionOrExistingPaperWrites":False,
        "candidatePromotionApproved":False,
        "streams":streams,
    }

def synthetic_files(*,eth=True,btc=True):
    files=source_packets()
    if eth:add_verified_month_synthetic(files,"ETH_V93_SIX_STREAM",eth_snapshot())
    if btc:add_verified_month_synthetic(files,"BTC_SOL_V93_HIGH_VOL",btc_snapshot())
    return files

class FrozenProspectiveNoData(TestCase):
    def test_original_frozen_branch_mapping_never_main(self):
        self.assertEqual(set(m.CHANNELS),{"ETH_V93_SIX_STREAM","BTC_SOL_V93_HIGH_VOL"})
        self.assertTrue(all(x["branch"].startswith("research/") for x in m.CHANNELS.values()))

    def test_real_preflight_pins_have_not_drifted(self):
        source=source_packets()
        for channel in m.CHANNELS:
            spec,pre,sha=m.validate_origin(channel,readfiles(source))
            self.assertEqual(len(sha),2)
            self.assertEqual(spec["freezeUTC"],m.CHANNELS[channel]["freeze"])

    def test_no_postfreeze_snapshots_is_zero_eligible_opportunities(self):
        out=m.audit(fetcher=readfiles(source_packets()),now_utc=NOW)
        self.assertEqual(out["uniqueRealTimeEntryOpportunitiesValidated"],0)
        self.assertEqual(out["cohortRowsReadAcrossAllVersions"],0)
        self.assertEqual(out["liveOrContemporaneousEntryCards"],[])
        self.assertEqual(out["historical51TradesCreditedAsProspective"],0)
        self.assertEqual(out["newUserAlerts"] if "newUserAlerts" in out else out["noAlerts"],True)
        self.assertFalse(out["prospectiveSourceScriptsWereReexecuted"])
        self.assertTrue(all(x["status"]=="NO_COMPLETED_POSTFREEZE_MONTHLY_SNAPSHOT"
                            for x in out["channels"].values()))

    def test_local_frozen_spec_byte_tamper_is_rejected(self):
        files=source_packets()
        channel="ETH_V93_SIX_STREAM"
        key=(channel,m.CHANNELS[channel]["specPath"])
        files[key]=files[key]+b" "
        with self.assertRaisesRegex(ValueError,"E5B_REMOTE_FROZEN_SPEC_PREFLIGHT_DRIFT"):
            m.validate_origin(channel,readfiles(files))

    def test_remote_path_escape_rejected(self):
        with self.assertRaisesRegex(ValueError,"E5B_UNAUTHORIZED_REMOTE_PATH"):
            m.fetch_source("ETH_V93_SIX_STREAM",
              "forward/v93_shadow_prospective_20261113/../../fake.json")

    def test_unknown_channel_rejected(self):
        with self.assertRaisesRegex(ValueError,"E5B_UNKNOWN_FROZEN_CHANNEL"):
            m.fetch_source("FAKE","forward/a.json")

    def test_optional_404_is_no_data_but_auth_failure_is_not(self):
        def raiser(req,timeout):
            raise HTTPError(req.full_url,404,"missing",None,None)
        with patch.object(m,"urlopen",side_effect=raiser):
            x=m.fetch_source("ETH_V93_SIX_STREAM",
                "forward/v93_shadow_prospective_20261113/latest.json",optional=True)
        self.assertIsNone(x)
        def forbidden(req,timeout):
            raise HTTPError(req.full_url,403,"forbidden",None,None)
        with patch.object(m,"urlopen",side_effect=forbidden):
            with self.assertRaisesRegex(ValueError,"E5B_FROZEN_SOURCE_HTTP_FAILURE"):
                m.fetch_source("ETH_V93_SIX_STREAM",
                    "forward/v93_shadow_prospective_20261113/latest.json",optional=True)

class SyntheticSnapshotValidation(TestCase):
    def check(self,files):
        return m.audit(fetcher=readfiles(files),now_utc=NOW)

    def test_both_synthetic_completed_months_are_audit_only(self):
        result=self.check(synthetic_files())
        self.assertEqual(result["cohortRowsReadAcrossAllVersions"],2)
        self.assertEqual(result["uniqueRealTimeEntryOpportunitiesValidated"],0)
        self.assertEqual(result["liveOrContemporaneousEntryCards"],[])
        self.assertEqual(result["readiness"],"MONTHLY_FROZEN_SOURCE_AUDIT_AVAILABLE_BUT_NO_TIMELY_ENTRY")
        self.assertTrue(all(c["immutableMonthlySnapshotExactMatch"]
                            for c in result["channels"].values()))
        self.assertFalse(result["officialMonthlyZIPsRedownloadedByE5B"])
        self.assertEqual(result["newTradeOrders"],0) if "newTradeOrders" in result else self.assertTrue(result["noOrders"])

    def test_eth_valid_price_stop_target_and_25bps_math(self):
        rows=m.scan_trades([eth_trade()],"ETHUSDT",
            m.utc("2026-11-14T00:00:00Z"),m.utc(ASOF),
            {"trades":1,"netR":-1.5},with_prices=True)
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]["priceAndStopAvailable"])
        self.assertFalse(rows[0]["signalCouldHaveBeenIssuedAtEntry"])

    def test_btc_only_summary_has_no_price_or_stop(self):
        rows=m.scan_trades([btc_trade()],"BTCUSDT",
            m.utc("2026-11-15T00:00:00Z"),m.utc(ASOF),
            {"trades":1,"netR":-1.5},with_prices=False)
        self.assertEqual(len(rows),1)
        self.assertFalse(rows[0]["priceAndStopAvailable"])
        self.assertTrue(rows[0]["retrospectiveOnly"])

    def test_last_closed_month_in_future_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"E5B_SOURCE_FROM_FUTURE_OR_PREFREEZE"):
            m.audit(fetcher=readfiles(synthetic_files()),now_utc="2026-11-14T21:00:00Z")

    def test_latest_not_equal_immutable_month_rejected(self):
        files=synthetic_files()
        channel="ETH_V93_SIX_STREAM"
        path=m.CHANNELS[channel]["folder"]+"/snapshots/2026-11.json"
        files[(channel,path)]=files[(channel,path)]+b" "
        with self.assertRaisesRegex(ValueError,"E5B_LATEST_DIFFERS_FROM_IMMUTABLE_MONTH_SNAPSHOT"):
            self.check(files)

    def test_missing_month_witness_rejected(self):
        files=synthetic_files()
        channel="BTC_SOL_V93_HIGH_VOL"
        path=m.CHANNELS[channel]["folder"]+"/snapshots/2026-11.json"
        del files[(channel,path)]
        with self.assertRaisesRegex(ValueError,"TEST_EXPECTED_DOCUMENT_MISSING"):
            self.check(files)

    def test_corrupted_funding_freeze_rejected(self):
        files=synthetic_files()
        channel="BTC_SOL_V93_HIGH_VOL"
        item=btc_snapshot()
        item["freezeUTC"]="2026-11-14T00:00:00Z"
        add_verified_month_synthetic(files,channel,item)
        with self.assertRaisesRegex(ValueError,"E5B_BTC_SOL_FROZEN_SOURCE_OR_SAFETY_MISMATCH"):
            self.check(files)

    def test_archive_hash_backfill_is_caught(self):
        files=synthetic_files()
        channel="ETH_V93_SIX_STREAM"
        item=eth_snapshot()
        item["archiveSHA256"]["BTCUSDT:2026-10"]="f"*64
        add_verified_month_synthetic(files,channel,item)
        with self.assertRaisesRegex(ValueError,"E5B_OLD_SHA256_ARCHIVE_REFERENCE_CHANGED"):
            self.check(files)

    def test_missing_month_archive_declaration_rejected(self):
        files=synthetic_files()
        channel="ETH_V93_SIX_STREAM"
        item=eth_snapshot()
        del item["archiveSHA256"]["SOLUSDT:2026-11"]
        item["verifiedArchives"]-=1
        add_verified_month_synthetic(files,channel,item)
        with self.assertRaisesRegex(ValueError,"E5B_MISSING_OR_EXTRA_ARCHIVE_MONTHS"):
            self.check(files)

    def test_fake_metrics_return_rejected(self):
        files=synthetic_files()
        channel="BTC_SOL_V93_HIGH_VOL"
        item=btc_snapshot()
        item["streams"]["BTCUSDT"]["versions"]["V92_REFERENCE"]["metric"]["25"]["netR"]=-2.0
        add_verified_month_synthetic(files,channel,item)
        with self.assertRaisesRegex(ValueError,"E5B_REPORTED_NET_R25_NOT_RECONCILED"):
            self.check(files)

    def test_unknown_eth_mode_rejected(self):
        files=synthetic_files()
        channel="ETH_V93_SIX_STREAM"
        item=eth_snapshot()
        item["reportedStreams"]["ETH_BOS_EMA_RELAX"]["disabledGates"]=[]
        add_verified_month_synthetic(files,channel,item)
        with self.assertRaisesRegex(ValueError,"E5B_ETH_CANDIDATE_MISMATCH"):
            self.check(files)

    def test_pre_registered_lookahead_violates_freeze(self):
        t=btc_trade();t["watchKnownUTC"]="2026-11-14T01:00:00Z"
        with self.assertRaisesRegex(ValueError,"E5B_LOOKAHEAD_OR_PREFREEZE_TRADE"):
            m.validate_closed_trade(t,"BTCUSDT",m.utc("2026-11-15T00:00:00Z"),
                                    m.utc(ASOF),with_prices=False)

    def test_same_hour_watch_retest_not_eligible(self):
        t=eth_trade();t["watchKnownUTC"]=t["retestKnownUTC"]
        with self.assertRaisesRegex(ValueError,"E5B_LOOKAHEAD_OR_PREFREEZE_TRADE"):
            m.validate_closed_trade(t,"ETHUSDT",m.utc("2026-11-14T00:00:00Z"),
                                    m.utc(ASOF),with_prices=True)

    def test_stop_wrong_side_rejected(self):
        t=eth_trade()
        t["stop"]=101.
        t["targets"]=[99.,98.,97.]
        with self.assertRaisesRegex(ValueError,"E5B_STOP_ON_WRONG_SIDE"):
            m.validate_closed_trade(t,"ETHUSDT",m.utc("2026-11-14T00:00:00Z"),
                                    m.utc(ASOF),with_prices=True)

    def test_manipulated_25bps_net_r_rejected(self):
        t=eth_trade();t["netR25Bps"]=-1.1
        with self.assertRaisesRegex(ValueError,"E5B_FUNDAMENTAL_COST_FORMULA_VIOLATION"):
            m.validate_closed_trade(t,"ETHUSDT",m.utc("2026-11-14T00:00:00Z"),
                                    m.utc(ASOF),with_prices=True)

    def test_long_trade_retained_no_fake_current_entry(self):
        t=eth_trade()
        with self.assertRaisesRegex(ValueError,"E5B_TRADE_OVER_MAX_24H"):
            t["exitKnownUTC"]="2026-11-18T03:00:00Z"
            m.validate_closed_trade(t,"ETHUSDT",m.utc("2026-11-14T00:00:00Z"),
                                    m.utc(ASOF),with_prices=True)

    def test_duplicate_trade_rejected(self):
        t=btc_trade()
        with self.assertRaisesRegex(ValueError,"E5B_DUPLICATE_OR_UNSORTED_ENTRIES"):
            m.scan_trades([t,t],"BTCUSDT",m.utc("2026-11-15T00:00:00Z"),
                          m.utc(ASOF),{"trades":2,"netR":-3.},with_prices=False)

    def test_missing_trade_price_on_eth_rejected(self):
        t=eth_trade();del t["stop"]
        with self.assertRaisesRegex(ValueError,"E5B_CLOSED_TRADE_SCHEMA_CHANGED"):
            m.validate_closed_trade(t,"ETHUSDT",m.utc("2026-11-14T00:00:00Z"),
                                    m.utc(ASOF),with_prices=True)

    def test_one_source_missing_is_not_complete_shadow(self):
        files=synthetic_files(btc=False)
        result=self.check(files)
        self.assertEqual(result["cohortRowsReadAcrossAllVersions"],1)
        self.assertEqual(result["readiness"],
              "NO_COMPLETE_PROSPECTIVE_SOURCE_FOR_SOME_OR_ALL_CHANNELS")
        self.assertEqual(result["uniqueRealTimeEntryOpportunitiesValidated"],0)

if __name__=="__main__":
    import unittest
    unittest.main()
