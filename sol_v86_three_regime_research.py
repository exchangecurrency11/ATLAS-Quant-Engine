#!/usr/bin/env python3
"""SOL V8.6: three market states instead of blindly following Daily+4H trend.

All decisions use already CLOSED UTC 4H+Daily+1H candles, no future labels.
Observation schedule: exactly one 4H close at 20:00 UTC (23:00 TSİ)
per day. The response is measured 24h later (6 full 4H candles) so
sample outcome windows DON'T overlap in a contiguous verified archive.

Three candidate signals:
* TREND_CONTINUATION_LONG / TREND_CONTINUATION_SHORT
* RELIEF_BOUNCE_LONG / RELIEF_BOUNCE_SHORT (countertrend, aggressive)
* REVERSAL_UP / REVERSAL_DOWN (structural regime transition)

Three abstain outcomes:
* OVERSOLD_BOUNCE_RISK / OVERBOUGHT_PULLBACK_RISK
* MIXED_REGIME_NO_SIGNAL
* NO_CLOSED_1H_CONFIRMATION

No MACD. Uses chart S/R sweep proxy, SMA100/200, RSI14, volume, and
one-hour 4-candle microstructure (not an institutional order book).
Only SOL Binance USD-M futures officially SHA256-verified 1H archive.
These periods were already inspected in V8.5; no independent prospective
sample. No orders or approvals, no asserted 75% predictive edge.
"""
from __future__ import annotations
from bisect import bisect_right
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import argparse,json,math

from sol_v85_dual_regime_research import (
    HOUR,FOUR,DAY,verified_history,rolling_sma,rolling_rsi14,iso)
from sol_v82_fib_pivot_confluence import wilson_lower

SESSION_4H_CLOSE_UTC_HOUR=20
NEXT_4H_BARS=6
MIN_DAILY_SMA=200
RSI_EXTREME_LOW=30
RSI_EXTREME_HIGH=70
RSI_NO_CHASE_LOW=35
RSI_NO_CHASE_HIGH=65
RSI_MOMENTUM_LONG=50
RSI_MOMENTUM_SHORT=50
RVOL_REJECTION=1.20
MIN_EVENTS_FOR_RESEARCH=30


def last_four_1h(one,fourbar):
    b=fourbar
    bars=[x for x in one if b["t"]<=x["t"]<b["t"]+FOUR]
    if len(bars)!=4 or any(bars[k]["t"]!=b["t"]+HOUR*k for k in range(4)):
        raise ValueError("4H_ONE_HOUR_CONSTITUENTS_NOT_CONTIGUOUS")
    if any(abs(v)>max(1e-5,abs(agg)*2e-6) for v,agg in (
          (bars[0]["o"]-b["o"],b["o"]),
          (max(x["h"] for x in bars)-b["h"],b["h"]),
          (min(x["l"] for x in bars)-b["l"],b["l"]),
          (bars[-1]["c"]-b["c"],b["c"]),
          (sum(x["v"] for x in bars)-b["v"],b["v"]))):
        raise ValueError("4H_CONSTITUENT_OHLCV_DIFFERENCE")
    return bars


def causal_daily_index(daily,close_ts):
    ends=[b["t"]+DAY for b in daily]
    k=bisect_right(ends,close_ts)-1
    if k<0 or ends[k]>close_ts:raise ValueError("NO_COMPLETE_DAILY")
    return k


def one_hour_evidence(one,four,i):
    """Four most recent 1H bars already CLOSED inside this completed 4H."""
    recent=last_four_1h(one,four[i])
    last=recent[-1]
    prev=recent[:-1]
    bear=(last["c"]<last["o"] and last["c"]<min(p["l"] for p in prev))
    bull=(last["c"]>last["o"] and last["c"]>max(p["h"] for p in prev))
    # 1H bullish/bearish rejection/sweep of past 3 closed 1H bars
    sweep_low=(last["l"]<min(p["l"] for p in prev)
               and last["c"]>min(p["l"] for p in prev)
               and last["c"]>last["o"])
    sweep_high=(last["h"]>max(p["h"] for p in prev)
                and last["c"]<max(p["h"] for p in prev)
                and last["c"]<last["o"])
    return {"1HBullBOS":bull,"1HBearBOS":bear,
            "1HBullSweep":sweep_low,"1HBearSweep":sweep_high,
            "last1HClose":last["c"],
            "closedAtUTC":iso(last["t"]+HOUR)}


