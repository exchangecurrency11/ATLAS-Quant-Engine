#!/usr/bin/env python3
"""Strict 2026-11-09 15→19 TSİ frozen 4H MACD-free BTC/ETH/SOL review.
BTC and SOL reference data are VERIFIED contemporaneous V7 snapshots.
ETH was not observed by independent ETH V7 then: later Coinalyze history
is truncated at the 15:00 TSİ 4H close, then compared to the 19:00 close.
Research-only, NO ORDERS, no fake historical entry prices.
"""
from datetime import datetime,timezone
from pathlib import Path
import json
import os
from v8_blind4h_review import fetch,frame
import v8_blind4h_review as recon

START="2026-11-09T12:00:00Z"
END="2026-11-09T16:00:00Z"
BTC="BTCUSDT_PERP.A"
ETH="ETHUSDT_PERP.A"
SOL="SOLUSDT_PERP.A"
COINS=[BTC,ETH,SOL]
FRAME_SECS={"1hour":3600,"4hour":14400,"daily":86400}
START_S=int(datetime.fromisoformat(START.replace("Z","+00:00")).timestamp())
END_S=int(datetime.fromisoformat(END.replace("Z","+00:00")).timestamp())

def normalize_snapshot(s, pair):
    if s.get("status")!="VERIFIED_PAPER_OBSERVATION":
        raise ValueError("V7_SNAPSHOT_UNVERIFIED")
    ctx=s["marketContext"][pair]
    result={}
    for tf in ("1hour","4hour","daily"):
        t=ctx["timeframes"][tf]
        result[tf]={
            "lastClosedUTC":t["closeTimeUTC"],
            "candle":t["candle"],
            "indicators":t["indicators"],
        }
    return result

def selected_features(tfs,freeze):
    tfmap={}
    for tf in ("1hour","4hour","daily"):
        x=tfs[tf]
        closed=x["lastClosedUTC"].replace(".000Z","Z")
        expected=(START if tf!="daily" else "2026-11-09T00:00:00Z")
        if closed!=expected:raise ValueError("LEAKED_FUTURE_OR_STALE_"+tf)
        c=x["candle"]["close"]
        q=x["indicators"]
        rsi=q["RSI14"]
        e20=q["EMA20"]
        e50=q["EMA50"]
        e200=q["EMA200"]
        if c<e20 and c<e50 and rsi<50:
            trend="BEARISH"
        elif c>e20 and c>e50 and rsi>50:
            trend="BULLISH"
        else:
            trend="MIXED"
        tfmap[tf]={"closedAtUTC":closed,"close":c,"rsi14":rsi,
                   "ema20":e20,"ema50":e50,"ema200":e200,
                   "trendWithoutMACD":trend,
                   "rsiOversoldUnder35":rsi<35,
                   "ema200Agrees":(
                       c<e200 if trend=="BEARISH" else
                       c>e200 if trend=="BULLISH" else None)}
    direction=(tfmap["4hour"]["trendWithoutMACD"]
               if tfmap["4hour"]["trendWithoutMACD"]==
                  tfmap["daily"]["trendWithoutMACD"] else "MIXED")
    return {"timeframes":tfmap,
            "trendAt15MACDFree":direction,
            "1Hconfirm":tfmap["1hour"]["trendWithoutMACD"]==direction,
            "possibleCountertrendBounceFromRSIOversold":
                tfmap["4hour"]["rsiOversoldUnder35"],
            "notATradeEntry":True}

def compare(frozen,outcome):
    a=frozen["timeframes"]["4hour"]["close"]
    c=outcome["candle"]["close"]
    high=outcome["candle"]["high"]
    low=outcome["candle"]["low"]
    if outcome["lastClosedUTC"].replace(".000Z","Z")!=END:
        raise ValueError("OUTCOME_WRONG_CANDLE")
    observed="UP" if c>a else "DOWN" if c<a else "FLAT"
    predicted=("DOWN" if frozen["trendAt15MACDFree"]=="BEARISH" else
               "UP" if frozen["trendAt15MACDFree"]=="BULLISH" else "NO_PREDICTION")
    return {"next4hOpen":outcome["candle"]["open"],
            "next4hHigh":high,"next4hLow":low,"next4hClose":c,
            "percentChange":round(100*(c/a-1),4),
            "next4hDirection":observed,
            "trendDirectionAsNextCandlePrediction":predicted,
            "predictionMatched":predicted==observed if predicted!="NO_PREDICTION" else None,
            "note":"Single-candle outcome, not trend regime reversal or executed PnL"}

