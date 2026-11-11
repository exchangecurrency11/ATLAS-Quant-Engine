#!/usr/bin/env python3
"""V9+ causal trade-opportunity quality FEATURES, shadow-only.

Primary entry engine remains the original V7 BOS -> later retest -> next 1H
open. This independent V9 profile is computed ONLY after a V7 BOS has
passed its original filter and on the SAME closed 1H candle that confirms
the watch. No future high/low, OI, funding, taker CVD, chart structure
retrospectively revised, or candle after the BOS is allowed.

Not a profit probability. Liquidity, OHLCV order blocks and FVG are
chart patterns only, NOT real resting orders or execution liquidity.
Thresholds 60 and 75 are pre-registered research candidates, not chosen
from the inspected backtest; only a NEW prospective trade evaluation may
support production adoption.

Feature group names:
- breakout quality (distance beyond BOS broken level, ATR14)
- relative volume (20 prior CLOSED 1H bars)
- 1H directional candle body
- momentum alignment with EMA20/EMA50 and EMA20 slope
- ATR14 / past 70 ATR14 regime (quiet, normal, expansion, chaotic)
- prior-20H high/low sweep and re-entry
- nearby open directional three-candle FVG from prior/current closed bars
- nearby non-invalidated OHLCV order block (heuristic only)
- opposing wick and excessive extension risk penalty.
"""
import math
from statistics import mean
from market_structure import average_true_range,analyze

HOUR=3600
MIN_HISTORY=250
SCORE_CANDIDATES={"V9_QUALITY_SCORE_60":60,"V9_QUALITY_SCORE_75":75}
PREDECLARED_FEATURE_WEIGHTS={
 "base":20.,"breakoutATR":18.,"relativeVolume":14.,"bodyATR":12.,
 "emaAlignment":8.,"ema20Slope":7.,"volatilityRegime":10.,
 "priorHighLowSweep":6.,"nearOpenFVG":8.,"nearUninvalidatedOrderBlock":10.,
 "overextendedPenalty":-12.,"opposingWickPenalty":-8.,
}


def _ema(closes,period):
    if not closes:raise ValueError("EMPTY_EMA")
    k=2/(period+1)
    z=float(closes[0])
    for value in closes[1:]:
        z=k*value+(1-k)*z
    return z


def _distance_to_interval(value,lo,hi):
    return max(lo-value,0.,value-hi)


def _cap(value,high):
    return max(0.,min(high,value))