def regime_at_close(one,four,daily,i,prepared):
    """Returns point-in-time label, no after-timeframe candle ever referenced."""
    b=four[i]
    cutoff=b["t"]+FOUR
    dk=causal_daily_index(daily,cutoff)
    fv=prepared["four"]
    dv=prepared["daily"]
    if i<220 or dk<200:
        return None
    f100,f200=fv["s100"][i],fv["s200"][i]
    d100,d200=dv["s100"][dk],dv["s200"][dk]
    fr,dr=fv["rsi"][i],dv["rsi"][dk]
    if None in (f100,f200,d100,d200,fr,dr):
        return None
    price=b["c"]
    dprice=daily[dk]["c"]
    micro=one_hour_evidence(one,four,i)
    prev4=four[i-1]
    before=four[i-8:i]
    prev_high=max(q["h"] for q in before)
    prev_low=min(q["l"] for q in before)
    volume20=sum(q["v"] for q in four[i-20:i])/20
    rvol=(b["v"]/volume20) if volume20>0 else None
    zone_high=prev_high
    zone_low=prev_low
    # Descriptive DAILY price-context and 4H price-context; unlike V8.5
    # DO NOT demand stale Daily SMA100/SMA200 order to match for a trend.
    bearish=(price<f100 and f100<f200 and
             dprice<d100 and dr<50)
    bullish=(price>f100 and f100>f200 and
             dprice>d100 and dr>50)
    strong_down=(price<prev4["c"] and b["l"]<prev_low
                 and (rvol is None or rvol>=.8))
    strong_up=(price>prev4["c"] and b["h"]>prev_high
               and (rvol is None or rvol>=.8))
    bounce_bull=(micro["1HBullBOS"] or micro["1HBullSweep"])
    bounce_bear=(micro["1HBearBOS"] or micro["1HBearSweep"])
    reversal_bull=(dprice>d100 and dr>50 and
                   price>f100 and fr>50 and strong_up and bounce_bull)
    reversal_bear=(dprice<d100 and dr<50 and
                   price<f100 and fr<50 and strong_down and bounce_bear)

    state="MIXED_REGIME_NO_SIGNAL"
    side=None
    reason="No causal agreement at Daily+4H with candle confirmation"
    # Countertrend bounce risk is a THREAT FIRST; reserve long only
    # for a closed bullish 1H rejection. Same symmetric logic for bullish.
    if bearish and (fr<=RSI_EXTREME_LOW or dr<=RSI_EXTREME_LOW):
        if bounce_bull:
            state="RELIEF_BOUNCE_LONG"
            side="LONG"
            reason="Bear trend + RSI extreme + bullish 1H rejection/BOS; countertrend"
        else:
            state="OVERSOLD_BOUNCE_RISK"
            reason="Bear trend + RSI <=30; no bullish 1H reversal confirmation"
    elif bullish and (fr>=RSI_EXTREME_HIGH or dr>=RSI_EXTREME_HIGH):
        if bounce_bear:
            state="RELIEF_BOUNCE_SHORT"
            side="SHORT"
            reason="Bull trend + RSI extreme + bearish 1H rejection/BOS; countertrend"
        else:
            state="OVERBOUGHT_PULLBACK_RISK"
            reason="Bull trend + RSI >=70; no bearish 1H reversal confirmation"
    elif reversal_bull and not bullish:
        state="REVERSAL_UP_CANDIDATE"
        side="LONG"
        reason="Price retakes Daily SMA100 & 4H SMA100, daily/4h RSI>50, 4H/1H BOS"
    elif reversal_bear and not bearish:
        state="REVERSAL_DOWN_CANDIDATE"
        side="SHORT"
        reason="Price loses Daily SMA100 & 4H SMA100, daily/4h RSI<50, 4H/1H BOS"
    elif bearish and fr>=RSI_NO_CHASE_LOW and fr<RSI_MOMENTUM_SHORT:
        if micro["1HBearBOS"] or micro["1HBearSweep"]:
            state="TREND_CONTINUATION_SHORT"
            side="SHORT"
            reason="Bear Daily price/RSI + bear 4H SMA+price and closed 1H bear confirmation"
        else:
            state="NO_CLOSED_1H_CONFIRMATION"
            reason="Downtrend exists, but closed 1H rejection/BOS absent"
    elif bullish and fr<=RSI_NO_CHASE_HIGH and fr>=RSI_MOMENTUM_LONG:
        if micro["1HBullBOS"] or micro["1HBullSweep"]:
            state="TREND_CONTINUATION_LONG"
            side="LONG"
            reason="Bull Daily price/RSI + bull 4H SMA+price and closed 1H bull confirmation"
        else:
            state="NO_CLOSED_1H_CONFIRMATION"
            reason="Uptrend exists, but closed 1H rejection/BOS absent"
    elif bearish:
        state="BEAR_TREND_REST_NO_TRADE"
        reason="Bear context without qualifying RSI momentum range"
    elif bullish:
        state="BULL_TREND_REST_NO_TRADE"
        reason="Bull context without qualifying RSI momentum range"

    return {
        "decisionKnownUTC":iso(cutoff),
        "latestCompleteDailyUTC":iso(daily[dk]["t"]+DAY),
        "label":state,"side":side,"reason":reason,
        "close":round(price,7),
        "dailyClose":round(dprice,7),
        "RSI4H":round(fr,3),"RSIDaily":round(dr,3),
        "SMA1004H":round(f100,6),"SMA2004H":round(f200,6),
        "SMA100Daily":round(d100,6),"SMA200Daily":round(d200,6),
        "SMA100AboveSMA200Daily":d100>d200,
        "SMA100AboveSMA2004H":f100>f200,
        "relativeVolume4H":round(rvol,4) if rvol is not None else None,
        "prior8BarHigh":round(zone_high,6),
        "prior8BarLow":round(zone_low,6),
        "daily4HBearContext":bearish,"daily4HBullContext":bullish,
        "last4HStructureHighBreak":strong_up,
        "last4HStructureLowBreak":strong_down,
        "micro":micro,"MACDUsed":False,
        "WyckoffUnproven":True,
        "noInstitutionalOrderbookInferred":True,
    }


