"""ETH V9.1 exact-V7, no backfill, paper-only prospective source safety tests."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from v91_eth_prospective_retest import (
    MODE, capture, scoreboard, verify_eth_source, prior_commit_evidence
)
from v91_prospective_retest import path_at
from v7_forward_observer import iso

T=int(datetime(2026,11,12,8,0,tzinfo=timezone.utc).timestamp())
H=3600

def no_trade():
    return {"newWatchAtThisClose":[],"paperTradeExitsObservedAtThisClose":[],
            "currentPaperState":{"activeBOSWatch":None,
                                 "pendingNextOpenPaperEntry":None,
                                 "openHypotheticalPosition":None},
            "diagnosticTotalRollingWindowAlerts":0,
            "diagnosticTotalRollingWindowClosedTrades":0}

def original():
    return {"mode":"ETH_V7_INDEPENDENT_PAPER_FORWARD_NO_ORDERS",
            "status":"VERIFIED_PAPER_OBSERVATION",
            "paperForwardObservation":True,"brokerOrders":False,
            "productionSystemModified":False,
            "symbol":"ETHUSDT_PERP.A",
            "dataSource":"Coinalyze ETHUSDT_PERP.A / Binance perpetual read-only API",
            "observedAtUTC":iso(T+13*60),"targetClosed1HUTC":iso(T),
            "results":{"ETHUSDT_PERP.A":{"V7_signal_filter":no_trade()}},
            "marketContext":{"ETHUSDT_PERP.A":{"timeframes":{
                tf:{"closeTimeUTC":iso(T//secs*secs),
                    "candle":{"open":2000.,"high":2001.,"low":1999.,
                              "close":2000.5,"volume":1000.}}
                for tf,secs in (("1hour",H),("4hour",4*H),("daily",24*H))
            }}}}

def bars():
    return {tf:[{"t":T//sec*sec-sec,"o":2000.,"h":2001.,
                 "l":1999.,"c":2000.5,"v":1000.}]
            for tf,sec in (("1hour",H),("4hour",4*H),("daily",24*H))}

def empty_snapshot(t):
    return {"mode":MODE,"targetClosed1HUTC":iso(t),
            "capturedAtUTC":iso(t+20*60),
            "verifiedSourceAndExactV7Replay":True,
            "noBrokerOrders":True,"noUserNotifications":True,
            "originalV7":no_trade(),"max4hRetest":no_trade()}

class ETHV91Tests(unittest.TestCase):
    def test_current_verified_exact_v7_hour_and_replay(self):
        with tempfile.TemporaryDirectory() as d, \
             patch("v91_eth_prospective_retest.validate_sources",
                   return_value=(bars(),{"1hour":"a","4hour":"b","daily":"c"},
                                 {"1H_matches_4H":5,"1H_matches_daily":5})), \
             patch("v91_eth_prospective_retest.replay_pair",
                   return_value={"status":"PAPER_BACKTEST_NOT_LIVE"}) as replay, \
             patch("v91_eth_prospective_retest.latest_events",
                   return_value=no_trade()):
            snap,path=capture(original(),{},now=T+15*60,folder=d)
            self.assertEqual(replay.call_count,2)
            self.assertEqual(snap["sourceClose1H"],2000.5)
            self.assertTrue(snap["verifiedSourceAndExactV7Replay"])
            self.assertTrue(snap["noUserNotifications"])
            self.assertTrue(snap["noBrokerOrders"])
            self.assertTrue(snap["entryAtNextOpenIsHistoricalUnverifiedFill"])
            self.assertFalse(snap["independentBinanceMarketTruthEstablished"])
            self.assertFalse(path.exists())
            out=scoreboard(d,current=snap)
            self.assertEqual(out["savedDistinctVerifiedHours"],1)
            self.assertEqual(out["results"]["ETH_V91" if False else "V91_RETEST_MAX4H"]["eligibleClosedPaperTrades"],0)
            self.assertEqual(out["realTimeExecutableEntryCountProven"],0)

    def test_coinalyze_instrument_only_and_source_timestamp(self):
        o=original()
        o["dataSource"]="Binance official USD-M futures public GET /fapi/v1/klines"
        with self.assertRaisesRegex(ValueError,"ETH_V91_MISSING_VERIFIED"):
            verify_eth_source(o,bars(),T)
        o=original();o["targetClosed1HUTC"]=iso(T-H)
        with self.assertRaisesRegex(ValueError,"ETH_V91_MISSING_VERIFIED"):
            verify_eth_source(o,bars(),T)
        o=original();o["marketContext"]["ETHUSDT_PERP.A"]["timeframes"]["4hour"]["closeTimeUTC"]=iso(T-4*H)
        with self.assertRaisesRegex(ValueError,"ETH_V91_TIMEFRAME_CLOSE_MISMATCH"):
            verify_eth_source(o,bars(),T)

    def test_mismatched_price_volume_fail_closed(self):
        for tf,key,val in [("1hour","c",1980.),("4hour","v",2000.),
                           ("daily","o",2011.)]:
            with self.subTest(tf=tf,key=key):
                x=bars();x[tf][0][key]=val
                with self.assertRaisesRegex(ValueError,"PARITY_FAILED"):
                    verify_eth_source(original(),x,T)

    def test_v7_signal_replay_mismatch_fails(self):
        a=original()
        a["results"]["ETHUSDT_PERP.A"]["V7_signal_filter"]["newWatchAtThisClose"]=[{"side":"bullish"}]
        with tempfile.TemporaryDirectory() as d, \
             patch("v91_eth_prospective_retest.validate_sources",
                   return_value=(bars(),{},{})), \
             patch("v91_eth_prospective_retest.replay_pair",
                   return_value={"status":"PAPER_BACKTEST_NOT_LIVE"}), \
             patch("v91_eth_prospective_retest.latest_events",
                   return_value=no_trade()):
            with self.assertRaisesRegex(ValueError,"PARITY_FAILED"):
                capture(a,{},now=T+15*60,folder=d)

    def test_not_current_or_posthoc_capture_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,"ETH_V91_NOT_CURRENT"):
                capture(original(),{},now=T+5*60,folder=d)
            late=original()
            late["observedAtUTC"]=iso(T+40*60)
            with self.assertRaisesRegex(ValueError,"NOT_CONTEMPORANEOUS"):
                capture(late,{},now=T+15*60,folder=d)

    def test_scorecard_never_counts_uncommitted_paper_exit(self):
        trade={"watchKnownUTC":T-H,"retestKnownUTC":T,
               "entryOpenUTC":T,"exitKnownUTC":T+H,
               "entry":2000.,"stop":1990.,"risk":10.,
               "side":"bullish","netRIllustrative":0.4}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            old=empty_snapshot(T)
            pending={k:trade[k] for k in ("watchKnownUTC","retestKnownUTC","side","stop")}
            old["max4hRetest"]["currentPaperState"]["pendingNextOpenPaperEntry"]=pending
            path_at(root,T).write_text(json.dumps(old))
            latest=empty_snapshot(T+H)
            latest["max4hRetest"]["paperTradeExitsObservedAtThisClose"]=[trade]
            with patch("v91_eth_prospective_retest._first_commit_epoch",return_value=None):
                score=scoreboard(root,current=latest)
            self.assertEqual(score["results"]["V91_RETEST_MAX4H"]["eligibleClosedPaperTrades"],0)
            self.assertEqual(len(score["excludedUnprovenExits"]["V91_RETEST_MAX4H"]),1)
            with patch("v91_eth_prospective_retest._first_commit_epoch",return_value=T+22*60):
                score=scoreboard(root,current=latest)
            self.assertEqual(score["results"]["V91_RETEST_MAX4H"]["eligibleClosedPaperTrades"],1)
            self.assertEqual(score["results"]["V91_RETEST_MAX4H"]["totalNetR9BpsPerSide"],.4)
            self.assertEqual(score["realTimeExecutableEntryCountProven"],0)

    def test_existing_hour_rejected_from_scoreboard(self):
        with tempfile.TemporaryDirectory() as d:
            path_at(d,T).write_text(json.dumps(empty_snapshot(T)))
            with self.assertRaisesRegex(ValueError,"DUPLICATE_IMMUTABLE"):
                scoreboard(d,current=empty_snapshot(T))

if __name__=="__main__":
    unittest.main()
