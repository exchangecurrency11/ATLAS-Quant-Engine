"""V9.1 prospective shadow: reject stale source, preserve V7, require sealed paper retest."""
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from v91_prospective_retest import (
    MODE,HOUR,STRATEGIES,path_at,capture,safe_trade,scoreboard, _entry_evidence,
    current_hour_capture_window)

END=int(datetime(2026,11,11,16,0,tzinfo=timezone.utc).timestamp())


def state(pending=None):
    return {"activeBOSWatch":None,"pendingNextOpenPaperEntry":pending,
            "openHypotheticalPosition":None}


def row(pending=None,exits=None):
    return {"newWatchAtThisClose":[],"paperTradeExitsObservedAtThisClose":exits or [],
            "currentPaperState":state(pending),
            "diagnosticTotalRollingWindowAlerts":0,
            "diagnosticTotalRollingWindowClosedTrades":0}


def sample_original():
    return {
        "status":"VERIFIED_PAPER_OBSERVATION","brokerOrders":False,
        "targetClosed1HUTC":"2026-11-11T16:00:00Z",
        "observedAtUTC":"2026-11-11T16:19:00Z",
        "results":{s+"_PERP.A":{"V7_signal_filter":row()} for s in ("BTCUSDT","SOLUSDT")},
        "marketContext":{s+"_PERP.A":{"timeframes":{
            tf:{"closeTimeUTC":("2026-11-11T00:00:00Z" if tf=="daily"
                                 else "2026-11-11T16:00:00Z"),
                "candle":{"open":100.,"high":101.,"low":99.,"close":100.,"volume":700.}}
            for tf in ("1hour","4hour","daily")}}
            for s in ("BTCUSDT","SOLUSDT")}
    }


def sample_parsed():
    starts={"1hour":END-HOUR,"4hour":END-4*HOUR,"daily":END-40*HOUR}
    return {tf:{s+"_PERP.A":[{"t":starts[tf],"o":100.,"h":101.,
                              "l":99.,"c":100.,"v":700.}]
                for s in ("BTCUSDT","SOLUSDT")} for tf in starts}


def example_trade(ret=END,exit_time=END+HOUR):
    return {"watchKnownUTC":ret-HOUR,"retestKnownUTC":ret,
            "entryOpenUTC":ret,"exitKnownUTC":exit_time,
            "side":"bullish","entry":101.,"stop":99.,"risk":2.,
            "netRIllustrative":0.7}


def snapshot_at(t, *,candidate=None,baseline=None,pending=None):
    from v7_forward_observer import iso
    c = candidate or []
    b = baseline or []
    return {"mode":MODE,"targetClosed1HUTC":iso(t),
        "capturedAtUTC":iso(t+34*60),"sourceVerifiedSameHour":True,
        "V7SnapshotAndIndependentRecomputeExactMatch":True,
        "assets":{s:{"originalV7":row(pending if s=="SOLUSDT" else None,b if s=="SOLUSDT" else []),
                    "max4hRetest":row(pending if s=="SOLUSDT" else None,c if s=="SOLUSDT" else [])}
                  for s in ("BTCUSDT","SOLUSDT")}}