def features(four,daily):
    def frame(bars):
        close=[x["c"] for x in bars]
        return {"s100":rolling_sma(close,100),
                "s200":rolling_sma(close,200),
                "rsi":rolling_rsi14(close)}
    return {"four":frame(four),"daily":frame(daily)}


def scan_daily_checkpoints(one,four,daily):
    prep=features(four,daily)
    events=[]
    total=0
    for i,b in enumerate(four):
        end=b["t"]+FOUR
        # Exactly 23:00 Turkey = 20:00 UTC. One nonoverlapping 24h
        # outcome per UTC day, rather than 6 overlapping outcomes.
        if datetime.fromtimestamp(end,timezone.utc).hour!=SESSION_4H_CLOSE_UTC_HOUR:
            continue
        if i+NEXT_4H_BARS>=len(four):continue
        row=regime_at_close(one,four,daily,i,prep)
        if row is None:continue
        total+=1
        # Future data is used for OUTCOME ONLY, never as model features.
        future_close=four[i+NEXT_4H_BARS]["c"]
        next_close=four[i+1]["c"]
        sign=(future_close-row["close"])/row["close"]*100
        four_sign=(next_close-row["close"])/row["close"]*100
        row["outcome24hPct"]=round(sign,5)
        row["outcomeNext4hPct"]=round(four_sign,5)
        row["correct24hDirection"]=(sign>0 if row["side"]=="LONG"
                                     else sign<0 if row["side"]=="SHORT" else None)
        row["correctNext4hDirection"]=(four_sign>0 if row["side"]=="LONG"
                                     else four_sign<0 if row["side"]=="SHORT" else None)
        row["candleAfterUTC"]=iso(four[i+NEXT_4H_BARS]["t"]+FOUR)
        events.append(row)
    return events,{"sampledIndependent24hAnchors":total,
                   "lastSampleUTC":events[-1]["decisionKnownUTC"] if events else None}


