#!/usr/bin/env python3
"""SOL V8.3 fixed, causal confluence study (2023-2026); paper only.

Daily+4H broad support boxes -> break -> bearish retest (existing V8.1)
+ prior-completed daily pivot, Fibonacci V8.2, 4H/Daily RSI/EMA,
4H OHLCV Wyckoff-inspired SOW/LPSY proxies, chart-derived bearish
Order Block/FVG, volume and optional closed-1H confirmation.

Predicts only whether 6 subsequent CLOSED 4H candles finish lower than the
retest close. Also separately simulates 4H-entry paper SHORTs at NEXT 4H
OPEN with same-candle stop-first, 2R target, six-candle time exit, 9bps
per side, planned <=0.5 USD equity risk at 10x isolated.

This is exploratory already-inspected history, NOT an independent forward
experiment. All filters/thresholds written before running and not optimised
to the user's 75% benchmark. Institutional orders/Wyckoff phases NOT
confirmed by OHLCV. Funding/OI unavailable point-in-time across sample.
No broker calls, no production edits.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json,math
from pathlib import Path
from statistics import median

from sol_v81_htf_role_flip_research import official_history, atr, iso
from sol_v82_fib_pivot_confluence import evaluate as v82_evaluate, wilson_lower
from sol_v81_historical_wide_zone_study import SECS4, DAY, ts_istanbul
from backtest_retest_long_v4 import ema, rsi14
from market_structure import analyze

FEE_SLIP_ONE_SIDE=0.0009
RISK_CAP_USDT=.5
START_EQUITY_USDT=100
LEVERAGE_CAP=10
WINDOW_4H=6
SCORE_THRESH=4
SAMPLE_MIN=30
RSI_MIN_FOR_NO_CHASE=30


def true_range_position(bar):
    span=bar["h"]-bar["l"]
    return (bar["c"]-bar["l"])/span if span>0 else 0.5


def relative_volume(bars,index,window=20):
    if index<window:raise ValueError("RVOL_INSUFFICIENT")
    baseline=sum(b["v"] for b in bars[index-window:index])/window
    return bars[index]["v"]/baseline if baseline>0 else None


def causal_indicators(four,daily,retest_i):
    """Only 4H and complete Daily bars as at 4H retest CLOSE."""
    cutoff=four[retest_i]["t"]+SECS4
    day=[x for x in daily if x["t"]+DAY<=cutoff]
    bars=four[:retest_i+1]
    if len(day)<55 or len(bars)<200:
        raise ValueError("INDICATORS_NOT_WARM")
    f_close=[b["c"] for b in bars]
    d_close=[b["c"] for b in day]
    f_rsi=rsi14(f_close)
    d_rsi=rsi14(d_close)
    f20,f50,f200=(ema(f_close,n) for n in (20,50,200))
    d20,d50,d200=(ema(d_close,n) for n in (20,50,200))
    four_bear=(f_close[-1]<f20 and f_close[-1]<f50)
    daily_bear=(d_close[-1]<d20 and d_close[-1]<d50)
    return {
      "4hRSI14":round(f_rsi,3),"dailyRSI14":round(d_rsi,3),
      "4hEMA20":round(f20,4),"4hEMA50":round(f50,4),"4hEMA200":round(f200,4),
      "dailyEMA20":round(d20,4),"dailyEMA50":round(d50,4),"dailyEMA200":round(d200,4),
      "dailyBarClosedUTC":iso(day[-1]["t"]+DAY),
      "MACDFreeEMABear":four_bear and daily_bear,
      "RSIBear":f_rsi<50 and d_rsi<50,
      "RSI30OrAboveNotExtremelyOversold":f_rsi>=RSI_MIN_FOR_NO_CHASE,
      "EMA200FourContextBear":f_close[-1]<f200,
      "EMA200DailyContextBear":d_close[-1]<d200 if len(day)>=200 else None,
      "EMA200DailyWarm":len(day)>=200,
    }


def wyckoff_proxy(four,break_i,retest_i):
    """Only proxies, NOT a Wyckoff phase classification.

    Weakness (SOW): broken support on a down-volume-expansion 4H close.
    LPSY-like: retest fails below low of former base with lower-high and
    contained/reduced volume vs the break, or significant upper rejection.
    Spring/UTAD detection would require wider structure/volume context and
    remains UNVERIFIED; never claim these events happened.
    """
    broken=four[break_i]
    retest=four[retest_i]
    rv_break=relative_volume(four,break_i)
    rv_retest=relative_volume(four,retest_i)
    prior=four[max(0,break_i-12):break_i]
    prev_range_high=max(x["h"] for x in prior)
    close_pos=true_range_position(broken)
    sow=bool(rv_break is not None and rv_break>=1.20
             and close_pos<=.40 and broken["c"]<broken["o"])
    body=max(1e-9,abs(retest["o"]-retest["c"]))
    upper_wick=retest["h"]-max(retest["o"],retest["c"])
    lower_high=retest["h"]<prev_range_high
    lpsy=bool(retest["c"]<retest["o"] and lower_high and
              ((rv_retest is not None and rv_break is not None
                and rv_retest<=rv_break)
               or upper_wick>=.5*body))
    return {
      "breakRelativeVolume":round(rv_break,4) if rv_break is not None else None,
      "retestRelativeVolume":round(rv_retest,4) if rv_retest is not None else None,
      "breakCloseLocationInRange":round(close_pos,4),
      "lowerHighRelativeTo12Prebreak4H":lower_high,
      "wyckoffSOWProxy":sow,
      "wyckoffLPSYProxy":lpsy,
      "wyckoffCombined":sow and lpsy,
      "provenSpring":False,"provenUTAD":False,
      "wyckoffClassification":"OHLCV proxies, NOT proven Wyckoff distribution phase",
    }


def chart_order_blocks(four,retest_i,at_ts,atr14):
    # Chart-structure function only sees already closed bars. Restrict to
    # last 250 bars; OB is eligible only if known BEFORE retest OPEN.
    history=four[max(0,retest_i-250):retest_i+1]
    if history[-1]["t"]+SECS4!=at_ts:
        raise ValueError("CHART_LOOKAHEAD")
    s=analyze(history,"4hour",as_of=at_ts)
    if s["status"]!="READY":
        raise ValueError("CHART_STRUCTURE_UNAVAILABLE")
    bar=four[retest_i]
    touch=lambda lo,hi:bar["l"]<=hi+.20*atr14 and bar["h"]>=lo-.20*atr14
    ob=[z for z in s["orderBlocks"]
        if z["side"]=="bearish"
        and z["confirmedAt"]<=bar["t"]
        and z.get("state")!="invalidated"
        and touch(z["wick"]["low"],z["wick"]["high"])]
    fvg=[z for z in s["fvg"]
         if z["side"]=="bearish"
         and z["confirmedAt"]<=bar["t"]
         and z.get("state")=="open"
         and touch(z["low"],z["high"])]
    return {"bearishOBConfluence":bool(ob),
            "bearishFVGConfluence":bool(fvg),
            "OBcount":len(ob),"FVGcount":len(fvg),
            "actualInstitutionalOrdersConfirmed":False}


def last_hour_rejection(one,four,retest_i):
    """At retest 4H close only; four 1H constituents must be contiguous."""
    bar=four[retest_i]
    ends=bar["t"]+SECS4
    hours=[b for b in one if bar["t"]<=b["t"]<ends]
    if len(hours)!=4 or any(hours[i+1]["t"]-hours[i]["t"]!=3600 for i in range(3)):
        raise ValueError("FOUR_1H_CONSTITUENTS_MISSING")
    if abs(hours[-1]["c"]-bar["c"])>max(1e-7,bar["c"]*1e-6):
        raise ValueError("1H_4H_MISMATCH")
    last=hours[-1]
    return {"last1hClosedUTC":iso(ends),
            "hourlyBearishClose":last["c"]<last["o"] and
                last["c"]<hours[-2]["c"],
            "allFourConstituentsVerified":True}


def paper_short_next4h(four,event,at_i,atr_prev,stop_style="full_box"):
    """Independent event-based hypothetical short: next 4H open only."""
    if at_i+WINDOW_4H>=len(four):return None
    entry=four[at_i+1]["o"]
    if stop_style not in ("full_box","local_retest_wick"):
        raise ValueError("UNKNOWN_STOP_MODEL")
    stop=(max(four[at_i]["h"],event["boxHigh"]) if stop_style=="full_box"
          else four[at_i]["h"])+.15*atr_prev
    gap_after_close=entry
    d=stop-entry
    if not entry>0 or not .001<=d/entry<=.04:
        return {"status":"SKIPPED_INVALID_STOP_OR_GAP","stopStyle":stop_style}
    tp=entry-2*d
    exit_price=four[at_i+WINDOW_4H]["c"]
    reason="TIME_24H"
    exit_time=at_i+WINDOW_4H
    for j in range(at_i+1,at_i+1+WINDOW_4H):
        b=four[j]
        # Gap-through-stop takes worse actual opening price.
        if b["o"]>=stop:
            exit_price=b["o"]
            reason="STOP_GAP_THROUGH"
            exit_time=j
            break
        if b["h"]>=stop:
            exit_price=stop
            reason="STOP_FIRST"
            exit_time=j
            break
        if b["l"]<=tp:
            exit_price=tp
            reason="TARGET_2R"
            exit_time=j
            break
    cost=(entry+exit_price)*FEE_SLIP_ONE_SIDE
    # Position sizing reserves fee/slippage at the planned STOP price,
    # not entry-price twice; ordinary stop loss stays <= risk cap.
    qty=min(RISK_CAP_USDT/(d+FEE_SLIP_ONE_SIDE*(entry+stop)),
            START_EQUITY_USDT*LEVERAGE_CAP/entry)
    dollars=qty*(entry-exit_price-cost)
    return {"status":"ILLUSTRATIVE_PAPER_ONLY","stopStyle":stop_style,
            "entryNext4HOpenUTC":iso(four[at_i+1]["t"]),
            "exitKnownUTC":iso(four[exit_time]["t"]+SECS4),
            "entryPrice":round(entry,5),
            "stopPrice":round(stop,5),
            "targetPrice":round(tp,5),
            "reason":reason,
            "plannedRiskUSDT":RISK_CAP_USDT,
            "marginUSDT":round(qty*entry/LEVERAGE_CAP,5),
            "netPnLUSDT":round(dollars,6),
            "netR":round((entry-exit_price-cost)/d,6),
            "gapsCanExceedPlannedRisk":reason=="STOP_GAP_THROUGH"}


def features_for_event(one,four,daily,event):
    if not event.get("retestClosedUTC") or not event.get("breakUTC"):
        raise ValueError("MISSING_CONFIRMED_BREAK_OR_RETEST")
    index={bar["t"]+SECS4:i for i,bar in enumerate(four)}
    i=index.get(int(datetime.fromisoformat(event["retestClosedUTC"].replace("Z","+00:00")).timestamp()))
    br=index.get(int(datetime.fromisoformat(event["breakUTC"].replace("Z","+00:00")).timestamp()))
    if i is None or br is None or br>=i:
        raise ValueError("INCONSISTENT_TIMING")
    ind=causal_indicators(four,daily,i)
    w=wyckoff_proxy(four,br,i)
    av=atr(four,i-1)
    ob=chart_order_blocks(four,i,four[i]["t"]+SECS4,av)
    h=last_hour_rejection(one,four,i)
    vol=relative_volume(four,br)
    # Eight evidence votes (separately auditable, no future information).
    votes={
      "Fibonacci":bool(event["fibHit"]),
      "PreviousDayPivot":bool(event["pivotHit"]),
      "RSI14_Daily4H":bool(ind["RSIBear"] and ind["RSI30OrAboveNotExtremelyOversold"]),
      "EMA20_50_Daily4H":bool(ind["MACDFreeEMABear"]),
      "WyckoffSOW_LPSYProxy":bool(w["wyckoffCombined"]),
      "OrderBlock_4H":bool(ob["bearishOBConfluence"]),
      "BreakHighVolume":bool(vol is not None and vol>=1.2),
      "LastClosed1HRejection":bool(h["hourlyBearishClose"]),
    }
    aux={"FVG_4H":bool(ob["bearishFVGConfluence"])}
    score=sum(votes.values())
    paper=paper_short_next4h(four,event,i,av,stop_style="full_box")
    local_paper=paper_short_next4h(four,event,i,av,stop_style="local_retest_wick")
    return {**event,"features":votes,"aux":aux,
            "confluenceScore8":score,"featureCount":len(votes),
            "WyckoffProxy":w,"indicators":ind,"OBFVG":ob,"last1H":h,
            "paperNext4H":paper,"paperAlternativeLocalRetestStop":local_paper,
            "featureKnownAtUTC":event["retestClosedUTC"]}


def segment_summary(rows,filter_fn):
    qualifying=[x for x in rows if filter_fn(x)]
    answered=[x for x in qualifying if x["future24hPct"] is not None]
    won=[x for x in answered if x["future24hPct"]<0]
    paper=[x["paperNext4H"] for x in answered if x["paperNext4H"]
           and x["paperNext4H"]["status"]=="ILLUSTRATIVE_PAPER_ONLY"]
    local=[x["paperAlternativeLocalRetestStop"] for x in answered
           if x["paperAlternativeLocalRetestStop"]
           and x["paperAlternativeLocalRetestStop"]["status"]=="ILLUSTRATIVE_PAPER_ONLY"]
    count=len(answered)
    rate=round(100*len(won)/count,2) if count else None
    return {
       "candidateRetests":len(qualifying),
       "answered24h":count,
       "directionCorrect":len(won),
       "directionHitPct":rate,
       "wilson95LowerPct":round(100*wilson_lower(len(won),count),2) if count else None,
       "sampleAtLeast30":count>=SAMPLE_MIN,
       "target75Observed":bool(rate is not None and rate>=75),
       "meets75With30":bool(rate is not None and rate>=75 and count>=SAMPLE_MIN),
       "median24hChangePct":round(median(x["future24hPct"] for x in answered),4) if answered else None,
       "paperTradesCompleted":len(paper),
       "paperPositivePnL":sum(x["netPnLUSDT"]>0 for x in paper),
       "paperWinPct":round(100*sum(x["netPnLUSDT"]>0 for x in paper)/len(paper),2) if paper else None,
       "paperNetUSDStandaloneSum":round(sum(x["netPnLUSDT"] for x in paper),4),
       "paperGapStopEvents":sum(x["gapsCanExceedPlannedRisk"] for x in paper),
       "localRetestStopSensitivityPostHoc":{
           "paperTrades":len(local),
           "wins":sum(x["netPnLUSDT"]>0 for x in local),
           "winRatePct":round(100*sum(x["netPnLUSDT"]>0 for x in local)/len(local),2) if local else None,
           "perEventHypotheticalPnLSumUSDT":round(sum(x["netPnLUSDT"] for x in local),4),
           "stopGapEvents":sum(x["gapsCanExceedPlannedRisk"] for x in local),
           "notValidForwardComparison":True,
           "source":"After discovering full-zone stop allowed zero trades, local stop added as post-hoc execution sensitivity only."},
       "notIndependentlyValidated":True}


def all_filters():
    return {
       "00_BaseWideZoneRetest":lambda x:True,
       "01_RSI14Daily4H":lambda x:x["features"]["RSI14_Daily4H"],
       "02_EMA20_50Daily4H":lambda x:x["features"]["EMA20_50_Daily4H"],
       "03_WyckoffSOW_LPSYProxy":lambda x:x["features"]["WyckoffSOW_LPSYProxy"],
       "04_Fibonacci":lambda x:x["features"]["Fibonacci"],
       "05_PreviousDayPivot":lambda x:x["features"]["PreviousDayPivot"],
       "06_ChartOrderBlock":lambda x:x["features"]["OrderBlock_4H"],
       "07_BreakHighVolume":lambda x:x["features"]["BreakHighVolume"],
       "08_1HRejection":lambda x:x["features"]["LastClosed1HRejection"],
       "09_FibonacciAndPivot":lambda x:x["features"]["Fibonacci"] and x["features"]["PreviousDayPivot"],
       "10_Trend_RSI_EMA_Wyckoff":lambda x:x["features"]["RSI14_Daily4H"] and x["features"]["EMA20_50_Daily4H"] and x["features"]["WyckoffSOW_LPSYProxy"],
       "11_AllEightMandatory":lambda x:all(x["features"].values()),
       "12_Score4of8":lambda x:x["confluenceScore8"]>=SCORE_THRESH,
       "13_Score5of8":lambda x:x["confluenceScore8"]>=5,
       "14_FibAndScore4of8":lambda x:x["features"]["Fibonacci"] and x["confluenceScore8"]>=SCORE_THRESH,
       "15_Trend_Wyckoff_Fib":lambda x:x["features"]["EMA20_50_Daily4H"] and x["features"]["WyckoffSOW_LPSYProxy"] and x["features"]["Fibonacci"],
       "16_FVGextra":lambda x:x["aux"]["FVG_4H"],
    }


def run_period(start,end):
    four,daily,proofs=official_history(start,end,6)
    # Crucial: 1H is needed, but official_history only returns aggregated 4H,D.
    # Instead fetch identical monthly archives with verified checksums once more
    # for this pipeline: do not silently infer 1H signals from 4H candles.
    from download_binance_um_history import download_month,months_inclusive,month_start,month_end
    from concurrent.futures import ThreadPoolExecutor,as_completed
    monthly={}
    months=months_inclusive(start,end)
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(download_month,"SOLUSDT",m):m for m in months}
        for job in as_completed(futures):
            symbol,month,bars,proof=job.result()
            if symbol!="SOLUSDT" or month!=futures[job]:
                raise ValueError("INCORRECT_SOURCE_SOL")
            monthly[month]=bars
    one=[b for m in months for b in monthly[m]]
    if len(one)!=(month_end(end)-month_start(start))//3600:
        raise ValueError("1H_HISTORY_INCOMPLETE")
    if any(one[i]["t"]!=month_start(start)+i*3600 for i in range(len(one))):
        raise ValueError("1H_TIME_ALIGNMENT_INCOMPLETE")
    # Need historical RSI200 daily warmup. First events naturally arise later.
    retests,old_results,counts=v82_evaluate(four,daily)
    enriched=[]
    skipped_warmup=0
    for event in retests:
        try:
            enriched.append(features_for_event(one,four,daily,event))
        except ValueError as e:
            if str(e)=="INDICATORS_NOT_WARM":
                skipped_warmup+=1
            else:
                raise
    return enriched,{"verifiedSHA256Months":len(proofs),
                     "preexistingRetests":len(retests),
                     "excludedInitialRSIEMA50WarmupRetests":skipped_warmup,
                     "1hourBars":len(one),"4hourBars":len(four),"dailyBars":len(daily),
                     "events":counts}


def report_table(reports,segments):
    names=list(all_filters())
    lines=[
       "# SOL V8.3 — Wyckoff proxies + RSI + EMA + Fib + Daily pivot + Order Block + volume",
       "",
       "THIS IS EXPLORATORY HISTORICAL RESEARCH, NOT REAL TIME SUCCESS OR AN EXECUTABLE SIGNAL.",
       "All eight indicators are evaluated on already closed bars; all-eight, score and individual filters compared.",
       "75% target is a user benchmark; thresholds were frozen before the study, not tuned for the best result.",
       "",
       "## Immutable research rules",
       "- SOL Binance USD-M Futures official SOLUSDT 1H monthly .zip plus .CHECKSUM verification; 45 months total across 2023-24 and 2025-Sep2026.",
       "- V8.1 wide Daily+4H support zone frozen before the break, red retest below the band.",
       "- V8.2 Fib 38.2–61.8 retracement and Classic prior completed UTC Daily P/R1/R2/S1/S2.",
       "- RSI14 4H and Daily under 50 but 4H >=30; EMA20/50 trend below BOTH timeframes. EMA200 is context only. First 55 Daily candles lack sufficient RSI/EMA50 warmup and are excluded for all filters.",
       "- Wyckoff SOW proxy = broken support with RVOL>=1.2 and bearish close in bottom 40% of the range.",
       "- Wyckoff LPSY proxy = after break, failed upper retest below previous 12-bar high and volume contraction or upper wick.",
       "- Bearish Order Block = CHoCH/BOS previous opposite candle from OHLCV structure, known BEFORE the 4H retest opens; FVG also recorded.",
       "- Last closed 1H rejection and prior 20-bar 4H break relative-volume recorded.",
       "- Score = sum of 8 binary votes (FVG is extra, no score); no MACD.",
       "- Paper SHORT (separate metric): next 4H OPEN, stop beyond retest/box +0.15ATR, TP2R or 24h exit, stop-first, 9bps one-way, 100 USD 10x, <=0.5 USD planned risk. Gap-through stops can exceed planned risk.",
       "- Alternative local retest-wick stop +0.15 ATR is post-hoc sensitivity introduced after finding no full-box eligible fills; not a tested production choice.",
       "- No proof of genuine Wyckoff phases, UTAD, springs or institutional orders; chart-only proxies.",
       "",
       "| Filter | 2023–24 hit | 2025–Sep2026 hit | Combined hit | Combined count | Full-box paper trades | Local-wick paper trades / net USDT (post-hoc) |",
       "|---|---:|---:|---:|---:|---:|---:|"]
    for name in names:
        def render_rate(x):
            z=x[name]
            return (f"{z['directionCorrect']}/{z['answered24h']} ({z['directionHitPct']}%)"
                    if z["answered24h"] else "No signal")
        a=reports["older2023_2024"][name]
        b=reports["recent2025_2026"][name]
        c=reports["combined"][name]
        lines.append(f"| {name} | {render_rate(reports['older2023_2024'])} | "
                     f"{render_rate(reports['recent2025_2026'])} | "
                     f"{render_rate(reports['combined'])} | {c['answered24h']} | "
                     f"{c['paperTradesCompleted']} | "
                     f"{c['localRetestStopSensitivityPostHoc']['paperTrades']} / "
                     f"{c['localRetestStopSensitivityPostHoc']['perEventHypotheticalPnLSumUSDT']:+.4f} |")
    lines+=["",
      "## Caveats",
      "- Both periods are previously examined; they are NOT a new independent validation cohort.",
      "- Multiple filters were compared; selecting the highest percentage is data snooping.",
      "- The count of signals is low; Wilson 95% lower bounds must be reported.",
      "- Paper net USD sums are per independent event, not an executable one-position-at-a-time account.",
      "- Funding, maker/taker actual fees, realized fill quality, changing spreads, OI and market impact not reconciled.",
      "- Consecutive 24-hour outcomes can overlap; these are not automatically independent observations.",
      "- No real orders and no BTC/ETH/SOL production branch edits.",
    ]
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="forward/v83_full_confluence/latest.json")
    p.add_argument("--markdown",default="forward/v83_full_confluence/latest.md")
    args=p.parse_args()
    records={}
    proofs={}
    for label,a,b in (("older2023_2024","2023-01","2024-12"),
                      ("recent2025_2026","2025-01","2026-09")):
        print("V83_START",label,flush=True)
        rows,manifest=run_period(a,b)
        records[label]=rows
        proofs[label]=manifest
        print("V83_DONE",label,len(rows),flush=True)
    allrows=records["older2023_2024"]+records["recent2025_2026"]
    periods={**records,"combined":allrows,
             "recentSinceJuly2026":[x for x in records["recent2025_2026"]
               if x["retestClosedUTC"]>="2026-07-01T00:00:00Z"]}
    defs=all_filters()
    comparison={period:{name:segment_summary(rows,fn) for name,fn in defs.items()}
                for period,rows in periods.items()}
    output={
       "mode":"V83_SOL_WYCKOFF_RSI_EMA_FIB_PIVOT_OB_VOLUME_1H_CLOSED_HISTORICAL_RESEARCH",
       "status":"RESEARCH_ONLY_UNVALIDATED_NO_ORDERS",
       "generatedUTC":datetime.now(timezone.utc).isoformat(),
       "periods":{"older":"2023-01 to 2024-12","recent":"2025-01 to 2026-09"},
       "source":"Official Binance Futures USD-M SOLUSDT 1H ZIP+.CHECKSUM",
       "verifiedArchivedMonthsTotal":sum(x["verifiedSHA256Months"] for x in proofs.values()),
       "provenance":proofs,
       "featureSet":["Fibonacci","PreviousDayPivot","RSI14_Daily4H","EMA20_50_Daily4H",
                     "WyckoffSOW_LPSYProxy","OrderBlock_4H","BreakHighVolume","LastClosed1HRejection"],
       "auxiliaryFeature":"FVG_4H",
       "comparison":comparison,
       "eventObservations":{k:v for k,v in records.items()},
       "comparisonContaminatedByPastInvestigations":True,
       "multipleComparisonsUnadjusted":True,
       "predefinedGoalDirectionAccuracyPct":75,
       "noThresholdFittingAfterOutcome":True,
       "brokerOrders":False,"productionModified":False,
       "liveSignalEnabled":False,"actualWyckoffOrInstitutionalOrdersVerified":False,
    }
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=Path(args.markdown);md.parent.mkdir(parents=True,exist_ok=True)
    md.write_text(report_table(comparison,periods),encoding="utf-8")
    print("V83_ALL_INDICATOR_RESEARCH_COMPLETED",output["verifiedArchivedMonthsTotal"],
          json.dumps(comparison["combined"]),flush=True)

if __name__=="__main__":
    main()
