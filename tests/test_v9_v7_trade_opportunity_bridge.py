"""V7 strategy primary and V9 4H own-body only secondary read-only research."""
import unittest,copy,tempfile,json
from pathlib import Path
from datetime import datetime,timezone
from test_v9_next4h_paper_outcome_score import forecast
from v9_v7_trade_opportunity_bridge import (
   asof_overlay,verify_saved_forecast,score_trade_subset,FOUR,HOUR,iso,ts,CANDIDATES)
T=ts("2026-11-11T12:00:00Z")
H=T+HOUR


def fixtures():
    v7={
       "status":"VERIFIED_PAPER_OBSERVATION",
       "brokerOrders":False,
       "targetClosed1HUTC":iso(H),
       "observedAtUTC":iso(H+13*60),
       "results":{},
       "marketContext":{}}
    hour={
       "status":"V9_HOURLY_OBSERVATION_VERIFIED_PAPER_CONTEXT_ONLY",
       "realOrders":False,
       "closed1HUTC":iso(H),
       "observedAtUTC":iso(H+18*60),
       "assets":{s:{"1H":{"OHLCV":{"close":100.},"context":"BEARISH"}}
                 for s in ("BTCUSDT","ETHUSDT","SOLUSDT")}}
    for s in CANDIDATES:
        ref=s+"_PERP.A"
        v7["results"][ref]={"V7_signal_filter":{
           "newWatchAtThisClose":[],
           "paperTradeExitsObservedAtThisClose":[],
           "currentPaperState":{"activeBOSWatch":None,
                                "pendingNextOpenPaperEntry":None,
                                "openHypotheticalPosition":None}}}
        v7["marketContext"][ref]={
           "timeframes":{"1hour":{"candle":{"close":100.}},
                         "4hour":{"directionVotes":{"label":"bearish"}},
                         "daily":{"directionVotes":{"label":"bearish"}}}}
    return v7,hour


def sealed():
    f=forecast()
    f["target4HStartUTC"]=iso(T)
    f["target4HEndUTC"]=iso(T+FOUR)
    f["decisionCapturedUTC"]=iso(T-600)
    return f


class V9V7BridgeTests(unittest.TestCase):
    def test_no_new_v7_signal_and_no_v9_lock_is_explicit_no_opportunity(self):
        v7,h=fixtures()
        r=asof_overlay(v7,h)
        self.assertEqual(r["original4HForecastLockStatus"],
                         "NO_ORIGINAL_GIT_SEALED_V9_4H_FORECAST")
        self.assertTrue(r["V7BOSRetestStrategyIsPrimary"])
        self.assertTrue(r["4HOwnColorIsSecondaryNotProfitTarget"])
        self.assertTrue(r["noNotifications"] and r["noOrders"])
        for s in CANDIDATES:
            self.assertEqual(r["contracts"][s]["originalV7NewWatchesAtThisClose"],0)
            self.assertIsNone(r["contracts"][s]["v9OriginalSealed4HColorContext"])
            self.assertEqual(r["contracts"][s]["eventOverlayOnly"],[])

    def test_v7_watch_survives_missing_4h_forecast(self):
        v7,h=fixtures()
        v7["results"]["SOLUSDT_PERP.A"]["V7_signal_filter"][
           "newWatchAtThisClose"]=[{"knownUTC":H,"side":"bullish"}]
        r=asof_overlay(v7,h)
        sol=r["contracts"]["SOLUSDT"]
        self.assertEqual(sol["originalV7NewWatchesAtThisClose"],1)
        self.assertIsNone(sol["eventOverlayOnly"][0][
                          "v9Primary94DirectionalAgreement"])
        self.assertTrue(sol["noOriginalV7WatchOrRetestRewritten"])

    def test_4h_lock_only_with_github_evidence_before_start(self):
        f=sealed()
        self.assertEqual(verify_saved_forecast(f,git_first_commit_time=T-300)["status"],
                         "ORIGINAL_LOCKED_BEFORE_START_FORECAST")
        self.assertEqual(verify_saved_forecast(f,git_first_commit_time=T+1)["status"],
                         "FORECAST_GIT_COMMIT_NOT_BEFORE_4H_START")
        self.assertEqual(verify_saved_forecast(f)["status"],
                         "NO_PROVEN_GIT_PRESTART_COMMIT")
        v7,h=fixtures()
        v7["results"]["BTCUSDT_PERP.A"]["V7_signal_filter"][
            "newWatchAtThisClose"]=[{"knownUTC":H,"side":"bullish"}]
        r=asof_overlay(v7,h,f,T-300)
        self.assertEqual(r["original4HForecastLockStatus"],
                         "ORIGINAL_LOCKED_BEFORE_START_FORECAST")
        self.assertTrue(r["contracts"]["BTCUSDT"]["eventOverlayOnly"][
                        0]["v9Primary94DirectionalAgreement"])
        late=asof_overlay(v7,h,f,T+10)
        self.assertIsNone(late["contracts"]["BTCUSDT"][
                          "v9OriginalSealed4HColorContext"])
        self.assertEqual(late["contracts"]["BTCUSDT"][
                          "originalV7NewWatchesAtThisClose"],1)

    def test_v7_v9_timestamp_or_price_disagreement_fails(self):
        v7,h=fixtures()
        h["assets"]["SOLUSDT"]["1H"]["OHLCV"]["close"]=110.
        with self.assertRaisesRegex(ValueError,"PRICE_SOURCE_MISMATCH"):
            asof_overlay(v7,h)
        v7,h=fixtures();h["closed1HUTC"]=iso(H-HOUR)
        with self.assertRaisesRegex(ValueError,"NOT_IDENTICAL"):
            asof_overlay(v7,h)

    def test_real_v7_paper_exits_only_not_fake_profit_without_trades(self):
        with tempfile.TemporaryDirectory() as temp:
            v=Path(temp)/"v7";v.mkdir()
            p=Path(temp)/"v9";p.mkdir()
            x=score_trade_subset(v,p,lambda file:None)
            self.assertEqual(x["originalV7TradeCount"],0)
            self.assertIsNone(x["originalV7PaperTradeMetrics"]["SOLUSDT"][
                              "meanNetRAt9bpsPerSide"])
            self.assertTrue(x["gatingWithoutFullStrategyReplayCannotProveHigherProfit"])

    def test_original_v7_one_trade_netR_and_cost_stress_not_replaced_by_4h_color(self):
        v7,h=fixtures()
        t={"side":"bullish","entryOpenUTC":H-5*HOUR,
           "retestKnownUTC":H-6*HOUR,"exitKnownUTC":H,
           "entry":100.,"risk":2.,"netRIllustrative":0.7}
        v7["results"]["SOLUSDT_PERP.A"]["V7_signal_filter"][
           "paperTradeExitsObservedAtThisClose"]=[t]
        with tempfile.TemporaryDirectory() as temp:
            v=Path(temp)/"v7";v.mkdir()
            p=Path(temp)/"v9";p.mkdir()
            (v/"2026-11-11T13-00Z.json").write_text(json.dumps(v7))
            x=score_trade_subset(v,p,lambda file:None)
            sol=x["originalV7PaperTradeMetrics"]["SOLUSDT"]
            self.assertEqual(sol["completedV7OriginalPaperTrades"],1)
            self.assertEqual(sol["meanNetRAt9bpsPerSide"],.7)
            self.assertEqual(sol["meanNetRStressAt25bpsPerSide"],.54)
            self.assertEqual(x["gatedSubsetCount"],0)
            self.assertTrue(x["unobservedCounterfactualTradesMustNotBeFilledIn"])

if __name__=="__main__":
    unittest.main()