def summarize(events):
    direction=[z for z in events if z["side"] in ("LONG","SHORT")]
    hits=sum(z["correct24hDirection"] for z in direction)
    hits4=sum(z["correctNext4hDirection"] for z in direction)
    n=len(direction)
    alln=len(events)
    return {
      "allNonoverlappingDailyCheckpoints":alln,
      "directionalSignals":n,
      "abstentions":alln-n,
      "signalCoveragePct":round(100*n/alln,2) if alln else None,
      "correct24H":hits,
      "hitRate24hPct":round(100*hits/n,2) if n else None,
      "wilson95LowerPct":round(100*wilson_lower(hits,n),2) if n else None,
      "correctNext4h":hits4,
      "hitRateNext4hPct":round(100*hits4/n,2) if n else None,
      "min30Signals":n>=MIN_EVENTS_FOR_RESEARCH,
      "reaches75Observed":n>0 and hits/n>=.75,
      "stateCounts":dict(Counter(z["label"] for z in events)),
      "directionalBreakdown":{side: {
          "signals":sum(z["side"]==side for z in direction),
          "correct":sum(z["side"]==side and z["correct24hDirection"] for z in direction),
        } for side in ("LONG","SHORT")},
    }


def per_label(allrows):
    return {label:summarize([z for z in allrows if z["label"]==label])
            for label in sorted({z["label"] for z in allrows})}