class V91ProspectiveTests(unittest.TestCase):
    def test_capture_window_allows_last_minute_but_never_next_hour(self):
        self.assertTrue(current_hour_capture_window(END,END+3599))
        self.assertTrue(current_hour_capture_window(END,END+12*60))
        self.assertFalse(current_hour_capture_window(END,END+11*60+59))
        self.assertFalse(current_hour_capture_window(END,END+3600))

    def test_exit_timestamp_must_equal_exact_current_close(self):
        t=example_trade()
        self.assertTrue(safe_trade(t,END+HOUR))
        with self.assertRaises(ValueError):
            safe_trade(t,END+2*HOUR)

    def test_current_capture_requires_original_and_closed_hour_source_parity(self):
        orig=sample_original()
        with tempfile.TemporaryDirectory() as d, \
             patch("v91_prospective_retest.validate_inputs",return_value=sample_parsed()), \
             patch("v91_prospective_retest.replay_pair",return_value={"status":"PAPER_BACKTEST_NOT_LIVE"}) as replay, \
             patch("v91_prospective_retest.latest_events",return_value=row()):
            snap,_=capture(orig,{"checkedAtUTC":"2026-11-11T16:01:00Z"},{},
                           now=END+30*60,folder=d)
            self.assertEqual(replay.call_count,4)
            self.assertTrue(snap["V7SnapshotAndIndependentRecomputeExactMatch"])
            self.assertTrue(snap["noBrokerOrders"])
            self.assertTrue(snap["priceAndVolumeValidatedAgainstOriginalV7For1H4HDaily"])
            self.assertEqual(set(snap["originalV7PriceVolumeParities"]),{"BTCUSDT","SOLUSDT"})
            self.assertEqual(set(snap["originalV7PriceVolumeParities"]["SOLUSDT"]),
                             {"1hour","4hour","daily"})
            self.assertTrue(snap["mainWorkerDataSameCoinalyzeProviderNotIndependentBinanceProof"])
            self.assertTrue(snap["hypotheticalNextOpenAtRetestClosePrecedesObservation"])
            self.assertTrue(snap["unverifiedCoinalyzeTXOIFundingNotUsedAsV91EntryFilter"])
            self.assertEqual(snap["retentionRuleHours"],{"V7_ORIGINAL":6,"V91_RETEST_MAX4H":4})

    def test_reject_changed_ohlc_on_any_timeframe_or_symbol(self):
        from v91_prospective_retest import verify_candle_quality_against_v7
        baseline=sample_original()
        for tf in ("1hour","4hour","daily"):
            for symbol in ("BTCUSDT_PERP.A","SOLUSDT_PERP.A"):
                for key in ("o","h","l","c"):
                    with self.subTest(tf=tf,symbol=symbol,field=key):
                        parsed=sample_parsed()
                        parsed[tf][symbol][-1][key]=102. if key!="l" else 98.
                        with self.assertRaisesRegex(ValueError,"SOURCE_OHLCV_PARITY_REJECTED"):
                            verify_candle_quality_against_v7(baseline,parsed,END)

    def test_reject_volume_mismatch_and_stale_daily(self):
        from v91_prospective_retest import verify_candle_quality_against_v7
        original=sample_original()
        p=sample_parsed()
        p["4hour"]["SOLUSDT_PERP.A"][-1]["v"]=720.
        with self.assertRaisesRegex(ValueError,"SOURCE_OHLCV_PARITY_REJECTED"):
            verify_candle_quality_against_v7(original,p,END)
        p=sample_parsed()
        p["daily"]["BTCUSDT_PERP.A"][-1]["t"]-=HOUR
        with self.assertRaisesRegex(ValueError,"CLOSE_TIME_MISMATCH"):
            verify_candle_quality_against_v7(original,p,END)

    def test_reject_original_4h_reference_with_mismatched_timestamp(self):
        from v91_prospective_retest import verify_candle_quality_against_v7
        original=sample_original()
        original["marketContext"]["SOLUSDT_PERP.A"]["timeframes"]["4hour"]["closeTimeUTC"]="2026-11-11T12:00:00Z"
        with self.assertRaisesRegex(ValueError,"CLOSE_TIME_MISMATCH"):
            verify_candle_quality_against_v7(original,sample_parsed(),END)

    def test_volume_tolerance_is_only_integrity_not_exchange_proof(self):
        from v91_prospective_retest import verify_candle_quality_against_v7
        original=sample_original()
        p=sample_parsed()
        p["4hour"]["BTCUSDT_PERP.A"][-1]["v"]=703.
        report=verify_candle_quality_against_v7(original,p,END)
        self.assertLess(report["BTCUSDT"]["4hour"]["relativeDifferences"]["volume"]["relativeDifference"],0.005)
        self.assertFalse(report["BTCUSDT"]["4hour"]["twoIndependentBinanceExchangeSourcesProven"])

    def test_no_stale_or_posthoc_v7_snapshot(self):
        orig=sample_original()
        orig["observedAtUTC"]="2026-11-11T17:00:00Z"
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,"SOURCE_NOT_SEALED"):
                capture(orig,{}, {},now=END+30*60,folder=d)

    def test_original_v7_state_difference_fail_closed(self):
        orig=sample_original()
        orig["results"]["BTCUSDT_PERP.A"]["V7_signal_filter"]["newWatchAtThisClose"]=[{"side":"bullish"}]
        with tempfile.TemporaryDirectory() as d, \
             patch("v91_prospective_retest.validate_inputs",return_value=sample_parsed()), \
             patch("v91_prospective_retest.replay_pair",return_value={"status":"PAPER_BACKTEST_NOT_LIVE"}), \
             patch("v91_prospective_retest.latest_events",return_value=row()):
            with self.assertRaisesRegex(ValueError,"PARITY_FAILED"):
                capture(orig,{"checkedAtUTC":"2026-11-11T16:01:00Z"},{},
                        now=END+30*60,folder=d)

    def test_prior_committed_retest_required_for_counting_paper_exit(self):
        trade=example_trade()
        pending={k:trade[k] for k in ("retestKnownUTC","watchKnownUTC","side","stop")}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            before=snapshot_at(END,pending=pending)
            p=path_at(root,END)
            p.write_text(json.dumps(before))
            current=snapshot_at(END+HOUR,candidate=[trade])
            with patch("v91_prospective_retest._first_commit_epoch",return_value=END+36*60):
                j=scoreboard(root,current=current)
            self.assertEqual(j["results"]["SOLUSDT"]["V91_RETEST_MAX4H"]["eligibleClosedPaperTrades"],1)
            self.assertEqual(j["results"]["SOLUSDT"]["V91_RETEST_MAX4H"]["totalNetR9BpsPerSide"],0.7)
            self.assertEqual(j["results"]["SOLUSDT"]["V7_ORIGINAL"]["eligibleClosedPaperTrades"],0)
            self.assertEqual(j["realTimeExecutableEntryCountProven"],0)
            self.assertTrue(j["delayedSignalPublicationNotModeledInNetR"])
            self.assertTrue(j["unverifiedDerivativeFieldsNeverBecomeEntryVeto"])
            with patch("v91_prospective_retest._first_commit_epoch",return_value=None):
                j=scoreboard(root,current=current)
            self.assertEqual(j["results"]["SOLUSDT"]["V91_RETEST_MAX4H"]["eligibleClosedPaperTrades"],0)
            self.assertEqual(len(j["excludedUnsealedOrUnprovenPaperExits"]["SOLUSDT"]["V91_RETEST_MAX4H"]),1)

    def test_missing_prior_hour_never_backfilled_as_win(self):
        t=example_trade()
        with tempfile.TemporaryDirectory() as d:
            j=scoreboard(d,current=snapshot_at(END+HOUR,candidate=[t]))
        self.assertEqual(j["results"]["SOLUSDT"]["V91_RETEST_MAX4H"]["eligibleClosedPaperTrades"],0)
        self.assertEqual(j["savedDistinctVerifiedHours"],1)


    def test_retest_features_are_descriptive_not_a_strong_gate(self):
        from v91_prospective_retest import retest_diagnostics
        p={"side":"bullish","level":99.8,"watchKnownUTC":END-HOUR,
           "retestKnownUTC":END,"stop":98.0}
        r=row(pending=p)
        bars=[{"t":END-HOUR,"o":100.,"h":101.,"l":99.,"c":100.,"v":100.}]
        ret={"passed":False,"reasons":["V91_DIRECTIONAL_BODY_WEAK"],
             "features":{"retestClosedAtUTC":END,
                         "directionalBody_ATR":0.03,
                         "retestRelativeVolume20":0.7}}
        with patch("v91_prospective_retest.strong_retest",return_value=ret) as f:
            d=retest_diagnostics(r,bars,END)
            self.assertEqual(f.call_count,1)
            self.assertTrue(d["observationOnlyNoVeto"])
            self.assertFalse(d["strongGateWouldPassButIsNotActive"])
            self.assertEqual(d["closed1HRetraceFeatures"]["directionalBody_ATR"],.03)
            self.assertEqual(r["currentPaperState"]["pendingNextOpenPaperEntry"],p)

    def test_retest_features_fail_closed_when_record_is_not_this_hour(self):
        from v91_prospective_retest import retest_diagnostics
        p={"side":"bullish","level":99.8,"watchKnownUTC":END-2*HOUR,
           "retestKnownUTC":END-HOUR}
        with self.assertRaisesRegex(ValueError,"DIAGNOSTIC_RETEST_TIMELINE_INVALID"):
            retest_diagnostics(row(pending=p),
                [{"t":END-HOUR,"c":100.}],END)


    def test_unavailable_strong_retest_diagnostic_does_not_delete_paper_entry(self):
        from v91_prospective_retest import retest_diagnostics
        pending={"side":"bullish","level":99.8,"watchKnownUTC":END-HOUR,
                 "retestKnownUTC":END,"stop":98.0}
        ret={"passed":False,"reasons":["V91_RETEST_NO_REFERENCE_VOLUME"],
             "features":{}}
        with patch("v91_prospective_retest.strong_retest",return_value=ret):
            d=retest_diagnostics(row(pending),[{"t":END-HOUR}],END)
        self.assertEqual(d["status"],"DIAGNOSTIC_UNAVAILABLE_NO_ENTRY_VETO")
        self.assertTrue(d["observationOnlyNoVeto"])
        self.assertIsNone(d["strongGateWouldPassButIsNotActive"])
        self.assertIsNone(d["closed1HRetraceFeatures"])

    def test_strong_retest_raises_but_v7_paper_state_kept(self):
        from v91_prospective_retest import retest_diagnostics
        pending={"side":"bearish","level":99.8,"watchKnownUTC":END-HOUR,
                 "retestKnownUTC":END,"stop":102.}
        with patch("v91_prospective_retest.strong_retest",side_effect=ValueError("bad optional volume")):
            d=retest_diagnostics(row(pending),[{"t":END-HOUR}],END)
        self.assertEqual(d["reasonCode"],"ValueError")
        self.assertTrue(d["observationOnlyNoVeto"])

    def test_existing_hour_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p=path_at(d,END)
            p.write_text(json.dumps(snapshot_at(END)))
            with self.assertRaises(ValueError):
                scoreboard(d,current=snapshot_at(END))

if __name__=="__main__":
    unittest.main()