def quality_profile(bars,bos,indicators):
    if len(bars)<MIN_HISTORY:
        raise ValueError("V9_QUALITY_REQUIRES_250_FINISHED_HOURS")
    if bos.get("event")!="BOS" or bos.get("direction") not in ("bullish","bearish"):
        raise ValueError("V9_QUALITY_ONLY_FROM_V7_CONFIRMED_BOS")
    if bos.get("at")!=bars[-1]["t"]:
        raise ValueError("V9_QUALITY_BOS_NOT_LAST_CLOSED_HOUR")
    if any(type(b["t"]) is not int or b["t"]%HOUR for b in bars):
        raise ValueError("V9_QUALITY_NOT_1H_ALIGNED")
    if any(bars[i+1]["t"]!=bars[i]["t"]+HOUR for i in range(len(bars)-1)):
        raise ValueError("V9_QUALITY_HISTORY_HAS_GAP")
    end=bars[-1]["t"]+HOUR
    if bos.get("confirmedAt",end)>end:
        raise ValueError("V9_QUALITY_FUTURE_BOS")
    for bar in bars:
        o,h,l,c,v=[float(bar[k]) for k in ("o","h","l","c","v")]
        if not all(map(math.isfinite,(o,h,l,c,v))) or l<=0 or l>min(o,c) or h<max(o,c) or v<0:
            raise ValueError("V9_QUALITY_INVALID_1H_OHLCV")
    signed=1 if bos["direction"]=="bullish" else -1
    last=bars[-1];previous=bars[:-1]
    close=float(last["c"]);op=float(last["o"])
    level=float(bos["brokenLevel"])
    atr=average_true_range(bars,len(bars)-1,count=14)
    if not atr or atr<=0 or not math.isfinite(atr) or not math.isfinite(level):
        raise ValueError("V9_QUALITY_NO_VALID_ATR_OR_LEVEL")
    rv_den=mean(float(x["v"]) for x in bars[-21:-1])
    if rv_den<=0:raise ValueError("V9_QUALITY_NO_REFERENCE_VOLUME")
    rv=float(last["v"])/rv_den
    delta=signed*(close-level)/atr
    body=signed*(close-op)/atr
    high,low=float(last["h"]),float(last["l"])
    candle_range=max(1e-12,high-low)
    upper=(high-max(op,close))/candle_range
    lower=(min(op,close)-low)/candle_range
    opposing_wick=upper if signed>0 else lower
    prices=[float(x["c"]) for x in bars[-90:]]
    ema20=_ema(prices,20);ema50=_ema(prices,50)
    ema20_5h_ago=_ema(prices[:-5],20)
    ema_aligned=signed*(ema20-ema50)>0
    ema_slope_aligned=signed*(ema20-ema20_5h_ago)>0
    extension=signed*(close-ema20)/atr

    # ATR regime is calculated only from previously closed 1H bars.
    atr_hist=[average_true_range(bars,i,count=14)
              for i in range(len(bars)-71,len(bars)-1)]
    if any(x is None or x<=0 for x in atr_hist):
        raise ValueError("V9_QUALITY_INSUFFICIENT_REGIME_HISTORY")
    ratio=atr/mean(atr_hist)
    regime=("CALM" if ratio<.70 else "NORMAL" if ratio<=1.50 else
            "EXPANSION" if ratio<=2.8 else "CHAOTIC")
    regime_points={"CALM":3.,"NORMAL":10.,"EXPANSION":6.,"CHAOTIC":0.}[regime]

    prev20=previous[-20:]
    prior_hi=max(float(x["h"]) for x in prev20)
    prior_lo=min(float(x["l"]) for x in prev20)
    sweep=(low<prior_lo and close>prior_lo) if signed>0 else (
        high>prior_hi and close<prior_hi)

    # Already known ON THIS BOS HOUR: this is NOT a later retest result.
    # Reuse existing market_structure 1H chart-pattern semantics, no
    # speculative actual order flow, and insist all confirmedAt <= end.
    structure=analyze(bars,"1hour",as_of=end)
    if structure["status"]!="READY" or structure["lastCloseTimeUTC"]!=end:
        raise ValueError("V9_QUALITY_CHART_STRUCTURE_NOT_CLOSED")
    for family in ("orderBlocks","fvg"):
        if any(z["confirmedAt"]>end for z in structure[family]):
            raise ValueError("V9_QUALITY_FUTURE_CHART_ZONE_LEAK")
    near_fvg=[
      z for z in structure["fvg"]
      if z["side"]==bos["direction"] and z["state"]=="open"
      and _distance_to_interval(close,z["low"],z["high"])<=1.5*atr
      and z["confirmedAt"]<=end
    ]
    near_ob=[
      z for z in structure["orderBlocks"]
      if z["side"]==bos["direction"] and z["state"]!="invalidated"
      and _distance_to_interval(close,z["wick"]["low"],z["wick"]["high"])<=2*atr
      and z["confirmedAt"]<=end
    ]

    parts={
      "base":20.,
      "breakoutATR":_cap(12*delta,18),
      "relativeVolume":_cap((rv-1)*9,14),
      "bodyATR":_cap(12*body,12),
      "emaAlignment":8. if ema_aligned else 0.,
      "ema20Slope":7. if ema_slope_aligned else 0.,
      "volatilityRegime":regime_points,
      "priorHighLowSweep":6. if sweep else 0.,
      "nearOpenFVG":8. if near_fvg else 0.,
      "nearUninvalidatedOrderBlock":10. if near_ob else 0.,
      "overextendedPenalty":-12. if extension>2.5 else 0.,
      "opposingWickPenalty":-8. if opposing_wick>.45 else 0.,
    }
    raw=sum(parts.values())
    score=round(_cap(raw,100),3)
    return {
       "status":"V9_TRADE_QUALITY_SNAPSHOT_FROM_CLOSED_V7_BOS_ONLY",
       "observedClosed1HUTC":end,
       "direction":bos["direction"],
       "bosLevel":level,
       "qualityScoreNotProfitProbability":score,
       "qualityBand":"HIGH" if score>=75 else "MEDIUM" if score>=60 else "LOW",
       "components":{k:round(v,4) for k,v in parts.items()},
       "featureWeightsRegisteredWithoutOutcomeTuning":PREDECLARED_FEATURE_WEIGHTS,
       "features":{
           "breakoutInATR":round(delta,5),
           "relativeVolume20":round(rv,5),
           "directionalBodyInATR":round(body,5),
           "ema20AboveEMA50Agree":ema_aligned,
           "ema20SlopeAgrees":ema_slope_aligned,
           "atrRegimeRatio":round(ratio,5),
           "atrRegime":regime,
           "prior20HighLowSweepAgainstOpposingSide":sweep,
           "nearFVGCount":len(near_fvg),
           "nearOrderBlockCount":len(near_ob),
           "overextensionInATR":round(extension,5),
           "opposingWickShare":round(opposing_wick,5),
       },
       "liquidityFVGAndOrderBlocksNotActualOrders":True,
       "noFutureRetestOrTPUsed":True,
       "noProviderOIOrFundingOrUnverifiedTradeCount":True,
       "noTradePlaced":True,
       "notAStandaloneEntrySignal":True,
    }


