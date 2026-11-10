#!/usr/bin/env python3
"""V8.2 SOL: Fibonacci + previous-Daily pivots on frozen broad 4H support flips.

Strict event timing: broad Daily+4H boxes were already frozen before break;
retest event known only after its 4H candle CLOSE; Fib anchors and pivot
use nothing after that close. MACD is excluded. No paper orders or execution.
This historic archive has previously been examined. The 75% goal is a
benchmark to ASSESS, never a target for selecting thresholds after outcomes.
"""
import argparse
from bisect import bisect_right
from datetime import datetime,timezone,timedelta
import json
import math
from pathlib import Path

from sol_v81_htf_role_flip_research import official_history,atr,iso
from sol_v81_historical_wide_zone_study import (
    discover_boxes,independent_events,SECS4,DAY,SPLIT,ts_istanbul)

# Frozen BEFORE running against prior outcomes. Not optimised after seeing PnL.
FIB_START=.382
FIB_END=.618
FIB_ATR_TOLERANCE=.35
FIB_SWING_PREBREAK_4H=18
PIVOT_ATR_TOLERANCE=.65
SCORE_GOAL=.75
MIN_EVENTS_FOR_PRELIMINARY_CONFIDENCE=30

def previous_day_pivots(daily, four_bar):
    """Prior completed UTC day to the UTC day in which the 4H retest OPENED."""
    if not daily: return None
    day_start=four_bar["t"]//DAY*DAY
    ends=[d["t"]+DAY for d in daily]
    i=bisect_right(ends,day_start)-1
    if i<0:return None
    d=daily[i]
    if d["t"]+DAY>day_start:
        raise ValueError("PIVOT_USES_FUTURE_OR_UNCLOSED_DAY")
    h,l,c=d["h"],d["l"],d["c"]
    p=(h+l+c)/3.0
    span=h-l
    vals={"P":p,"R1":2*p-l,"R2":p+span,
          "S1":2*p-h,"S2":p-span}
    return {"sourceClosedUTC":iso(ends[i]),"sourceIndex":i,
            "levels":vals}


def frozen_confluence(four,daily,break_index,retest_index):
    """All inputs exist at 4H RETEST candle close; pivot from prior UTC day."""
    if not 20<=break_index<retest_index<len(four):
        raise ValueError("INVALID_EVENT_TIMELINE")
    retest=four[retest_index]
    retest_closed=retest["t"]+SECS4
    prior_atr=atr(four,retest_index-1)
    if not prior_atr or prior_atr<=0:raise ValueError("INVALID_CAUSAL_ATR")
    preceding=four[max(0,break_index-FIB_SWING_PREBREAK_4H):break_index]
    if len(preceding)<FIB_SWING_PREBREAK_4H:raise ValueError("NOT_ENOUGH_PREBREAK_4H")
    swing_high=max(b["h"] for b in preceding)
    swing_low=min(b["l"] for b in four[break_index:retest_index+1])
    if swing_high<=swing_low:
        fib_low=fib_high=None
        fib_touch=False
    else:
        span=swing_high-swing_low
        fib_low=swing_low+FIB_START*span
        fib_high=swing_low+FIB_END*span
        fib_touch=(fib_low-FIB_ATR_TOLERANCE*prior_atr
                   <=retest["h"]<=
                   fib_high+FIB_ATR_TOLERANCE*prior_atr)
    piv=previous_day_pivots(daily,retest)
    if not piv:raise ValueError("MISSING_PRIOR_COMPLETED_DAILY_PIVOT")
    # Only previous-day levels at or ABOVE the rejection candle close can
    # be interpreted as potential resistance; no hindsight pivot selection.
    above=[(label,val) for label,val in piv["levels"].items()
           if val>=retest["c"]]
    nearest=min(above,key=lambda p:(abs(p[1]-retest["h"]),p[0])) if above else None
    distance=abs(nearest[1]-retest["h"]) if nearest else None
    pivot_touch=(distance is not None and distance<=PIVOT_ATR_TOLERANCE*prior_atr)
    if piv["sourceClosedUTC"]>iso(retest["t"]):
        raise ValueError("PIVOT_KNOWN_ONLY_AFTER_RETEST_OPEN")
    return {
      "retestClosedUTC":iso(retest_closed),
      "retest4HOpenUTC":iso(retest["t"]),
      "retestHigh":round(retest["h"],6),
      "retestClose":round(retest["c"],6),
      "ATR14PreRetest":round(prior_atr,6),
      "fibAnchorSwingHighPrebreak":round(swing_high,6),
      "fibAnchorSwingLowBreakToRetest":round(swing_low,6),
      "fib382":round(fib_low,6) if fib_low is not None else None,
      "fib618":round(fib_high,6) if fib_high is not None else None,
      "fibHit":bool(fib_touch),
      "pivotPreviousDayClosedUTC":piv["sourceClosedUTC"],
      "pivotLevels":{k:round(v,6) for k,v in piv["levels"].items()},
      "nearestResistancePivotName":nearest[0] if nearest else None,
      "nearestResistancePivot":round(nearest[1],6) if nearest else None,
      "pivotHighDistanceATR":round(distance/prior_atr,5) if distance is not None else None,
      "pivotHit":bool(pivot_touch),
      "confluenceScore":int(fib_touch)+int(pivot_touch),
      "MACDUsed":False}


