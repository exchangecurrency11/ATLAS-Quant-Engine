#!/usr/bin/env python3
"""V8.5 SOL perpetual NOW: auditable close-only shadow decision, never orders.

A single one-shot historical-present snapshot from independent Coinalyze
SOLUSDT_PERP.A 1H /4H / Daily. It refuses stale, missing or cross-TF
inconsistent data, only displays the V8.5 already-frozen decision. This
one-shot status is NOT an approval to automate or execute trades.
"""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json,os,math
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from sol_v85_dual_regime_research import (
    HOUR,FOUR,DAY,iso,rolling_sma,rolling_rsi14,
    features_at_4h_close,first_1h_confirm_index,simulate_trade,
    EXPLORATORY_SCORE_THRESHOLD)
from market_structure import candles_from_history

SYMBOL="SOLUSDT_PERP.A"
URL="https://api.coinalyze.net/v1/ohlcv-history"
INTERVAL={"1hour":HOUR,"4hour":FOUR,"daily":DAY}


def acquire(key,tf,current):
    need={"1hour":17,"4hour":150,"daily":315}[tf]
    params=urlencode({"symbols":SYMBOL,"interval":tf,
                      "from":current-need*DAY,"to":current+40})
    req=Request(URL+"?"+params,headers={
        "api_key":key,"User-Agent":"V85-SOL-closed-shadow-audit/1.0",
        "Accept":"application/json"})
    with urlopen(req,timeout=45) as response:
        if response.status!=200:raise ValueError("API_NON200_"+tf)
        raw=response.read(2800000)
    payload=json.loads(raw)
    if not isinstance(payload,list) or len(payload)!=1 or payload[0].get("symbol")!=SYMBOL:
        raise ValueError("WRONG_SOL_PERPETUAL_CONTRACT_"+tf)
    bars=candles_from_history(payload[0].get("history",[]),tf,as_of=current)
    if not bars or len(bars)<{"1hour":200,"4hour":600,"daily":220}[tf]:
        raise ValueError("INSUFFICIENT_"+tf)
    sec=INTERVAL[tf]
    if any(bars[i]["t"]+sec!=bars[i+1]["t"] for i in range(len(bars)-1)):
        raise ValueError("GAPPED_OR_DUPLICATED_"+tf)
    if bars[-1]["t"]+sec>current:
        raise ValueError("UNCLOSED_CANDLE_IN_RESPONSE_"+tf)
    return bars,sha256(raw).hexdigest()


def reconcile_h4_to_h1(one,four):
    close=four[-1]["t"]+FOUR
    h=[b for b in one if close-FOUR<=b["t"]<close]
    if len(h)!=4:
        raise ValueError("MISSING_ONE_OF_FOUR_1H_CONSTITUENTS")
    aggregated={"o":h[0]["o"],"h":max(b["h"] for b in h),
                "l":min(b["l"] for b in h),"c":h[-1]["c"],
                "v":sum(b["v"] for b in h)}
    for key,value in aggregated.items():
        b=four[-1][key]
        if abs(b-value)>max(.00001,abs(value)*0.000002):
            raise ValueError("COINALYZE_1H_4H_DISAGREE_"+key)


