#!/usr/bin/env python3
"""MACD-free counterfactual: freeze 15:00 TSİ indicators, compare next 19:00 4H.
Reads previously source-verified 15-to-19 paper reconstruction only.
Do not read MACD values for any logic. No orders or claims of forward efficacy.
"""
import json
from datetime import datetime,timezone
from pathlib import Path

INPUT=Path("forward/v8_blind4h/2026-11-10_15-to-19-TSI.json")
OUTPUT=Path("forward/v8_blind4h/2026-11-10_no_macd_15-to-19-TSI.json")
TF=("1hour","4hour","daily")
ASSETS=("BTCUSDT_PERP.A","ETHUSDT_PERP.A","SOLUSDT_PERP.A")


def evaluate_frozen_coin(coin, item):
    old=item["asOf15TSI"]
    later=item["asOf19TSI"]
    if old["targetUTC"]!="2026-11-10T12:00:00Z" or later["targetUTC"]!="2026-11-10T16:00:00Z":
        raise ValueError("WRONG_AS_OF_CUTOFF")
    o={}
    for tf in TF:
        x=old["timeframes"][tf]
        if tf=="daily":
            if x["lastClosedUTC"]!="2026-11-10T00:00:00Z":
                raise ValueError("STALE_DAILY_FOR_BLIND_TEST")
        elif x["lastClosedUTC"]!="2026-11-10T12:00:00Z":
            raise ValueError("FUTURE_OR_STALE_BAR")
        q=x["indicators"]
        close=x["OHLCV"]["c"]
        # Explicitly and exclusively allowed price/EMA/RSI inputs.
        ema20,ema50,ema200,rsi=(q["EMA20"],q["EMA50"],q["EMA200"],q["RSI14"])
        votes={
            "belowEMA20":close<ema20,
            "belowEMA50":close<ema50,
            "RSIbelow50":rsi<50,
            "aboveEMA20":close>ema20,
            "aboveEMA50":close>ema50,
            "RSIabove50":rsi>50,
        }
        trend=("BEARISH" if all(votes[k] for k in
            ("belowEMA20","belowEMA50","RSIbelow50")) else
            "BULLISH" if all(votes[k] for k in
            ("aboveEMA20","aboveEMA50","RSIabove50")) else "MIXED")
        o[tf]={"lastClosedUTC":x["lastClosedUTC"],
               "close":close,"RSI14":rsi,
               "EMA20":ema20,"EMA50":ema50,"EMA200":ema200,
               "votes":votes,"trendMACDExcluded":trend,
               "EMA200SupportsTrend":(
                   close<ema200 if trend=="BEARISH" else
                   close>ema200 if trend=="BULLISH" else None),
               "oversoldCaution":rsi<35,
               "overboughtCaution":rsi>65}
    main=[o["4hour"]["trendMACDExcluded"],o["daily"]["trendMACDExcluded"]]
    # EMA200 is context, not a veto that masks BTC's daily 20/50 trend.
    direction=main[0] if main[0]==main[1] else "MIXED"
    outcome=item["comparison"]
    anticipated=("DOWN" if direction=="BEARISH" else
                 "UP" if direction=="BULLISH" else "NO_DIRECTION")
    observed=outcome["actualDirection"]
    # Deeper breakout evidence is observed ONLY AFTER the 19:00 close.
    return {
        "coin":coin,
        "MACDUsed":False,
        "frozenAtUTC":old["targetUTC"],
        "timeframes":o,
        "primaryTrendMACDFree":direction,
        "oneHourAgrees":o["1hour"]["trendMACDExcluded"]==direction,
        "predictedNext4HDirection":anticipated,
        "actualNext4HDirection":observed,
        "directionMatchesOutcome":(
            anticipated==observed if anticipated!="NO_DIRECTION" else None),
        "previous4HClose":outcome["previous4HClose"],
        "next4HOpen":outcome["next4HOpen"],
        "next4HHigh":outcome["next4HHigh"],
        "next4HLow":outcome["next4HLow"],
        "next4HClose":outcome["next4HClose"],
        "next4HChangePercent":outcome["priceChangePct"],
        "priorCandleLowBrokenOnNextClose":outcome["nextCloseBelowPriorCandleLow"],
        "V7New1HBOSAt15":old["asOfOnly"]["new1HBOSAtClose"],
        "V7PaperEntryAt15":False,
        "asOf15ActualVerifiedSnapshot":item["firstCandleHadRealtimeVerifiedSnapshot"],
        "warning":"Direction ≠ verified trade entry. A BOS/retest is not invented.",
    }


def run(data):
    if data.get("status")!="RETROSPECTIVE_BLIND_CUTOFF_RECONSTRUCTED_NO_ORDERS":
        raise ValueError("UNVERIFIED_SOURCE")
    if data.get("freezeAtUTC")!="2026-11-10T12:00:00Z" or data.get("compareAtUTC")!="2026-11-10T16:00:00Z":
        raise ValueError("WRONG_TEST_PERIOD")
    if data.get("brokerOrders") is not False or set(data.get("coins",{}))!=set(ASSETS):
        raise ValueError("UNSAFE_OR_INCOMPLETE_INPUT")
    out={"status":"VERIFIED_RETROSPECTIVE_MACD_EXCLUDED_PAPER_REVIEW",
         "frozenAtUTC":data["freezeAtUTC"],"comparedAtUTC":data["compareAtUTC"],
         "strategy":"MACD_FREE_EMA20_EMA50_RSI14_DAILY_4H_DIRECTION",
         "realtimePrediction":False,"brokerOrders":False,
         "liveTradingApproved":False,
         "note":"Baseline 4H direction already MACD independent; this version also removes MACD momentum gate and treats EMA200 as context not hard veto.",
         "coins":{}}
    for coin in ASSETS:
        out["coins"][coin]=evaluate_frozen_coin(coin,data["coins"][coin])
    out["directionHits"]=sum(r["directionMatchesOutcome"] is True for r in out["coins"].values())
    out["assessedAssets"]=len(out["coins"])
    out["originalETH15RealTimeDataUnavailable"]=True
    return out


def main():
    source=json.loads(INPUT.read_text(encoding="utf-8"))
    result=run(source)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("V8_4H_NO_MACD_REVIEW",result["directionHits"],result["assessedAssets"])
    for key,x in result["coins"].items():
        print(key,x["primaryTrendMACDFree"],x["next4HChangePercent"],
              x["directionMatchesOutcome"],"1H_BOS",x["V7New1HBOSAt15"])


if __name__=="__main__":
    main()