def wilson_lower(successes,n,z=1.95996398454):
    if n==0:return None
    phat=successes/n
    denom=1+z*z/n
    center=(phat+z*z/(2*n))/denom
    margin=z*math.sqrt((phat*(1-phat)+z*z/(4*n))/n)/denom
    return round(max(0,center-margin),4)


def summarize(rows):
    valid=[x for x in rows if x.get("future24hPct") is not None]
    wins=sum(x["future24hPct"]<0 for x in valid)
    n=len(valid)
    pct=round(100*wins/n,2) if n else None
    return {
        "qualifiedRetests":len(rows),
        "complete24hObservations":n,
        "lowerAfter24h":wins,
        "directionHitRatePct":pct,
        "wilson95LowerBoundPct":round(100*wilson_lower(wins,n),2) if n else None,
        "goal75ObservedInThisSample":pct is not None and pct>=75,
        "min30Observations":n>=MIN_EVENTS_FOR_PRELIMINARY_CONFIDENCE,
        "meets75GoalWithMin30":n>=MIN_EVENTS_FOR_PRELIMINARY_CONFIDENCE
            and pct is not None and pct>=75,
        "medianFuture24hPct":round(sorted(x["future24hPct"] for x in valid)[n//2],4)
            if n%2 else round((sorted(x["future24hPct"] for x in valid)[n//2-1]+
                              sorted(x["future24hPct"] for x in valid)[n//2])/2,4)
            if n else None,
    }


def evaluate(four,daily):
    boxes=discover_boxes(four,daily)
    all_rows,episodes=independent_events(boxes,four)
    index_by_closed={bar["t"]+SECS4:i for i,bar in enumerate(four)}
    if len(index_by_closed)!=len(four):raise ValueError("DUPLICATE_4H_CLOSE")
    rows=[]
    for event in episodes:
        if event.get("state")!="BEARISH_RETEST_REJECTION":
            continue
        break_i=index_by_closed.get(event["breakTs"])
        retest_i=index_by_closed.get(event["retestTs"])
        if break_i is None or retest_i is None:
            raise ValueError("MISSING_RETEST_INDICES")
        flags=frozen_confluence(four,daily,break_i,retest_i)
        if flags["retestClosedUTC"]!=event["retestUTC"]:
            raise ValueError("EVENT_RETEST_TIMELINE_DISAGREEMENT")
        row={
           "boxCreatedUTC":event["frozenUTC"],
           "boxLow":event["low"],"boxHigh":event["high"],
           "breakUTC":event["breakUTC"],
           "retestClosedUTC":event["retestUTC"],
           "retestClosedTSI":ts_istanbul(event["retestTs"]),
           "evaluatedWithOnlyClosedCandles":True,
           "future24hPct":event["next6AfterRetestPct"],
           "actualNext24hDown":(event["next6AfterRetestPct"]<0
                                  if event["next6AfterRetestPct"] is not None else None),
           **flags,
        }
        rows.append(row)
    filters={
       "baselineAllRetestRejections":lambda x:True,
       "fib382To618":lambda x:x["fibHit"],
       "previousDailyPivot":lambda x:x["pivotHit"],
       "fibAndPivotBoth":lambda x:x["fibHit"] and x["pivotHit"],
       "fibOrPivotEither":lambda x:x["fibHit"] or x["pivotHit"],
       "neitherConfluence":lambda x:not(x["fibHit"] or x["pivotHit"]),
    }
    segment={
       "all":lambda x:True,
       "before2026Jul":lambda x:int(datetime.fromisoformat(x["retestClosedUTC"].replace("Z","+00:00")).timestamp())<SPLIT,
       "reused2026JulSep":lambda x:int(datetime.fromisoformat(x["retestClosedUTC"].replace("Z","+00:00")).timestamp())>=SPLIT,
    }
    result={}
    for period,sc in segment.items():
        group=[x for x in rows if sc(x)]
        result[period]={k:summarize([x for x in group if fn(x)])
                        for k,fn in filters.items()}
    return rows,result,{
       "allCandidateBoxes":len(boxes),
       "deduplicatedBreakEpisodes":len(episodes),
       "qualifiedHistoricalRetests":len(rows),
       "withFuture24H":sum(x["future24hPct"] is not None for x in rows),
       "dailyPivotsOnlyPrevCompleteDay":True}


def render(report):
    lines=[
        "# SOL V8.2 — Fibonacci + previous Daily pivot on wide-zone 4H retests",
        "",
        "**No real trading or independent forward validation.** User's objective of 75% "
        "is a *benchmark*, not a basis for after-the-fact threshold optimization.",
        "",
        "**Source:** official Binance USD-M SOLUSDT 1H monthly ZIP + .CHECKSUM",
        f"**Verified months:** {report['sha256VerifiedMonths']}; "
        f"**period:** {report['period']['start']}–{report['period']['end']}",
        "",
        "## Frozen test rules (no MACD)",
        "- Wide Daily+4H boxes frozen at prior Daily closes; no user price anchor is used.",
        "- After 4H support breakdown and confirmed retest candle closes bearish below zone:",
        f"  - Fibonacci anchors: highest high in the {FIB_SWING_PREBREAK_4H} 4H candles BEFORE breakdown, "
        "lowest low from break through retest close. Wick high near 38.2–61.8% "
        f"retracement (±{FIB_ATR_TOLERANCE} times previous 4H ATR14).",
        f"  - Classical pivots: from the **previous completed UTC day** only "
        "(P, R1, R2, S1, S2). Retest high within "
        f"{PIVOT_ATR_TOLERANCE} times the previous 4H ATR14 of a level "
        "at/above retest close.",
        "- This is a retrospective diagnostic of 6 future 4H closing bars (24 hours); "
        "not a hypothetical entry PnL.",
        "- Event sample is deduplicated as in V8.1; no threshold fitting to the 75% objective.",
        "",
        "| Period | Filter | Retests | Down 24h | Direction hit | Wilson 95% lower bound |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for period,lab in (("all","Full historical"),
                       ("before2026Jul","Before July 2026"),
                       ("reused2026JulSep","July–Sep 2026 (reused)")):
        for filt,s in report["filterResults"][period].items():
            lines.append(f"| {lab} | {filt} | {s['complete24hObservations']} | "
                         f"{s['lowerAfter24h']} | "
                         f"{s['directionHitRatePct'] if s['directionHitRatePct'] is not None else 'N/A'}% | "
                         f"{s['wilson95LowerBoundPct'] if s['wilson95LowerBoundPct'] is not None else 'N/A'}% |")
    lines.extend(["", "## Sample event examples",
        "| Retest TSİ | Wide zone (USD) | Fib matched | Pivot matched | Nearest pivot | 24h direction return |",
        "|---|---|---|---|---|---:|"])
    for r in report["retestExamples"]:
        future=(f"{r['future24hPct']:+.3f}%" if r["future24hPct"] is not None else "Unresolved")
        lines.append(
            f"| {r['retestClosedTSI']} | {r['boxLow']:.2f}–{r['boxHigh']:.2f} | "
            f"{'Yes' if r['fibHit'] else 'No'} | "
            f"{'Yes' if r['pivotHit'] else 'No'} | "
            f"{r['nearestResistancePivotName'] or 'N/A'} | {future} |")
    lines+=["", "## Limitations",
            "- These filters were designed after earlier analysis of the same archive; results are exploratory, not a clean held-out experiment.",
            "- A 75% hit rate from a small subset can be noise. Also test win/loss *money*, fees, spread, stop, and forward time-separated samples.",
            "- No actual fills, OI, funding, taker or verified institutional OB modeled.",
            "- A direction hit over 24 hours is not equal to a profitable SHORT position.",
            "- No production or active BTC/SOL/ETH trading workflows were modified.",
            ""]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default="2025-01")
    p.add_argument("--end",default="2026-09")
    p.add_argument("--workers",default=6,type=int)
    p.add_argument("--json",default="forward/v82_fib_pivot/latest.json")
    p.add_argument("--markdown",default="forward/v82_fib_pivot/latest.md")
    args=p.parse_args()
    four,daily,proofs=official_history(args.start,args.end,args.workers)
    rows,results,counts=evaluate(four,daily)
    doc={
      "mode":"V82_SOL_FIB_PREVIOUS_DAY_PIVOT_ON_FROZEN_4H_WIDE_BOX_RETETS_NO_ORDERS",
      "status":"HISTORICAL_EXPLORATION_NO_LIVE_SIGNAL",
      "createdUTC":datetime.now(timezone.utc).isoformat(),
      "period":{"start":args.start,"end":args.end,
                "holdoutReusedNotIndependent":"2026-07-01 onwards"},
      "source":"Binance USD-M SOLUSDT official monthly 1H ZIP + CHECKSUM",
      "sha256VerifiedMonths":len(proofs),
      "candleCounts":{"4hour":len(four),"daily":len(daily)},
      "goalDirectionHitRatePct":SCORE_GOAL*100,
      "frozenParameters":{"fibSwingPrior4HCandles":FIB_SWING_PREBREAK_4H,
                          "fibRetracementStartPct":FIB_START*100,
                          "fibRetracementEndPct":FIB_END*100,
                          "fibTolerancePrev4HATR":FIB_ATR_TOLERANCE,
                          "pivotTolerancePrev4HATR":PIVOT_ATR_TOLERANCE,
                          "pivotReference":"Previous completed UTC Daily candle before retest 4H open",
                          "pivotLevels":["P","R1","R2","S1","S2"],
                          "MACDUsed":False,
                          "thresholdTunedToOutcomes":False},
      "counts":counts,"filterResults":results,
      "retestExamples":rows[-25:],
      "allRetestFeatures":rows,
      "note":"Descriptive 24h direction metric, not net PnL or forward performance.",
      "mainProductionModified":False,"brokerOrders":False,
      "liveTradingApproved":False}
    out=Path(args.json);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(doc,indent=2,ensure_ascii=False)+"\n")
    md=Path(args.markdown);md.parent.mkdir(parents=True,exist_ok=True)
    md.write_text(render(doc))
    print("V82_FIB_PIVOT_RESULTS_VERIFIED",len(proofs),json.dumps(results["all"]),
          flush=True)


if __name__=="__main__":
    main()