def current_audit():
    key=(os.getenv("ETH_V7_COINALYZE_API_KEY") or os.getenv("COINALYZE_API_KEY") or "").strip()
    if not key:raise ValueError("MISSING_READONLY_HISTORICAL_API_KEY")
    now=int(datetime.now(timezone.utc).timestamp())
    raw={}
    proofs={}
    for tf in INTERVAL:
        bars,digest=acquire(key,tf,now)
        raw[tf]=bars
        proofs[tf]=digest
    one,four,daily=raw["1hour"],raw["4hour"],raw["daily"]
    latest4=four[-1]["t"]+FOUR
    target4=now//FOUR*FOUR
    expected1=now//HOUR*HOUR
    last1=one[-1]["t"]+HOUR
    statuses={"expected4H":iso(target4),"latestVerified4H":iso(latest4),
              "expected1H":iso(expected1),"latestVerified1H":iso(last1),
              "latestDaily":iso(daily[-1]["t"]+DAY)}
    output={
       "status":"RESEARCH_SNAPSHOT_NO_ORDERS",
       "symbol":SYMBOL,
       "runUTC":iso(now),
       "localRunTSI":datetime.fromtimestamp(now,timezone.utc).astimezone(
           __import__("datetime").timezone(__import__("datetime").timedelta(hours=3))).strftime("%Y-%m-%d %H:%M TSİ"),
       "sources":"Coinalyze SOLUSDT perpetual read-only 1H,4H,Daily",
       "responseSHA256":proofs,
       "closeValidation":statuses,
       "candleCounts":{k:len(v) for k,v in raw.items()},
       "liveTradeAllowed":False,
       "productionModified":False,
       "current4H":{"open":four[-1]["o"],"high":four[-1]["h"],
                    "low":four[-1]["l"],"close":four[-1]["c"]},
       "decision":{"action":"ABSTAIN_UNTIL_CONFIRMED","reason":"Pending feed validation"},
    }
    if latest4!=target4 or last1!=expected1:
        output["decision"]={"action":"ABSTAIN_STALE_SOURCE",
                           "reason":"Recent 1H and 4H closes do not match current expected timestamp"}
        return output
    reconcile_h4_to_h1(one,four)
    fc=[b["c"] for b in four]
    dc=[b["c"] for b in daily]
    i=len(four)-1
    features=features_at_4h_close(
         one,four,daily,i,
         rolling_sma(fc,100),rolling_sma(fc,200),rolling_rsi14(fc),
         rolling_sma(dc,100),rolling_sma(dc,200),rolling_rsi14(dc))
    if features is None:
        output["decision"]={"action":"ABSTAIN_INSUFFICIENT_WARMUP",
                            "reason":"Cannot compute closed-only SMA200/RSI"}
        return output
    output["technicalFeaturesAtLastVerified4HClose"]=features
    if features["status"]!="CANDIDATE":
        output["decision"]={"action":"ABSTAIN_MIXED_SMA_REGIME",
                            "reason":"Daily and 4H SMA100 vs 200 direction not aligned"}
        return output
    if features["score10"]<EXPLORATORY_SCORE_THRESHOLD:
        output["decision"]={"action":"ABSTAIN_SCORE_BELOW_SIX",
                            "reason":"Even shadow research 6/10 minimum not met",
                            "directionContext":features["side"],
                            "score10":features["score10"]}
        return output
    # At the immediate 4H close no subsequent 1H bar has finished; refuse
    # to turn a 4H watch into a 1H signal.
    subsequent=[x for x in one if x["t"]>=latest4]
    if not subsequent:
        output["decision"]={"action":"WAIT_FOR_CLOSED_1H_CONFIRMATION",
                            "reason":"No completed 1H bar after current 4H close",
                            "directionContext":features["side"],
                            "score10":features["score10"]}
        return output
    first_i=next((i for i,x in enumerate(one) if x["t"]==latest4),None)
    if first_i is None:
        output["decision"]={"action":"ABSTAIN_MISSING_NEXT_1H",
                            "reason":"Cannot verify first post-4H candle"}
        return output
    signal=first_1h_confirm_index(one,first_i,features["side"])
    if signal is None or one[signal["index"]]["t"]+HOUR>expected1:
        output["decision"]={"action":"WAIT_FOR_CLOSED_1H_CONFIRMATION",
                            "reason":"No qualifying closed 1H trigger found",
                            "directionContext":features["side"],
                            "score10":features["score10"]}
        return output
    # If signal is confirmed, report only a paper WATCH; no fills.
    output["decision"]={"action":"PAPER_WATCH_NOT_AN_ORDER",
                        "side":features["side"],"score10":features["score10"],
                        "trigger":signal,
                        "reason":"1H confirmed; any hypothetical entry at next 1H open only"}
    return output


def main():
    doc=current_audit()
    dest=Path("forward/v85_shadow/latest.json")
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(doc,indent=2,ensure_ascii=False)+"\n")
    print("V85_REAL_TIME_SHADOW_CLOSED_ONLY",doc["decision"],doc["closeValidation"],flush=True)


if __name__=="__main__":
    main()
