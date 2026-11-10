#!/usr/bin/env python3
"""V8.4 SOL historical playbook: broad Daily/4H zone + classic trader inputs.

A separate RESEARCH pipeline; no broker endpoints or secrets:
  * Daily+4H wide demand -> broken support -> resistance flip candidate,
    fixed before 4H break (V8.1).
  * Previous COMPLETED daily classic pivot and prebreak Fibonacci (V8.2).
  * RSI14; SIMPLE moving averages SMA100 and SMA200, NOT EMA.
  * Wyckoff-style SOW/LPSY OHLCV PROXIES (not proven real distribution);
    prior 24h 1H liquidity sweep and OHLCV candidate bearish Order Block.
  * After 4H rejection, next 1-8 CLOSED 1H candles can confirm a lower-low
    or a false breakout / bearish sweep. Paper SHORT only NEXT 1H OPEN.
  * Three frozen variants: 1H price-only, >=4 of 8 confluence points,
    SMA/RSI plus >=4 of 8. Compare all on the SAME setup universe.
  * 24h direction, independent paper outcomes and non-overlapping $100
    equity replay, fee+slippage 9bps each side, initial stop-first, 2R
    profit target, 24h time exit, capped planned risk 0.50 USD and 10x.

Historical periods 2023-24 and 2025-Sep2026 are previously inspected and
are NOT independent holdouts. 75% is an aspiration, not a fitted threshold.
No MACD; no futures orders, no production changes. Only SOL/SHORT experiment.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bisect import bisect_right
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import median
from collections import Counter

from download_binance_um_history import download_month, months_inclusive, month_start, month_end, aggregate
from sol_v82_fib_pivot_confluence import evaluate as v82_evaluate, wilson_lower
from sol_v83_full_confluence_paper import features_for_event
from market_structure import average_true_range
from backtest_retest_long_v4 import rsi14

FOUR=14400
HOUR=3600
DAY=86400
RISK_CAP_USDT=0.5
START_EQUITY_USDT=100.0
LEVERAGE=10
COST_ONE_SIDE=0.0009
DIRECTION_HORIZON_H=24
EXIT_HORIZON_H=24
SIGNAL_WINDOW_H=8
CONFIRM_SCORE_MIN=4   # frozen BEFORE comparing outcomes
MAX_STOP_DISTANCE_PCT=0.04
MIN_STOP_DISTANCE_PCT=0.001
MIN_RESEARCH_CASES=30
TARGET_HIT_PCT=75
SPLIT_AT="2026-07-01T00:00:00Z"

def iso(ts):
    return datetime.fromtimestamp(ts,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def timestamp(value):
    return int(datetime.fromisoformat(value.replace("Z","+00:00")).timestamp())

def verified_history(start,end):
    months=months_inclusive(start,end)
    first,last=month_start(start),month_end(end)
    monthly={}
    with ThreadPoolExecutor(max_workers=6) as pool:
        work={pool.submit(download_month,"SOLUSDT",m):m for m in months}
        for future in as_completed(work):
            symbol,month,rows,proof=future.result()
            if symbol!="SOLUSDT" or month!=work[future]:
                raise ValueError("WRONG_VERIFIED_ARCHIVE")
            if len(rows)!= (month_end(month)-month_start(month))//HOUR:
                raise ValueError("INCOMPLETE_BINANCE_ARCHIVE_"+month)
            if not proof.get("sha256"):
                raise ValueError("MISSING_SHA256_PROOF")
            monthly[month]=rows
            print("SOL_OFFICIAL_SHA256",month,len(rows),flush=True)
    one=[c for month in months for c in monthly[month]]
    if len(one)!=(last-first)//HOUR or any(x["t"]!=first+i*HOUR for i,x in enumerate(one)):
        raise ValueError("MISSING_OR_DUPLICATE_1H_SOURCE")
    four=aggregate(one,FOUR)
    daily=aggregate(one,DAY)
    return one,four,daily,len(months)

def sma(bars,index,n):
    if index+1<n:return None
    return sum(bars[j]["c"] for j in range(index-n+1,index+1))/n

def known_sma_rsi(one,four,daily,retest_i):
    close=four[retest_i]["t"]+FOUR
    days=[b for b in daily if b["t"]+DAY<=close]
    iD=len(days)-1
    if retest_i<200 or iD<99:
        return None
    four_c=[b["c"] for b in four[:retest_i+1]]
    daily_c=[b["c"] for b in days]
    fs100,fs200=sma(four,retest_i,100),sma(four,retest_i,200)
    ds100=sma(daily,iD,100)
    ds200=sma(daily,iD,200) if iD>=199 else None
    f4=four[retest_i]["c"]
    d=days[-1]["c"]
    f_rsi=rsi14(four_c)
    d_rsi=rsi14(daily_c)
    return {"frozenAtUTC":iso(close),
            "dailyLastClosedUTC":iso(days[-1]["t"]+DAY),
            "fourSMA100":round(fs100,6),"fourSMA200":round(fs200,6),
            "dailySMA100":round(ds100,6),
            "dailySMA200":round(ds200,6) if ds200 is not None else None,
            "dailySMA200Available":ds200 is not None,
            "rsi4H":round(f_rsi,4),"rsiDaily":round(d_rsi,4),
            "smaBearish4H":f4<fs100 and f4<fs200,
            "smaBearishDaily100":d<ds100,
            "smaBearishDaily200":d<ds200 if ds200 is not None else None,
            "smaBearishHigherFrames":f4<fs100 and f4<fs200 and d<ds100,
            "rsiBearishNotOversold":30<=f_rsi<50 and d_rsi<50,
            "MACDUsed":False}

def sweep_last24h_before_4h_close(one,cutoff):
    t=[x["t"] for x in one]
    n=bisect_right(t,cutoff-HOUR)
    if n<36:return {"liquiditySweep":False,"sweepClosedUTC":None,
                     "reason":"insufficient_history"}
    start=max(12,n-24)
    matches=[]
    for j in range(start,n):
        bar=one[j]
        if bar["t"]+HOUR>cutoff:raise ValueError("FUTURE_1H_IN_SWEEP")
        high=max(z["h"] for z in one[j-12:j])
        if bar["h"]>high and bar["c"]<high and bar["c"]<bar["o"]:
            matches.append(iso(bar["t"]+HOUR))
    return {"liquiditySweep":bool(matches),
            "sweepClosedUTC":matches[-1] if matches else None,
            "lookback":"12 previous closed 1H highs, prior 24h window",
            "notOrderbookLiquidityProof":True}

def trigger_candle(one,index,allow_sweep=True):
    """At current CLOSED one-hour candle, never use future close."""
    if index<24:return None
    b=one[index]
    prior=one[index-12:index]
    p4=one[index-4:index]
    low4=min(z["l"] for z in p4)
    high12=max(z["h"] for z in prior)
    sweep=b["h"]>high12 and b["c"]<high12 and b["c"]<b["o"]
    break_low=b["c"]<low4 and b["c"]<b["o"]
    if not (break_low or (allow_sweep and sweep)):
        return None
    return {"closeUTC":iso(b["t"]+HOUR),
            "kind":"LIQUIDITY_SWEEP_UPPER_REJECTION" if sweep else "LOWER_LOW_1H_BREAK",
            "barIndex":index,"levelPrior12High":round(high12,6),
            "levelPrior4Low":round(low4,6),
            "close":round(b["c"],7),
            "confirmedOnClosedCandle":True}

def next_1h_confirmation(one,event_ts):
    """Wait only the NEXT 8 closed 1H bars, enter on subsequent bar OPEN."""
    times=[c["t"] for c in one]
    first=bisect_right(times,event_ts-1)
    if first>=len(one) or one[first]["t"]!=event_ts:
        raise ValueError("MISSING_FIRST_1H_AFTER_4H_CLOSE")
    end=min(len(one)-1,first+SIGNAL_WINDOW_H)
    for i in range(first,end):
        sig=trigger_candle(one,i)
        if sig:
            if one[i+1]["t"]!=one[i]["t"]+HOUR:
                raise ValueError("MISSING_NEXT_OPEN_AFTER_HOURLY_SIGNAL")
            return sig
    return None

def make_1h_paper(one,signal,atr4,box_low):
    """1H entry AFTER signal close; stop near 1H signal wick, not box roof.

    We don't force a wide 7.5USD stop into a 100USDT account. The box defines
    context; 1H candle gives local invalidation. Gap-through-stop slippage
    may exceed planned 0.50 USD risk. No fills are claimed.
    """
    if signal is None:return {"status":"NO_TRIGGER"}
    j=signal["barIndex"]
    if j+EXIT_HORIZON_H>=len(one):
        return {"status":"INSUFFICIENT_FUTURE_EXIT_BARS"}
    entry=one[j+1]["o"]
    stop=max(one[j]["h"],one[j-1]["h"])+max(.03*atr4,.0005*entry)
    risk=stop-entry
    if entry<=0 or risk<=0 or not MIN_STOP_DISTANCE_PCT<=risk/entry<=MAX_STOP_DISTANCE_PCT:
        return {"status":"SKIP_INVALID_1H_STOP_OR_GAP"}
    target=entry-2*risk
    exit_price=one[j+EXIT_HORIZON_H]["c"]
    exit_idx=j+EXIT_HORIZON_H
    exit_reason="TIME_24H"
    for k in range(j+1,j+EXIT_HORIZON_H+1):
        bar=one[k]
        if bar["o"]>=stop:
            exit_price=bar["o"];exit_idx=k;exit_reason="STOP_GAP_THROUGH";break
        if bar["h"]>=stop:
            exit_price=stop;exit_idx=k;exit_reason="STOP_FIRST";break
        if bar["l"]<=target:
            exit_price=target;exit_idx=k;exit_reason="TARGET_2R";break
    fee=entry*COST_ONE_SIDE+exit_price*COST_ONE_SIDE
    planned_cost_at_stop=COST_ONE_SIDE*(entry+stop)
    quantity=min(RISK_CAP_USDT/(risk+planned_cost_at_stop),
                 LEVERAGE*START_EQUITY_USDT/entry)
    net_per_unit=entry-exit_price-fee
    pnl=quantity*net_per_unit
    if exit_reason=="STOP_FIRST" and pnl<-(RISK_CAP_USDT+1e-5):
        raise ValueError("STOP_LOSS_EXCEEDS_PLANNED_RISK")
    return {
       "status":"HYPOTHETICAL_1H_PAPER_NOT_AN_ORDER",
       "triggerUTC":signal["closeUTC"],
       "entryKnownUTC":iso(one[j+1]["t"]),
       "exitKnownUTC":iso(one[exit_idx]["t"]+HOUR),
       "entryIndex":j+1,"exitIndex":exit_idx,
       "entry":round(entry,7),"stop":round(stop,7),
       "target2R":round(target,7),
       "feeAndSlippageBpsPerSide":9,
       "exitReason":exit_reason,
       "plannedRiskUSD":RISK_CAP_USDT,
       "quantityBasedOn100USD":round(quantity,9),
       "marginBasedOn100USD":round(quantity*entry/LEVERAGE,6),
       "pnlBasedOn100USD":round(pnl,6),
       "grossRiskPerUnit":risk,
       "netPerUnit":net_per_unit,
       "stopGapCanExceedRisk":exit_reason=="STOP_GAP_THROUGH",
       "boxLowerContextOnly":box_low}

def event_features(one,four,daily,event,idx4):
    """State at 4H rejection close only; 1H trigger is separate later."""
    t=timestamp(event["retestClosedUTC"])
    local=known_sma_rsi(one,four,daily,idx4)
    if local is None:return None
    swept=sweep_last24h_before_4h_close(one,t)
    initial=features_for_event(one,four,daily,event)
    votes={
       "SMA100_200_HTF":bool(local["smaBearishHigherFrames"]),
       "RSI14_HTF":bool(local["rsiBearishNotOversold"]),
       "WyckoffSOW_LPSYProxy":bool(initial["WyckoffProxy"]["wyckoffCombined"]),
       "LiquiditySweepPrior24h":bool(swept["liquiditySweep"]),
       "Fibonacci382_618":bool(event["fibHit"]),
       "DailyPivotLine":bool(event["pivotHit"]),
       "BearishOrderBlock":bool(initial["features"]["OrderBlock_4H"]),
       "OneHourRejectionAt4HClose":bool(initial["features"]["LastClosed1HRejection"]),
    }
    s=sum(votes.values())
    future=next_1h_confirmation(one,t)
    paper=make_1h_paper(one,future,initial["indicators"]["4hEMA20"]*0+
                        (average_true_range(four,idx4-1,14) or 0),event["boxLow"])
    # Labels after 1H confirmation: relevant only if 24 complete later hours
    # exist; avoid using original 4H retest outcome as an entered paper trade.
    after24=None
    if future and future["barIndex"]+DIRECTION_HORIZON_H<len(one):
        after24=round(100*(one[future["barIndex"]+DIRECTION_HORIZON_H]["c"]/
                           one[future["barIndex"]]["c"]-1),5)
    return {"retestClosedUTC":event["retestClosedUTC"],
            "wideZone":[event["boxLow"],event["boxHigh"]],
            "featureVotes":votes,"score8":s,
            "MACDUsed":False,"sma":local,"liquiditySweep":swept,
            "wyckoff":initial["WyckoffProxy"],
            "fib":{"hit":event["fibHit"],"low":event["fib382"],"high":event["fib618"]},
            "pivot":{"hit":event["pivotHit"],"previousClosed":event["pivotPreviousDayClosedUTC"],
                     "levels":event["pivotLevels"]},
            "orderBlock":initial["OBFVG"],
            "lastHourAt4HClose":initial["last1H"],
            "oneHourTrigger":future,
            "next24hPctAfter1HConfirmation":after24,
            "paper":paper,
            "oneHourTriggerNotAvailableAt4HDecision":bool(future),
            "futureDirectionNeverUsedForFilter":True}

def definitions():
    return {
     "00_1H_Confirmed_PriceOnly":lambda e:True,
     "01_SMA100200_RSI":lambda e:e["featureVotes"]["SMA100_200_HTF"] and e["featureVotes"]["RSI14_HTF"],
     "02_Wyckoff_SMA":lambda e:e["featureVotes"]["WyckoffSOW_LPSYProxy"] and e["featureVotes"]["SMA100_200_HTF"],
     "03_LiquiditySweep":lambda e:e["featureVotes"]["LiquiditySweepPrior24h"],
     "04_Fibonacci_Pivot":lambda e:e["featureVotes"]["Fibonacci382_618"] and e["featureVotes"]["DailyPivotLine"],
     "05_Score4of8":lambda e:e["score8"]>=CONFIRM_SCORE_MIN,
     "06_Score5of8":lambda e:e["score8"]>=5,
     "07_SMA_RSI_Score4":lambda e:e["featureVotes"]["SMA100_200_HTF"] and e["featureVotes"]["RSI14_HTF"] and e["score8"]>=CONFIRM_SCORE_MIN,
     "08_SMA_RSI_Wyckoff_Sweep":lambda e:e["featureVotes"]["SMA100_200_HTF"] and e["featureVotes"]["RSI14_HTF"] and e["featureVotes"]["WyckoffSOW_LPSYProxy"] and e["featureVotes"]["LiquiditySweepPrior24h"],
     "09_AllEightHardGates":lambda e:all(e["featureVotes"].values()),
    }

def portfolio_sim(rows):
    """Non-overlapping $100 account replay; quantity recalculated at current equity."""
    valid=sorted(
      (r for r in rows if r["paper"]["status"]=="HYPOTHETICAL_1H_PAPER_NOT_AN_ORDER"),
      key=lambda r:r["paper"]["entryKnownUTC"])
    equity=START_EQUITY_USDT
    peak=equity
    drawdown=0
    ignored=0
    accepted=[]
    previous_exit=""
    for r in valid:
        p=r["paper"]
        if p["entryKnownUTC"]<previous_exit:
            ignored+=1;continue
        if equity<=0:break
        entry,stop=p["entry"],p["stop"]
        planned_cost=COST_ONE_SIDE*(entry+stop)
        risk=min(RISK_CAP_USDT,.005*equity)
        qty=min(risk/(stop-entry+planned_cost),LEVERAGE*equity/entry)
        pnl=qty*p["netPerUnit"]
        equity+=pnl
        peak=max(peak,equity)
        drawdown=max(drawdown,peak-equity)
        if p["exitReason"]=="STOP_FIRST" and pnl<-(risk+0.00001):
            raise ValueError("PORTFOLIO_STOP_EXCEEDS_PLANNED_RISK")
        accepted.append({"entryKnownUTC":p["entryKnownUTC"],
                         "exitKnownUTC":p["exitKnownUTC"],
                         "exitReason":p["exitReason"],
                         "pnLUSD":round(pnl,6),
                         "equityAfterUSD":round(equity,6),
                         "plannedRiskUSD":round(risk,6),
                         "marginUSD":round(qty*entry/LEVERAGE,6)})
        previous_exit=p["exitKnownUTC"]
    return {"startingEquityUSD":100.0,"endingEquityUSD":round(equity,5),
            "netPnLUSD":round(equity-100,5),
            "maxDrawdownUSD":round(drawdown,5),
            "completedNonOverlappingTrades":len(accepted),
            "winningTrades":sum(x["pnLUSD"]>0 for x in accepted),
            "winRatePct":round(100*sum(x["pnLUSD"]>0 for x in accepted)/len(accepted),2) if accepted else None,
            "overlappingEntriesExcluded":ignored,
            "trades":accepted}

def summarize(rows):
    answered=[r for r in rows if r["next24hPctAfter1HConfirmation"] is not None]
    count=len(answered)
    hit=sum(r["next24hPctAfter1HConfirmation"]<0 for r in answered)
    pct=round(100*hit/count,2) if count else None
    missed=[r for r in rows if r["oneHourTrigger"] is None]
    risk_skips=[r for r in rows if r["paper"]["status"]=="SKIP_INVALID_1H_STOP_OR_GAP"]
    stats={
      "setupEvents":len(rows),
      "no1HConfirmation":len(missed),
      "invalidLocalStops":len(risk_skips),
      "completed24hDirectionLabels":count,
      "correctDown24hAfter1HSignal":hit,
      "directionAccuracyPct":pct,
      "wilson95LowerPct":round(100*wilson_lower(hit,count),2) if count else None,
      "target75Observed":pct is not None and pct>=TARGET_HIT_PCT,
      "atLeast30IndependentSetupEvents":count>=MIN_RESEARCH_CASES,
      "meets75WithMin30":bool(pct is not None and pct>=TARGET_HIT_PCT and count>=MIN_RESEARCH_CASES),
      "medianChange24hPct":round(median(r["next24hPctAfter1HConfirmation"] for r in answered),5) if answered else None,
      "portfolio":portfolio_sim(rows),
    }
    return stats

def study_range(start,end):
    one,four,daily,verified=verified_history(start,end)
    events,_stats,counts=v82_evaluate(four,daily)
    ts4={bar["t"]+FOUR:i for i,bar in enumerate(four)}
    results=[]
    excluded=0
    for e in events:
        i=ts4[timestamp(e["retestClosedUTC"])]
        enriched=event_features(one,four,daily,e,i)
        if enriched is None:
            excluded+=1
        else:
            results.append(enriched)
    return results,{"verifiedMonths":verified,
                    "1hourCandles":len(one),"4hourCandles":len(four),
                    "dailyCandles":len(daily),
                    "wideZoneRetestEvents":len(events),
                    "excludedForSMA100DailyWarmup":excluded,
                    "included":len(results)}

def md_report(x):
    lines=[
      "# SOL V8.4 — Pivot Line, RSI, SMA100/200, Wyckoff, liquidity sweep, Fibonacci, Daily+4H wide zones",
      "",
      "**Only research.** Short-direction study on SOL perpetual; no real orders, no BTC/ETH production edits.",
      "",
      "## Mechanical rules",
      "- Daily + 4H broad 8.5% OHLCV support boxes frozen BEFORE breakdown, then bearish 4H retest.",
      "- Next eight 1H CLOSED candles: either close below prior four 1H lows or bearish upper liquidity sweep above prior 12 1H highs. Entry is only NEXT 1H OPEN.",
      "- RSI14 Daily+4H <50, with 4H >=30 to flag oversold shorts; SMA 100/200 on 4H plus SMA100 Daily, optional Daily SMA200 where warmed.",
      "- Wyckoff SOW and LPSY are volume-price heuristic proxies, NOT verified institutional distribution/spring/UTAD.",
      "- Fibonacci 38.2–61.8 and classical P/R1/R2/S1/S2 previous fully completed Daily pivot.",
      "- Bearish OB/FVG chart-derived candidate only; look for 1H preceding 24h upper-high liquidity sweep; MACD excluded.",
      "- Each vote fixed before historical execution; score>=4 or >=5 variants shown; ALL eight hard mandatory is a diagnostic only.",
      "- Paper SHORT stop: 1H confirmation high or preceding high + 0.03 of 4H ATR buffer. TP2R / 24h close, pessimistic stop-first, 9 bps one-way. Planned risk <=0.5 USD per trade and 10x notional cap.",
      "- Independent per-strategy account starts at 100 USD. Any overlap is excluded (not double-counted). Stop-gap losses may exceed the planned risk.",
      "",
      "## Comparison — 24-hour direction accuracy AFTER 1H confirmation",
      "| Version | 2023–24 | 2025–Sep2026 | Combined | Non-overlap paper trades | Account net USD |",
      "|---|---:|---:|---:|---:|---:|"]
    for name in x["comparison"]["combined"]:
        def cell(segment):
            z=x["comparison"][segment][name]
            return f"{z['correctDown24hAfter1HSignal']}/{z['completed24hDirectionLabels']} ({z['directionAccuracyPct']}%)" if z["completed24hDirectionLabels"] else "No cases"
        com=x["comparison"]["combined"][name]
        acc=com["portfolio"]
        lines.append(f"| {name} | {cell('older2023_2024')} | {cell('recent2025_2026')} | "
                     f"{cell('combined')} | {acc['completedNonOverlappingTrades']} | {acc['netPnLUSD']:+.4f} |")
    lines.extend(["","## Important limitations",
                  "- All historical periods were already examined; no honest out-of-sample validation yet.",
                  "- Multiple versions measured; selecting whichever is 75% with low n is not evidence of an edge.",
                  "- OHLCV can indicate possible Wyckoff or liquidity sweep, but not confirmed market-maker intent.",
                  "- Fixed fee+slippage and no liquidation/funding/partial fill model. No claim of net profit.",
                  "- Previous candle analysis restricts feature creation; labels after entries are NEVER used for gating.",
                  "- This pipeline is standalone SOL SHORT only, not BTC/ETH or LONG live deployment.",
                  ""])
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--json",default="forward/v84_classic_playbook/latest.json")
    p.add_argument("--markdown",default="forward/v84_classic_playbook/latest.md")
    a=p.parse_args()
    historical={}
    source={}
    for key,start,end in (("older2023_2024","2023-01","2024-12"),
                          ("recent2025_2026","2025-01","2026-09")):
        print("V84_ARCHIVE_START",key,flush=True)
        items,meta=study_range(start,end)
        historical[key]=items
        source[key]=meta
        print("V84_ARCHIVE_DONE",key,meta,flush=True)
    both=historical["older2023_2024"]+historical["recent2025_2026"]
    slices={**historical,"combined":both,
            "julSep2026":[r for r in historical["recent2025_2026"]
              if r["retestClosedUTC"]>=SPLIT_AT]}
    filters=definitions()
    comparison={
        name:{variant:summarize([r for r in rows if gate(r)])
              for variant,gate in filters.items()}
        for name,rows in slices.items()
    }
    report={
      "mode":"SOL_V84_CLASSIC_SMA100_200_WYCKOFF_SWEEP_FIB_PIVOT_WIDE_ZONE_1H_PAPER",
      "status":"RESEARCH_EXPERIMENT_ONLY_NO_LIVE_TRADE",
      "createdUTC":datetime.now(timezone.utc).isoformat(),
      "source":"Binance USD-M SOLUSDT official 1H ZIP and checksum, 4H and Daily from contiguous 1H",
      "sourceAudit":source,
      "verifiedMonthlyArchives":sum(v["verifiedMonths"] for v in source.values()),
      "onlyShortSideTested":True,
      "frozenBeforeSeeingOutcomes":{
          "SMA4H":[100,200],"SMADaily":[100,200],"RSI14":True,
          "wyckoffSOWLPSYProxy":True,"liquiditySweepPrior12HHigh":True,
          "liquiditySweepMaxSearchAfterRetest1H":SIGNAL_WINDOW_H,
          "classicPriorDayPivot":True,"Fibonacci382_618":True,
          "wideSupplyDemandBoxV81":True,"bearishOBandFVGContext":True,
          "MACDUsed":False,"scoreThreshold":CONFIRM_SCORE_MIN},
      "comparison":comparison,
      "featureRows":historical,
      "previouslyInspectedHistoricalData":True,
      "noNewValidatedOutOfSample":True,
      "targetDirectionalHitPct":75,
      "brokerOrders":False,"productionModified":False,
      "liveSignalEnabled":False,
      "actualInstitutionalOrderEvidence":False,
    }
    out=Path(a.json);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=Path(a.markdown);md.parent.mkdir(parents=True,exist_ok=True)
    md.write_text(md_report(report),encoding="utf-8")
    print("V84_SOL_CLASSIC_PAPER_SUCCESS",report["verifiedMonthlyArchives"],
          json.dumps({name:{k:{"n":v["completed24hDirectionLabels"],
                                "pct":v["directionAccuracyPct"],
                                "paperUSD":v["portfolio"]["netPnLUSD"]}
                     for k,v in table.items()}
                      for name,table in comparison.items()}),flush=True)

if __name__=="__main__":
    main()