def eth_history(key):
    if not key: raise ValueError("MISSING_COINALYZE_KEY")
    recon.END_TS=END_S
    recon.START_TS=START_S
    candles={}
    proofs={}
    for tf in ("1hour","4hour","daily"):
        b,h=fetch(ETH,tf,END_S,key)
        candles[tf]=b
        proofs[tf]=h
    a=frame(ETH,candles,START_S)
    b=frame(ETH,candles,END_S)
    def unpack(x):
        return {
            tf:{"lastClosedUTC":x["timeframes"][tf]["lastClosedUTC"],
                "candle":{"open":x["timeframes"][tf]["OHLCV"]["o"],
                          "high":x["timeframes"][tf]["OHLCV"]["h"],
                          "low":x["timeframes"][tf]["OHLCV"]["l"],
                          "close":x["timeframes"][tf]["OHLCV"]["c"],
                          "volume":x["timeframes"][tf]["OHLCV"]["v"]},
                "indicators": {
                    "RSI14":x["timeframes"][tf]["indicators"]["RSI14"],
                    "EMA20":x["timeframes"][tf]["indicators"]["EMA20"],
                    "EMA50":x["timeframes"][tf]["indicators"]["EMA50"],
                    "EMA200":x["timeframes"][tf]["indicators"]["EMA200"]}}
            for tf in ("1hour","4hour","daily")}
    return unpack(a),unpack(b),proofs

def run():
    old=json.loads(Path("forward/snapshots/2026-11-09T12-00Z.json").read_text())
    new=json.loads(Path("forward/snapshots/2026-11-09T16-00Z.json").read_text())
    if old.get("targetClosed1HUTC")!=START or new.get("targetClosed1HUTC")!=END:
        raise ValueError("SNAPSHOT_DATE_MISMATCH")
    if old.get("brokerOrders") is not False or new.get("brokerOrders") is not False:
        raise ValueError("SNAPSHOT_NOT_PAPER")
    results={}
    for pair in (BTC,SOL):
        context15=normalize_snapshot(old,pair)
        context19=normalize_snapshot(new,pair)
        frozen=selected_features(context15,START)
        results[pair]={"source":"Contemporaneous verified V7 snapshot",
                       "asOf15RealtimeSnapshotVerified":True,
                       "frozen15":frozen,
                       "outcome19":compare(frozen,context19["4hour"]),
                       "V7New1hBOSAt15":old["marketContext"][pair]["newBOSCount"]}
    key=(os.getenv("ETH_V7_COINALYZE_API_KEY") or os.getenv("COINALYZE_API_KEY") or "").strip()
    e15,e19,sha=eth_history(key)
    frozen=selected_features(e15,START)
    results[ETH]={"source":"Retrospective Coinalyze Binance ETH perpetual OHLCV",
                  "asOf15RealtimeSnapshotVerified":False,
                  "frozen15":frozen,
                  "outcome19":compare(frozen,e19["4hour"]),
                  "sourceSHA256":sha,
                  "V7New1hBOSAt15":None}
    return {"mode":"V8_4H_28H_AGO_MACD_FREE_AUDIT_NO_ORDERS",
            "status":"RETROSPECTIVE_ETH_AND_CONTEMPORANEOUS_BTC_SOL_VERIFIED",
            "asOfUTC":START,"comparedUTC":END,
            "questionAskedAtTSI":"2026-11-10T21:39:49+03:00",
            "asOfContextTSI":"2026-11-09T17:39:49+03:00",
            "MACDusedForAnyDecision":False,
            "realtimePredictionClaim":False,
            "brokerOrders":False,
            "coins":results}

if __name__=="__main__":
    output=Path("forward/v8_blind4h/2026-11-09_no_macd_15-to-19-TSI.json")
    x=run()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(x,indent=2,ensure_ascii=False)+"\n")
    print("28H_PRIOR_MACD_FREE_AUDIT",x["status"])
    for c,j in x["coins"].items():
        print(c,j["frozen15"]["trendAt15MACDFree"],j["outcome19"]["percentChange"],
              "MATCH",j["outcome19"]["predictionMatched"],
              "RSI",j["frozen15"]["timeframes"]["4hour"]["rsi14"])