def render(report):
    a=report["results"]
    lines=[
      "# V8.6 SOL — Trend continuation vs countertrend relief vs reversal",
      "",
      "**Experimental classification of SOL Daily+4H+1H, no trading orders.**",
      "",
      "## Fixed pretest rules",
      "- One daily observation at exactly 20:00 UTC / 23:00 TSİ; ensuing 6x4H close (24h) outcomes don't overlap.",
      "- SMA100/200 actual simple averages on Daily and 4H, RSI14 Wilder, last 4 true 1H candles, 4H prior8 swing references, relative volume20.",
      "- Bear continuation: 4H below SMA100 with SMA100<SMA200; latest closed Daily below SMA100 and RSI<50; 4H RSI 35..50 and bearish 1H BOS/sweep.",
      "- Oversold: current 4H or Daily RSI <=30 in bear context. If bullish 1H rejection then relief bounce candidate LONG; else ABSTAIN.",
      "- Symmetric bull continuation, overbought pullback and reversal-candidate conditions. Reversal candidates require closed multi-timeframe price reclaim/loss and 1H plus 4H microstructure.",
      "- Daily SMA100/SMA200 CROSS is not a mandatory hard gate for existing trend: daily SMA lags 4H and price context; current daily order still reported.",
      "- Assesses next 4h and 24h close direction only. No simulated fills, fee-adjusted PnL or false win rate claim.",
      "- This reuses previously investigated 2023–26 data; no untouched holdout and no claim of forecast calibration.",
      "",
      "| Segment | Checkpoints | Signals | Coverage | 24h hit | Next 4h hit |",
      "|---|---:|---:|---:|---:|---:|"]
    for name,lab in (("older2023_2024","2023–24"),
                     ("recent2025_2026","2025–Sep2026"),
                     ("allCombined","Combined")):
        v=a[name]["all"]
        def fmt(key):
            return str(v[key]) if v[key] is not None else "n/a"
        lines.append(f"| {lab} | {v['allNonoverlappingDailyCheckpoints']} | "
          f"{v['directionalSignals']} | {fmt('signalCoveragePct')}% | "
          f"{v['correct24H']}/{v['directionalSignals']} ({fmt('hitRate24hPct')}%) | "
          f"{v['correctNext4h']}/{v['directionalSignals']} ({fmt('hitRateNext4hPct')}%) |")
    lines.extend(["",
      "## Breakdown by actual frozen label (combined)",
      "| Label | Signals | Direction right | 24h accuracy |",
      "|---|---:|---:|---:|"])
    for name,v in a["allCombined"]["byLabel"].items():
        if not v["directionalSignals"]:continue
        lines.append(f"| {name} | {v['directionalSignals']} | "
                     f"{v['correct24H']} | {v['hitRate24hPct']}% |")
    lines.extend(["","## Constraints",
       "- Daily checkpoint outcome windows are disjoint; historical bars reused for SMA warmup are not independent training data.",
       "- SOW/LPSY and liquidity sweeps are chart inferences; no proof of actual institutional order placement.",
       "- No BTC/ETH extrapolation from SOL backtest; no claim that 75% goal was reached.",
       "- The user-drawn 87.50–95 rectangle is not force-fitted into historical detection.",
       "- All results historical, not prospective; source archive completeness is enforced, missing months fail.",
       ""])
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--json",default="forward/v86_three_regimes/latest.json")
    p.add_argument("--markdown",default="forward/v86_three_regimes/latest.md")
    opt=p.parse_args()
    records={}
    source={}
    for name,start,end in (("older2023_2024","2023-01","2024-12"),
                           ("recent2025_2026","2025-01","2026-09")):
        one,four,daily,nmonths=verified_history(start,end)
        rows,audit=scan_daily_checkpoints(one,four,daily)
        records[name]=rows
        source[name]={"monthCount":nmonths,
                      "firstHourUTC":iso(one[0]["t"]),
                      "lastHourCloseUTC":iso(one[-1]["t"]+HOUR),
                      "oneHourBars":len(one),"fourHourBars":len(four),
                      "dailyBars":len(daily),**audit}
        print("V86_PERIOD_COMPLETE",name,audit,len(rows),flush=True)
    records["allCombined"]=records["older2023_2024"]+records["recent2025_2026"]
    report={
      "mode":"SOL_V86_CAUSAL_BOUNCE_CONTINUATION_REVERSAL_REGIME_RESEARCH",
      "status":"RESEARCH_CLASSIFIER_NO_AUTOMATED_ORDER",
      "atUTC":datetime.now(timezone.utc).isoformat(),
      "source":"Official Binance Futures USD-M SOLUSDT 1H ZIPs with .CHECKSUM",
      "checksummedMonths":sum(x["monthCount"] for x in source.values()),
      "sourcePeriods":source,
      "methodFrozenBeforePerformance":True,
      "nonoverlap24hCheckpoints":True,
      "checkpointsAtUTC":"20:00",
      "noMACD":True,
      "hasNoOrderCalls":True,
      "currentBTCETHNotBacktested":True,
      "results":{
        key:{"all":summarize(rows),"byLabel":per_label(rows)}
        for key,rows in records.items()},
      "examplesRecent":records["recent2025_2026"][-18:],
      "currentProductionModified":False,
      "liveTradingApproved":False,
      "historicalDataPreviouslyInspected":True,
      "targetAccuracyPct":75,
    }
    out=Path(opt.json);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    md=Path(opt.markdown);md.parent.mkdir(parents=True,exist_ok=True)
    md.write_text(render(report))
    print("V86_REGIME_TEST_COMPLETED",report["checksummedMonths"],
          json.dumps({k:v["all"] for k,v in report["results"].items()}),flush=True)


if __name__=="__main__":
    main()