def gate_v7_with_quality(bars,bos,indicators,original,threshold,evidence):
    if threshold not in SCORE_CANDIDATES.values():
        raise ValueError("UNREGISTERED_QUALITY_THRESHOLD")
    if not original.get("passed"):
        return original
    result=quality_profile(bars,bos,indicators)
    evidence["v7QualifyingBOSScored"]=evidence.get("v7QualifyingBOSScored",0)+1
    evidence.setdefault("scoreHistogram",{"LOW":0,"MEDIUM":0,"HIGH":0})
    evidence["scoreHistogram"][result["qualityBand"]]+=1
    evidence.setdefault("regimeHistogram",
        {"CALM":0,"NORMAL":0,"EXPANSION":0,"CHAOTIC":0})
    evidence["regimeHistogram"][result["features"]["atrRegime"]]+=1
    evidence.setdefault("scoresAtV7BOS",[])
    evidence["scoresAtV7BOS"].append({
        "closed1HUTC":result["observedClosed1HUTC"],
        "direction":result["direction"],"score":result["qualityScoreNotProfitProbability"],
        "qualityBand":result["qualityBand"],
        "atrRegime":result["features"]["atrRegime"],
        "hasFVG":result["features"]["nearFVGCount"]>0,
        "hasOB":result["features"]["nearOrderBlockCount"]>0,
        "hasSweep":result["features"]["prior20HighLowSweepAgainstOpposingSide"],
    })
    passed=result["qualityScoreNotProfitProbability"]>=threshold
    if not passed:
        evidence["v9QualityRejected"]=evidence.get("v9QualityRejected",0)+1
    else:
        evidence["v9QualityAccepted"]=evidence.get("v9QualityAccepted",0)+1
    return {
       **original,
       "passed":passed,
       "reasons":list(original["reasons"])+(
           [] if passed else ["V9_QUALITY_SCORE_BELOW_PREDECLARED_"+str(threshold)]),
       "v9QualityResearch":result,
    }
