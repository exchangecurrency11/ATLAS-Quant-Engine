#!/usr/bin/env python3
"""Reconstruct 2026-11-10 15:00 TSİ 4H assessment BLIND to next 4H close;
then compare the 19:00 TSİ candle for BTC ETH SOL perpetual (paper only).

Reconstructed after both closes from Coinalyze historical OHLCV. This is NOT
evidence of a real-time ETH signal at 15:00; actual ETH V7 feed was unavailable.
For BTC/SOL require reconciliation with persisted as-of 15:00/19:00 snapshots.
"""
import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime,timezone
from pathlib import Path

from market_structure import analyze, candles_from_history
from backtest_retest_long_v4 import indicators, bias, ema

START_CLOSED="2026-11-10T12:00:00Z" # 15:00 TSİ
END_CLOSED="2026-11-10T16:00:00Z"   # 19:00 TSİ
START_TS=1794312000
END_TS=1794326400
PERIODS={"1hour":(3600,15),"4hour":(14400,52),"daily":(86400,270)}
COINS=("BTCUSDT_PERP.A","ETHUSDT_PERP.A","SOLUSDT_PERP.A")
API="https://api.coinalyze.net/v1/ohlcv-history"

def iso(t):return datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def fetch(pair,tf,now,key):
    seconds,days=PERIODS[tf]
    query=urllib.parse.urlencode({"symbols":pair,"interval":tf,
                                  "from":now-days*86400,"to":now+90})
    request=urllib.request.Request(API+"?"+query,
        headers={"api_key":key,"Accept":"application/json",
                 "User-Agent":"V8-blind-4H-reconstruction-no-orders/1.0"})
    with urllib.request.urlopen(request,timeout=35) as stream:
        if stream.status!=200:raise RuntimeError("NON_200_COiNALYZE")
        blob=stream.read(1800000)
    raw=json.loads(blob)
    if not isinstance(raw,list) or len(raw)!=1 or raw[0].get("symbol")!=pair:
        raise ValueError("WRONG_PAIR_"+pair)
    hist=raw[0].get("history")
    if not isinstance(hist,list):raise ValueError("MISSING_HISTORY")
    bars=candles_from_history(hist,tf,as_of=now)
    if len(bars)<254:
        raise ValueError("INSUFFICIENT_CLOSED_BARS_"+pair+"_"+tf+":"+str(len(bars)))
    if any(bars[i]["t"]-bars[i-1]["t"]!=seconds for i in range(1,len(bars))):
        raise ValueError("HISTORY_GAP_"+pair+"_"+tf)
    if bars[-1]["t"]+seconds < (END_TS//seconds)*seconds:
        raise ValueError("STALE_"+pair+"_"+tf)
    return bars,hashlib.sha256(blob).hexdigest()


def snapshot(pair,target):
    base=Path("forward/snapshots")
    path=base/(target.replace(":00Z","-00Z").replace(":","-")+".json")
    raw=json.loads(path.read_text())
    if raw["status"]!="VERIFIED_PAPER_OBSERVATION":
        raise ValueError("BAD_PERSISTED_V7_SNAPSHOT")
    if raw["targetClosed1HUTC"]!=target:
        raise ValueError("WRONG_PERSISTED_TARGET")
    return raw["marketContext"][pair]


def strict_price_match(pair,tf,target,history,reference):
    actual=history[-1]
    candle=reference["timeframes"][tf]["candle"]
    expected={"o":candle["open"],"h":candle["high"],
              "l":candle["low"],"c":candle["close"],"v":candle["volume"]}
    for k,v in expected.items():
        if abs(actual[k]-v)>max(1e-7,abs(v)*1e-6):
            raise ValueError("PERSISTED_V7_PROVIDER_MISMATCH_"+pair+"_"+tf+"_"+k+
                             " "+str(actual[k])+" vs "+str(v))


def confirm_cross_tf(hist,t):
    one=[x for x in hist["1hour"] if x["t"]+3600<=t]
    four=[x for x in hist["4hour"] if x["t"]+14400<=t]
    if not one or not four or four[-1]["t"]+14400!=t:
        raise ValueError("WRONG_4H_TARGET")
    four_h=[x for x in one if t-14400<=x["t"]<t]
    if len(four_h)!=4:
        raise ValueError("INCOMPLETE_1H_SUPPORT")
    calc={"o":four_h[0]["o"],"h":max(x["h"] for x in four_h),
          "l":min(x["l"] for x in four_h),"c":four_h[-1]["c"],
          "v":sum(x["v"] for x in four_h)}
    for k,val in calc.items():
        if abs(four[-1][k]-val)>max(1e-6,abs(val)*2e-6):
            raise ValueError("1H_4H_RECONCILIATION_FAILED_"+k)
    return True


def ind_summary(bars):
    x=indicators(bars)
    if x is None:raise ValueError("INDICATORS_MISSING")
    return {"RSI14":round(x["RSI14"],4),
            "EMA20":round(x["EMA20"],4),
            "EMA50":round(x["EMA50"],4),
            "EMA200":round(ema([z["c"] for z in bars],200),4),
            "MACDHistogram":round(x["hist"],4)}


def frame(pair,history,t):
    visible={tf:[b for b in bars if b["t"]+PERIODS[tf][0]<=t]
             for tf,bars in history.items()}
    if any(len(bars)<250 for bars in visible.values()):
        raise ValueError("NOT_ENOUGH_250_CLOSED_BARS")
    if visible["4hour"][-1]["t"]+14400!=t:
        raise ValueError("STALE_4H_BAR")
    if visible["1hour"][-1]["t"]+3600!=t:
        raise ValueError("STALE_1H_BAR")
    confirm_cross_tf(history,t)
    result={"targetUTC":iso(t),"observedHistoricallyNotRealtime":True,
            "timeframes":{}}
    for tf in ("1hour","4hour","daily"):
        bars=visible[tf]
        result["timeframes"][tf]={
            "lastClosedUTC":iso(bars[-1]["t"]+PERIODS[tf][0]),
            "OHLCV":{k:round(bars[-1][k],7) for k in ("o","h","l","c","v")},
            "indicators":ind_summary(bars),
            "bias":bias(bars)}
    last=visible["4hour"][-1]
    daily=visible["daily"][-1]
    i4=result["timeframes"]["4hour"]["indicators"]
    iD=result["timeframes"]["daily"]["indicators"]
    bearish=(last["c"]<i4["EMA20"] and last["c"]<i4["EMA50"]
             and daily["c"]<iD["EMA20"] and daily["c"]<iD["EMA50"])
    bullish=(last["c"]>i4["EMA20"] and last["c"]>i4["EMA50"]
             and daily["c"]>iD["EMA20"] and daily["c"]>iD["EMA50"])
    frozen_direction=("BEARISH" if bearish else "BULLISH" if bullish else "MIXED")
    # This frozen rule is an outlook, NOT an execution-ready strategy.
    rsi4=i4["RSI14"]
    macd4=i4["MACDHistogram"]
    momentum=("CONFIRMED" if (bearish and rsi4<50 and macd4<0) or
                  (bullish and rsi4>50 and macd4>0) else "MIXED")
    oneStructure=analyze(visible["1hour"][-250:],"1hour",as_of=t)
    freshBOS=[z for z in oneStructure["structure"]
              if z["event"]=="BOS" and z["confirmedAt"]==t]
    structure4=analyze(visible["4hour"][-250:],"4hour",as_of=t)
    fresh4=[z for z in structure4["structure"] if z["confirmedAt"]==t]
    activeOB=[ob for ob in structure4["orderBlocks"]
              if ob["side"]==("bearish" if bearish else "bullish")
              and ob["confirmedAt"]<=t and ob["state"]!="invalidated"]
    activeFVG=[g for g in structure4["fvg"] if g["state"]=="open"]
    prior=visible["4hour"][-49:-1]
    low=min(x["l"] for x in prior)
    high=max(x["h"] for x in prior)
    result["asOfOnly"]={
       "predefined4HDirection":frozen_direction,
       "momentum4H":momentum,
       "cautionOversoldRSI":rsi4<35,
       "frozenDecision":"BEKLE_NO_V7_ENTRY",
       "new1HBOSAtClose":len(freshBOS),
       "new4HStructureEventsAtClose":len(fresh4),
       "last4HLow":last["l"],"last4HHigh":last["h"],
       "last48_4HRangeLow":low,"last48_4HRangeHigh":high,
       "fib382To618Zone":(
           [round(high-.618*(high-low),6),round(high-.382*(high-low),6)]
           if bullish else
           [round(low+.382*(high-low),6),round(low+.618*(high-low),6)] if bearish else None
       ),
       "candidateActiveOBCount":len(activeOB),
       "activeFVGCount":len(activeFVG),
       "notAnOrder":"4H bias is not an executable signal; V7 requires confirmed BOS and later 1H retest."}
    return result


def compare(a,b):
    previous=a["timeframes"]["4hour"]["OHLCV"]
    actual=b["timeframes"]["4hour"]["OHLCV"]
    growth=(actual["c"]/previous["c"]-1)*100
    direction=a["asOfOnly"]["predefined4HDirection"]
    correct=("DOWN" if growth<0 else "UP" if growth>0 else "FLAT")
    predicted=("DOWN" if direction=="BEARISH" else "UP" if direction=="BULLISH" else "NO_DIRECTION")
    return {"previous4HClose":previous["c"],
            "next4HOpen":actual["o"],"next4HHigh":actual["h"],
            "next4HLow":actual["l"],"next4HClose":actual["c"],
            "next4HVolume":actual["v"],
            "priceChangePct":round(growth,4),
            "frozenBiasPredicted":predicted,
            "actualDirection":correct,
            "biasDirectionCorrect":(predicted==correct if predicted!="NO_DIRECTION" else None),
            "nextCloseBelowPriorCandleLow":actual["c"]<previous["l"],
            "noPaperEntryVerified":a["asOfOnly"]["frozenDecision"]=="BEKLE_NO_V7_ENTRY",
            "note":"Retrospective direction assessment, not realized strategy performance"}


def run():
    key=(os.environ.get("ETH_V7_COINALYZE_API_KEY") or
         os.environ.get("COINALYZE_API_KEY") or "").strip()
    if not key:raise ValueError("MISSING_SECRET")
    output={"status":"RETROSPECTIVE_BLIND_CUTOFF_RECONSTRUCTED_NO_ORDERS",
            "source":"Coinalyze Binance USD-M BTC ETH SOL perpetual read-only OHLCV",
            "freezeAtUTC":START_CLOSED,"compareAtUTC":END_CLOSED,
            "ETH15RealtimeAvailability":"SOURCE_UNAVAILABLE_NO_SIGNAL (Binance 451)",
            "notLivePrediction":True,"brokerOrders":False,"productionSystemModified":False,
            "coins":{}}
    now=END_TS
    for pair in COINS:
        hist={}
        hashes={}
        for tf in PERIODS:
            data,sha=fetch(pair,tf,now,key)
            hist[tf]=data
            hashes[tf]=sha
        a=frame(pair,hist,START_TS)
        b=frame(pair,hist,END_TS)
        # BTC/SOL have authentic, timestamped as-of snapshots. Verify both.
        if not pair.startswith("ETH"):
            for t,record in ((START_CLOSED,a),(END_CLOSED,b)):
                ref=snapshot(pair,t)
                for tf in PERIODS:
                    rows=[r for r in hist[tf] if r["t"]+PERIODS[tf][0]<= (START_TS if t==START_CLOSED else END_TS)]
                    strict_price_match(pair,tf,t,rows,ref)
            a["verifiedAgainstContemporaryArchive"]=True
            b["verifiedAgainstContemporaryArchive"]=True
        else:
            a["verifiedAgainstContemporaryArchive"]=False
            b["verifiedAgainstContemporaryArchive"]=False
        output["coins"][pair]={"asOf15TSI":a,"asOf19TSI":b,
                              "comparison":compare(a,b),"sourceSHA256":hashes,
                              "firstCandleHadRealtimeVerifiedSnapshot":not pair.startswith("ETH")}
        print("BLIND_4H",pair,
              output["coins"][pair]["comparison"]["previous4HClose"],
              output["coins"][pair]["comparison"]["next4HClose"],
              output["coins"][pair]["comparison"]["priceChangePct"],flush=True)
    return output


def main():
    p=Path("forward/v8_blind4h/2026-11-10_15-to-19-TSI.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    result=run()
    p.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print("BLIND_4H_REPORT_VERIFIED",p,flush=True)

if __name__=="__main__":
    main()
