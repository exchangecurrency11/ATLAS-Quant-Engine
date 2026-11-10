#!/usr/bin/env python3
"""V8.1 broad SOL Daily+4H congestion -> support-break -> retest study.

Every box is discovered FROM CLOSED DATA ONLY, before its later break/retest.
No hand-drawn 87.50-95.00 price anchors enter the historical detector.
The 8.5% band is an EXPLORATORY fixed-width modelling choice inspired
by the user's broad rectangle, not a validated optimal size.
No MACD; no backfilled market/limit orders; not an ICT breaker proof.
All archives must be complete, checksum verified Binance SOLUSDT USD-M.
Dates are UTC; report also displays Europe/Istanbul local time.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path
from statistics import median,mean
import json,math
from bisect import bisect_right

from sol_v81_htf_role_flip_research import official_history, atr, iso

WIDTH_RATIO=0.085
DAILY_LOOKBACK=28
FOUR_LOOKBACK=DAILY_LOOKBACK*6
MIN_DAILY_CLOSES=6
MIN_FOUR_CLOSES=28
MIN_CANDIDATE_AGE_DAYS=21
MAX_BREAK_WAIT_4H=42  # 7 days after rectangle is frozen
MAX_RETEST_4H=30     # 5 days after breakdown
BREAK_PAD_ATR=0.15
SPLIT=int(datetime(2026,7,1,tzinfo=timezone.utc).timestamp())
SECS4=14400
DAY=86400


def ts_istanbul(x):
    t=datetime.fromtimestamp(x,timezone(timedelta(hours=3)))
    return t.strftime("%Y-%m-%d %H:%M TSİ")


def intersect_fraction(a,b):
    inter=max(0,min(a["high"],b["high"])-max(a["low"],b["low"]))
    union=max(a["high"],b["high"])-min(a["low"],b["low"])
    return inter/union if union>0 else 0


def select_box_at_cutoff(four,daily,cutoff):
    """No 4H or Daily bar with close time after cutoff may enter selection."""
    ends4=[b["t"]+SECS4 for b in four]
    endsD=[b["t"]+DAY for b in daily]
    i4=bisect_right(ends4,cutoff)
    iD=bisect_right(endsD,cutoff)
    if i4<FOUR_LOOKBACK or iD<DAILY_LOOKBACK:
        return None
    past4=four[i4-FOUR_LOOKBACK:i4]
    pastD=daily[iD-DAILY_LOOKBACK:iD]
    last=four[i4-1]
    candidates=[]
    # Anchors use only already closed Daily prices. The user-supplied
    # 87.50–95.00 zone is intentionally NOT in this function.
    for d in pastD:
        low=d["c"]*0.985
        high=low*(1+WIDTH_RATIO)
        count_d=sum(low<=x["c"]<=high for x in pastD)
        count_4=sum(low<=x["c"]<=high for x in past4)
        if count_d<MIN_DAILY_CLOSES or count_4<MIN_FOUR_CLOSES:
            continue
        # Price is still at/above the prospective floor at box creation,
        # not already well below support after a breakdown.
        if not low<=last["c"]<=high*1.08:
            continue
        above=sum(x["c"]>high for x in past4)
        below=sum(x["c"]<low for x in past4)
        # Exclude a box if the previous month has spent much more time
        # below the proposed support than inside or above.
        if below>count_4:
            continue
        score=6*count_d+count_4
        candidates.append((score,count_d,count_4,low,high,above,below))
    if not candidates:
        return None
    # Deterministic tie-breaker, never based on what happens AFTER cutoff.
    score,nd,n4,low,high,above,below=max(candidates,key=lambda v:(v[0],v[2],-v[3]))
    return {"frozenUTC":iso(cutoff),
            "frozenTs":cutoff,
            "low":round(low,6),
            "high":round(high,6),
            "widthPct":round(100*(high-low)/((high+low)/2),3),
            "dailyCloseCountAtCreation":nd,
            "fourHourCloseCountAtCreation":n4,
            "dailyCandlesUsed":DAILY_LOOKBACK,
            "fourHourCandlesUsed":FOUR_LOOKBACK,
            "last4HCloseAtCreation":round(last["c"],6),
            "dataLatest4HCloseAtCreationUTC":iso(ends4[i4-1]),
            "dataLatestDailyCloseAtCreationUTC":iso(endsD[iD-1]),
            "abovePrior4H":above,
            "belowPrior4H":below,
            "formationScore":score,
            "manualZoneAnchorUsed":False}


def discover_boxes(four,daily):
    """Freeze rectangles at a daily close, one per 21d unless distinct."""
    out=[]
    for day in daily[DAILY_LOOKBACK:]:
        ts=day["t"]+DAY
        if ts>four[-1]["t"]+SECS4:
            break
        box=select_box_at_cutoff(four,daily,ts)
        if box is None:continue
        # Suppress near-duplicate boxes drawn in adjacent days.
        if out and any(
            ts-z["frozenTs"]<MIN_CANDIDATE_AGE_DAYS*DAY
            and intersect_fraction(box,z)>.55
            for z in out[-8:]):
            continue
        out.append(box)
    return out


def identify_first_break(four,box):
    cut=box["frozenTs"]
    ends=[b["t"]+SECS4 for b in four]
    idx=bisect_right(ends,cut)
    lo=box["low"]
    for i in range(idx,min(len(four),idx+MAX_BREAK_WAIT_4H)):
        if i<15:continue
        # Only 4H bar i and earlier are known as of close i.
        volatility=atr(four,i-1)
        if not volatility or volatility<=0:continue
        if (four[i-1]["c"]>=lo
             and four[i]["c"]<lo-BREAK_PAD_ATR*volatility):
            return i
    return None


def examine_after_break(four,box,break_i):
    if break_i is None:
        return {"state":"NO_BREAK_WITHIN_7D","breakUTC":None,
                "retestUTC":None,"next6AfterBreakPct":None}
    lo,hi=box["low"],box["high"]
    result={
       "state":"BROKEN_NO_CONFIRMED_RETEST",
       "breakUTC":iso(four[break_i]["t"]+SECS4),
       "breakTs":four[break_i]["t"]+SECS4,
       "breakClose":round(four[break_i]["c"],6),
       "retestUTC":None,"retestTs":None,"retestClose":None,
       "retestHigh":None,"retestIndex":None,
       "next6AfterBreakPct":None,
       "next6AfterRetestPct":None,
       "retestCandleIsBearish":None,
    }
    if break_i+6<len(four):
        result["next6AfterBreakPct"]=round(
            100*(four[break_i+6]["c"]/four[break_i]["c"]-1),4)
    else:
        result["next6AfterBreakUnresolved"]=True

    for i in range(break_i+1,min(len(four),break_i+1+MAX_RETEST_4H)):
        b=four[i]
        # Reclaim first: this is known at the current closed 4H bar.
        if b["c"]>hi:
            result["state"]="RECLAIMED_ABOVE_ZONE"
            result["reclaimUTC"]=iso(b["t"]+SECS4)
            return result
        if b["h"]>=lo and b["l"]<=hi:
            # Bearish rejection after a break: retest high touches zone,
            # 4H close stays below its bottom and candle body is down.
            if b["c"]<lo and b["c"]<b["o"]:
                result["state"]="BEARISH_RETEST_REJECTION"
                result["retestUTC"]=iso(b["t"]+SECS4)
                result["retestTs"]=b["t"]+SECS4
                result["retestClose"]=round(b["c"],6)
                result["retestHigh"]=round(b["h"],6)
                result["retestIndex"]=i
                result["retestCandleIsBearish"]=True
                if i+6<len(four):
                    result["next6AfterRetestPct"]=round(
                        100*(four[i+6]["c"]/b["c"]-1),4)
                    result["next6AfterRetestClosesBelow"]=(four[i+6]["c"]<b["c"])
                else:
                    result["next6AfterRetestUnresolved"]=True
                return result
    return result


def independent_events(boxes,four):
    """All formed candidates retained; overlapping break episodes deduplicated."""
    all_rows=[]
    for box in boxes:
        idx=identify_first_break(four,box)
        row={**box,**examine_after_break(four,box,idx)}
        all_rows.append(row)
    episodes=[]
    for row in sorted(
        (x for x in all_rows if x.get("breakTs") is not None),
        key=lambda z:(z["breakTs"],z["frozenTs"])):
        match=[z for z in episodes if abs(row["breakTs"]-z["breakTs"])<=7*DAY
               and intersect_fraction(z,row)>.50]
        if match:
            continue
        episodes.append(row)
    return all_rows,episodes


def safe_summary(records):
    break_rows=[x for x in records if x.get("breakTs") is not None]
    retests=[x for x in break_rows if x["state"]=="BEARISH_RETEST_REJECTION"]
    returns=[x["next6AfterBreakPct"] for x in break_rows
             if x["next6AfterBreakPct"] is not None]
    after=[x["next6AfterRetestPct"] for x in retests
           if x.get("next6AfterRetestPct") is not None]
    return {
       "cases":len(records),
       "brokenSupportWithin7d":len(break_rows),
       "retestRejected":len(retests),
       "reclaimed":sum(x["state"]=="RECLAIMED_ABOVE_ZONE" for x in break_rows),
       "brokenButNoQualifiedRetest":sum(x["state"]=="BROKEN_NO_CONFIRMED_RETEST" for x in break_rows),
       "noBreakWithin7d":sum(x["state"]=="NO_BREAK_WITHIN_7D" for x in records),
       "afterBreak6barObserved":len(returns),
       "breakFollowThroughDown6bar":sum(x<0 for x in returns),
       "breakFollowThroughDownRatePct":round(100*sum(x<0 for x in returns)/len(returns),2) if returns else None,
       "median6barPriceChangeAfterBreakPct":round(median(returns),4) if returns else None,
       "afterRetest6barObserved":len(after),
       "retestFollowThroughDown6bar":sum(x<0 for x in after),
       "retestFollowThroughDownRatePct":round(100*sum(x<0 for x in after)/len(after),2) if after else None,
       "median6barPriceChangeAfterRetestPct":round(median(after),4) if after else None,
    }



def trend_control_baselines(four,daily):
    """Transparent descriptive control; overlapping 24h windows not independent.

    Only EMA20/50 and already closed 4H/Daily candles, never MACD, OB or
    a hindsight-chosen hand-drawn box. No trade execution implication.
    """
    def track(bars,n):
        alpha=2/(n+1)
        value=bars[0]["c"]
        output=[]
        for b in bars:
            value=alpha*b["c"]+(1-alpha)*value
            output.append(value)
        return output
    f20,f50=track(four,20),track(four,50)
    d20,d50=track(daily,20),track(daily,50)
    day_ends=[d["t"]+DAY for d in daily]
    observations=[]
    for i in range(200,len(four)-6):
        end=four[i]["t"]+SECS4
        di=bisect_right(day_ends,end)-1
        if di<50: continue
        close=four[i]["c"]
        follow=100*(four[i+6]["c"]/close-1)
        four_down=close<f20[i] and close<f50[i]
        daily_down=daily[di]["c"]<d20[di] and daily[di]["c"]<d50[di]
        observations.append({"asOfTs":end,"after6Pct":follow,
                             "bothHigherFramesBearish":four_down and daily_down})
    def summarize_segment(items):
        all_returns=[x["after6Pct"] for x in items]
        trend=[x["after6Pct"] for x in items if x["bothHigherFramesBearish"]]
        def summarize_returns(vals):
            return {"observations":len(vals),
                    "lowerAfter6Bars":sum(x<0 for x in vals),
                    "lowerAfter6BarsPct":round(100*sum(x<0 for x in vals)/len(vals),2) if vals else None,
                    "median6BarChangePct":round(median(vals),4) if vals else None}
        return {"all4HCloses":summarize_returns(all_returns),
                "MACDFreeDailyAnd4HBearish":summarize_returns(trend)}
    return {
        "all":summarize_segment(observations),
        "before2026Jul":summarize_segment([x for x in observations if x["asOfTs"]<SPLIT]),
        "since2026Jul":summarize_segment([x for x in observations if x["asOfTs"]>=SPLIT]),
        "warning":"24h observation windows overlap and are not independent trades."}


def render_md(report):
    a=report["summary"]
    formed=report["boxFormationCounts"]
    lines=[
       "# SOL — Historical Daily + 4H wide support-box role-flip study",
       "",
       "**Important:** This tests automatically frozen broad rectangles, "
       "not the exact manually drawn 87.50–95.00 zone in November 2026.",
       "",
       "## Method",
       f"- Binance USD-M SOL perpetual official monthly 1H ZIPs with SHA256: **{report['sha256VerifiedArchives']}**.",
       f"- {report['period']['start']} to {report['period']['end']} (inclusive complete months).",
       f"- Each day a band width of 8.5% of its lower edge is evaluated with **only the preceding {DAILY_LOOKBACK} closed Daily and {FOUR_LOOKBACK} closed 4H candles**.",
       f"- Require at least {MIN_DAILY_CLOSES} Daily and {MIN_FOUR_CLOSES} 4H closes inside the band, price at or above the lower boundary at formation.",
       "- Freeze box BEFORE searching for subsequent breaks; close below floor with 0.15 prior ATR14 margin within 7 days qualifies a break.",
       "- Next 5 days: a 4H bar touching the box but closing red below its lower edge is a qualified bearish retest rejection. Reclaim above upper edge is tracked separately.",
       "- Compare next 6 fully closed 4H returns after a break or retest; no simulated fills, no funding/slippage profit claims.",
       "- Only one representative episode per near-overlapping band / break time is included in summary to reduce repeated counting.",
       "",
       "## General background rate (control, not a trading strategy)",
       f"- All eligible 4H closes: **{report['controlBaselines']['all']['all4HCloses']['lowerAfter6Bars']} / {report['controlBaselines']['all']['all4HCloses']['observations']}** closed lower 24 hours later.",
       f"- When BOTH Daily+4H prices were below EMA20 and EMA50 (MACD excluded): **{report['controlBaselines']['all']['MACDFreeDailyAnd4HBearish']['lowerAfter6Bars']} / {report['controlBaselines']['all']['MACDFreeDailyAnd4HBearish']['observations']}** closed lower 24 hours later.",
       "- Baseline windows overlap and do not represent independent trades. Historical event results should be interpreted relative to these background rates.",
       "",
       "## Outcomes (overlapping break episodes deduplicated)",
       "| Segment | Frozen boxes | Breaks | Retest rejections | 6x4H down after break | 6x4H down after retest |",
       "|---|---:|---:|---:|---:|---:|",
    ]
    for name,lab in (("all","Entire complete archive"),
                     ("before2026Jul","Before Jul 2026"),
                     ("since2026Jul","Jul–Sep 2026 (previously examined)")):
       x=a[name]
       d=f"{x['breakFollowThroughDown6bar']}/{x['afterBreak6barObserved']}" if x['afterBreak6barObserved'] else "n/a"
       rr=f"{x['retestFollowThroughDown6bar']}/{x['afterRetest6barObserved']}" if x["afterRetest6barObserved"] else "n/a"
       lines.append(f"| {lab} | {formed[name]} | {x['brokenSupportWithin7d']} | {x['retestRejected']} | {d} | {rr} |")
    lines+=["","## Selected strictly historical examples",
            "| Frozen date TSİ | Zone (USDT) | Break date TSİ | Result | 6x4H after break |",
            "|---|---|---|---|---|"]
    for row in report["historicalExamples"][:12]:
       p=(f"{row['next6AfterBreakPct']:+.2f}%" if row.get("next6AfterBreakPct") is not None else "pending")
       lines.append(f"| {row['frozenTSI']} | {row['low']:.2f}–{row['high']:.2f} | {row['breakTSI'] or 'No break'} | {row['state']} | {p} |")
    lines+=["","## Limitations",
          "- The supplied manual 87.50–95.00 region does not prove an ICT breaker, only support/resistance flip hypothesis.",
          "- The band size and density rules are exploratory, not independently validated or fit on a completely unseen test set.",
          "- Downward 4H follow-through is not the same as a profitable SHORT after costs, stops and fills.",
          "- This historical archive is previously inspected; no statistical significance or live efficacy claim.",
          "- The daily close and 4H close boundaries both use UTC; TSİ is rendered only for convenience.",
          "- No live orders and no changes to BTC/ETH/SOL production.",
          ""]
    return "\n".join(lines)


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--start",default="2025-01")
    cli.add_argument("--end",default="2026-09")
    cli.add_argument("--workers",type=int,default=6)
    cli.add_argument("--out",default="forward/v81_wide_zones/latest.json")
    cli.add_argument("--markdown",default="forward/v81_wide_zones/latest.md")
    args=cli.parse_args()
    four,daily,proofs=official_history(args.start,args.end,args.workers)
    boxes=discover_boxes(four,daily)
    all_rows,episodes=independent_events(boxes,four)
    split=SPLIT
    pre=[x for x in episodes if x["frozenTs"]<split]
    post=[x for x in episodes if x["frozenTs"]>=split]
    def trim(x):
        return {k:v for k,v in x.items() if k!="formationScore"}
    examples=sorted(episodes,key=lambda r:(r.get("breakTs") or 0,r["frozenTs"]),reverse=True)
    enriched=[{**trim(row),"frozenTSI":ts_istanbul(row["frozenTs"]),
               "breakTSI":ts_istanbul(row["breakTs"]) if row.get("breakTs") is not None else None,
               "retestTSI":ts_istanbul(row["retestTs"]) if row.get("retestTs") is not None else None}
              for row in examples]
    report={
      "mode":"SOL_V81_DAILY_4H_HISTORICAL_WIDE_ZONE_CAUSAL_STUDY_NO_ORDERS",
      "status":"DIAGNOSTIC_ONLY_NOT_A_VALIDATED_SIGNAL",
      "createdUTC":datetime.now(timezone.utc).isoformat(),
      "period":{"start":args.start,"end":args.end,
                "previouslyExaminedOutOfSampleNotValid":"2026-07-01 onwards"},
      "market":"Binance USD-M SOLUSDT perpetual",
      "source":"Official Binance Futures monthly 1H ZIP + verified .CHECKSUM; exact 4H and Daily aggregation",
      "sha256VerifiedArchives":len(proofs),
      "fourHourCandles":len(four),"dailyCandles":len(daily),
      "method":{"bandWidthPctOfLow":WIDTH_RATIO*100,
                "dailyLookback":DAILY_LOOKBACK,
                "fourHourLookback":FOUR_LOOKBACK,
                "dailyClosesMin":MIN_DAILY_CLOSES,
                "fourHourClosesMin":MIN_FOUR_CLOSES,
                "breakMarginPriorATR14":BREAK_PAD_ATR,
                "breakDeadline4HCandles":MAX_BREAK_WAIT_4H,
                "retestDeadline4HCandles":MAX_RETEST_4H,
                "deduplicateBreaksWithinDays":7,
                "manualPriceBoundsUsedForDetection":False,
                "MACDUsed":False},
      "allBoxesFrozenBeforeOutcome":len(all_rows),
      "boxFormationCounts":{"all":len(all_rows),
              "before2026Jul":sum(x["frozenTs"]<SPLIT for x in all_rows),
              "since2026Jul":sum(x["frozenTs"]>=SPLIT for x in all_rows)},
      "uniqueBrokenEpisodes":len(episodes),
      "controlBaselines":trend_control_baselines(four,daily),
      "summary":{"all":safe_summary(episodes),
                 "before2026Jul":safe_summary(pre),
                 "since2026Jul":safe_summary(post)},
      "historicalExamples":enriched[:30],
      "allFrozenBoxEvents":[trim(r) for r in all_rows],
      "limitations":["User's hand-drawn 87.5–95 zone is not an algorithm input.",
                     "8.5% fixed wide box is an unvalidated research hypothesis.",
                     "Historic labels can be inspected only after a box is frozen.",
                     "No 1H trade entries, PnL, institutional orderbook, execution cost, funding or slippage simulated.",
                     "This previously examined archive is not independent out-of-sample.",
                     "An ICT breaker needs additional sweep/structural proof not supplied here."],
      "brokerOrders":False,
      "mainProductionModified":False,
      "liveTradingApproved":False,
    }
    output=Path(args.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    md=Path(args.markdown);md.parent.mkdir(parents=True,exist_ok=True)
    md.write_text(render_md(report),encoding="utf-8")
    print("V81_WIDE_ZONES_COMPLETED",report["sha256VerifiedArchives"],
          report["allBoxesFrozenBeforeOutcome"],report["uniqueBrokenEpisodes"],
          report["summary"]["all"],flush=True)


if __name__=="__main__":
    main()
