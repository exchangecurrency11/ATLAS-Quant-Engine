"""V9 close interpretation separate from prestart forecast, strict timestamps."""
import copy
import unittest
from datetime import datetime,timezone
from v9_daily_4h_close_commentary import map_sources,ts,ASSETS


def candle(o=100,c=99):
    return {"open":o,"high":o+1,"low":c-1,
            "close":c,"volume":100,"volumeChangePct":-20.}


def ind():
    return {"RSI14":28.,"EMA20":104.,"EMA50":110.,
            "EMA200":120.,"MACDHistogram":-3.}


def sources():
    dat={"ok":True,"provider":"Coinalyze","results":[]}
    struc={"method":"Heuristic swing pivots, BOS/CHoCH",
           "results":[]}
    eth={"status":"VERIFIED_PAPER_OBSERVATION",
         "symbol":"ETHUSDT_PERP.A","brokerOrders":False,
         "crossTimeframeOHLCVVerifiedLast5":{
            "1H_matches_4H":5,"1H_matches_daily":5},
         "marketContext":{"ETHUSDT_PERP.A":{"timeframes":{}}}}
    dates={"1hour":"2026-11-10T21:00:00Z","4hour":"2026-11-10T20:00:00Z",
           "daily":"2026-11-10T00:00:00Z"}
    for t in ("1hour","4hour","daily"):
        for name,sym in ASSETS.items():
            row={"status":"READY","symbol":sym,"interval":t,
                 "closeTimeUTC":dates[t],
                 "candle":candle(),"indicators":ind()}
            if name=="ETH":
                eth["marketContext"]["ETHUSDT_PERP.A"]["timeframes"][t]=row
            else:
                dat["results"].append(row)
                struc["results"].append({
                   "symbol":sym,"interval":t,"status":"READY",
                   "lastCloseTimeUTC":dates[t],
                   "structure":[{"at":ts(dates[t]),"event":"BOS",
                                 "direction":"bearish","brokenLevel":95},
                                {"at":ts(dates[t])+3600,"event":"BOS",
                                 "direction":"bullish","brokenLevel":105}],
                   "candidateOrderBlocks":[{"side":"bearish",
                     "confirmedAt":ts(dates[t])+3600,
                     "body":{"low":101,"high":105},"state":"fresh"}],
                   "openFVG":[{"formedAt":ts(dates[t])-3600,
                                 "low":100,"high":110,"side":"bearish"}],
                   "liquidity":[{"kind":"equal_lows","level":98}]})
    return dat,eth,struc


class V9CloseReportTests(unittest.TestCase):
    def test_all_assets_daily_and_4h_cannot_infer_next_direction(self):
        args=sources()
        x=map_sources(*args)
        self.assertEqual(set(x["assets"]),{"BTC","ETH","SOL"})
        self.assertTrue(x["preservePreviousFrozen4HPreStartPredictions"])
        self.assertTrue(x["commentaryNotAnEntrySignal"])
        self.assertTrue(x["noRealOrders"])
        self.assertEqual(x["assets"]["SOL"]["timeframes"]["4hour"]["candleBody"],"RED")
        self.assertEqual(x["assets"]["SOL"]["combinedInterpretation"]["caution"],"Oversold bounce")
        self.assertFalse(x["assets"]["ETH"]["structureCommentary"]["available"])
        self.assertEqual(len(x["assets"]["BTC"]["structureCommentary"]["nearestCandidateOB"]),0)
        self.assertEqual(x["assets"]["BTC"]["structureCommentary"]["mostRecentBOSorCHoCH"]["direction"],"bearish")

    def test_reject_source_lag_for_eth(self):
        m,e,s=sources()
        e["marketContext"]["ETHUSDT_PERP.A"]["timeframes"]["4hour"]["closeTimeUTC"]="2026-11-10T16:00:00Z"
        with self.assertRaisesRegex(ValueError,"TIMESTAMPS_UNALIGNED"):
            map_sources(m,e,s)

    def test_reject_different_structure_close(self):
        m,e,s=sources()
        for r in s["results"]:
            if r["symbol"]=="BTCUSDT_PERP.A" and r["interval"]=="4hour":
                r["lastCloseTimeUTC"]="2026-11-10T16:00:00Z"
        with self.assertRaisesRegex(ValueError,"STRUCTURE_CLOSE_MISMATCH"):
            map_sources(m,e,s)

    def test_reject_incomplete_eth_parity(self):
        m,e,s=sources()
        e["crossTimeframeOHLCVVerifiedLast5"]["1H_matches_4H"]=4
        with self.assertRaisesRegex(ValueError,"5_OF_5"):
            map_sources(m,e,s)

    def test_never_use_a_future_daily_candle(self):
        m,e,s=sources()
        for r in m["results"]:
            if r["interval"]=="daily":
                r["closeTimeUTC"]="2026-11-11T00:00:00Z"
        e["marketContext"]["ETHUSDT_PERP.A"]["timeframes"]["daily"]["closeTimeUTC"]="2026-11-11T00:00:00Z"
        for r in s["results"]:
            if r["interval"]=="daily":
                r["lastCloseTimeUTC"]="2026-11-11T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"FUTURE_DAILY"):
            map_sources(m,e,s)


if __name__=="__main__":
    unittest.main()
