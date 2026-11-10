#!/usr/bin/env python3
"""SOL V8.5 causal LONG/SHORT, regime-aware, abstaining paper research.

PREDECLARED MODEL (before 2021–2022 unseen historical robustness run):
* Both completed DAILY and 4H SMA100/SMA200 agree on direction.
* Prior CLOSED 4H: RSI14, daily RSI14, previous completed day P/S/R pivots,
  38.2/61.8 retracements, volume relative to prior20 bars,
  broad box learned from last 28 completed Daily closes (8.5% band),
  chart-only Wyckoff SOS/SOW proxy and prior 1H high/low liquidity sweep.
* Future (subsequent) 1H candle must CLOSE with direction-specific BOS or
  reversal sweep. Enter hypothetical at NEXT 1H OPEN. If no confirmation
  in next 4 hours => ABSTAIN. If ambiguous direction => ABSTAIN.
* 0.50 USD MAX PLANNED risk, 10x $100 paper; next 24h stop-first/2R,
  conservative exchange gap behavior, 9bp per side fee+slippage.
* Single chronology 24h cooldown across selected candidates, no overlaid
  hindsight optimization. Compare pre-declared baseline, score>=6/10,
  score>=8/10, and >=6 with latest liquidity sweep. A filter produces
  no signal if insufficient evidence; 75% user benchmark never tuned.

Data 2023–2026 has already been inspected. 2021–22 is older-unseen
market regime test, NOT a time-forward holdout; runs with exactly same
predeclared rules. OHLCV cannot prove Wyckoff market-maker actions
or actual stop-liquidity/confirmed institutional OB.
No live orders, no production changes or notifications.
"""
import argparse
from bisect import bisect_right
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json
import math
from pathlib import Path
from statistics import median

from download_binance_um_history import download_month,months_inclusive,month_start,month_end,aggregate
from market_structure import average_true_range
from sol_v82_fib_pivot_confluence import wilson_lower
from backtest_retest_long_v4 import rsi14

HOUR=3600
FOUR=14400
DAY=86400
COOLDOWN_HOURS=24
CONFIRM_FUTURE_1H=4
MAX_PAPER_HOURS=24
RISK_CAP=0.50
NOTIONAL_MAX=1000.
COST_SIDE=0.0009
TARGET_GOAL_PCT=75.
EXPLORATORY_SCORE_THRESHOLD=6
EXPLORATORY_STRICT_THRESHOLD=8


def iso(ts):
    return datetime.fromtimestamp(ts,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def verified_history(start,end):
    months=months_inclusive(start,end)
    first=month_start(start)
    finish=month_end(end)
    bundle={}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(download_month,"SOLUSDT",m):m for m in months}
        for f in as_completed(futures):
            symbol,month,candles,proof=f.result()
            if symbol!="SOLUSDT" or month!=futures[f]:
                raise ValueError("WRONG_SOURCE")
            if not proof.get("sha256"):
                raise ValueError("ARCHIVE_SHA256_MISSING")
            expected=(month_end(month)-month_start(month))//HOUR
            if len(candles)!=expected:raise ValueError("MISSING_"+month)
            bundle[month]=candles
            print("SOL_ARCHIVE_CHECKSUM_OK",month,len(candles),flush=True)
    one=[x for m in months for x in bundle[m]]
    if len(one)!=(finish-first)//HOUR or any(
        x["t"]!=first+i*HOUR for i,x in enumerate(one)):
        raise ValueError("INCOMPLETE_CONTIGUOUS_1H_SOURCE")
    four=aggregate(one,FOUR)
    daily=aggregate(one,DAY)
    return one,four,daily,len(months)


def rolling_sma(values,length):
    arr=[]
    total=0.
    for i,p in enumerate(values):
        total+=p
        if i>=length:total-=values[i-length]
        arr.append(total/length if i>=length-1 else None)
    return arr


def rolling_rsi14(values):
    result=[None]*len(values)
    if len(values)<15:return result
    up=sum(max(0,values[i]-values[i-1]) for i in range(1,15))/14
    down=sum(max(0,values[i-1]-values[i]) for i in range(1,15))/14
    def val(u,d):
        if u==0 and d==0:return 50.
        return 100. if d==0 else 100-100/(1+u/d)
    result[14]=val(up,down)
    for i in range(15,len(values)):
        change=values[i]-values[i-1]
        up=(13*up+max(0,change))/14
        down=(13*down+max(0,-change))/14
        result[i]=val(up,down)
    return result


def trigger(one,i,side):
    if i<14:return None
    b=one[i]
    previous=one[i-12:i]
    local=one[i-4:i]
    high=max(x["h"] for x in previous)
    low=min(x["l"] for x in previous)
    bos=(b["c"]>max(x["h"] for x in local) and b["c"]>b["o"]
         if side=="LONG" else
         b["c"]<min(x["l"] for x in local) and b["c"]<b["o"])
    sweep=(b["l"]<low and b["c"]>low and b["c"]>b["o"]
           if side=="LONG" else
           b["h"]>high and b["c"]<high and b["c"]<b["o"])
    if not (bos or sweep):return None
    return {"index":i,"closedUTC":iso(b["t"]+HOUR),
            "kind":"BOS" if bos else "SWEEP",
            "pre12High":round(high,6),"pre12Low":round(low,6),
            "closePrice":round(b["c"],7)}


def first_1h_confirm_index(one,start_i,side):
    if one[start_i]["t"]%FOUR:raise ValueError("1H_BLOCK_NOT_ALIGNED")
    for j in range(start_i,min(len(one)-1,start_i+CONFIRM_FUTURE_1H)):
        sig=trigger(one,j,side)
        if sig is not None:return sig
    return None


def broad_box(daily,day_i):
    """Wide region chosen ONLY from previous 28 completed daily closes."""
    if day_i<28:return None
    bars=daily[day_i-28:day_i]
    winners=[]
    for d in bars:
        floor=d["c"]*.985
        roof=floor*1.085
        n=sum(floor<=x["c"]<=roof for x in bars)
        if n>=6:winners.append((n,floor,roof))
    if not winners:return None
    n,floor,roof=max(winners,key=lambda x:(x[0],-x[1]))
    return {"low":floor,"high":roof,"density":n,
            "anchor":"28 previous completed Daily closes, 8.5% width"}


def recent_liquidity_sweep(one,prior_4h_last_hour_i,side):
    # Last 24 fully closed 1H bars up to the current completed 4H candle.
    if prior_4h_last_hour_i<36:return False
    for j in range(prior_4h_last_hour_i-23,prior_4h_last_hour_i+1):
        b=one[j]
        old=one[j-12:j]
        if side=="LONG":
            low=min(x["l"] for x in old)
            if b["l"]<low and b["c"]>low and b["c"]>b["o"]:
                return True
        else:
            high=max(x["h"] for x in old)
            if b["h"]>high and b["c"]<high and b["c"]<b["o"]:
                return True
    return False


def features_at_4h_close(one,four,daily,idx,sma_f100,sma_f200,rsi_f,
                          sma_d100,sma_d200,rsi_d):
    fourbar=four[idx]
    end=fourbar["t"]+FOUR
    # completed daily candle list ends; previous day's pivot is based on
    # prior UTC date, not a partially complete current daily bar.
    daily_ends=[x["t"]+DAY for x in daily]
    day_i=bisect_right(daily_ends,end)-1
    if day_i<200 or idx<200:return None
    if any(x is None for x in (sma_f100[idx],sma_f200[idx],rsi_f[idx],
                               sma_d100[day_i],sma_d200[day_i],rsi_d[day_i])):
        return None
    price=fourbar["c"]
    daily_price=daily[day_i]["c"]
    f100,f200=sma_f100[idx],sma_f200[idx]
    d100,d200=sma_d100[day_i],sma_d200[day_i]
    if d100>d200 and f100>f200:
        side="LONG"
    elif d100<d200 and f100<f200:
        side="SHORT"
    else:
        return {"status":"ABSTAIN_MIXED_SMA_REGIME","asOfUTC":iso(end)}
    vola=average_true_range(four,idx-1,14)
    if not vola or vola<=0:return None
    prevvol=sum(b["v"] for b in four[idx-20:idx])/20
    rv=fourbar["v"]/prevvol if prevvol else None
    # Important: for at 4H retest open, same-day Daily close is only
    # available at UTC midnight; the pivot level should depend on the
    # previous completed UTC calendar day, not today's in-progress OHLCV.
    today_start=fourbar["t"]//DAY*DAY
    prior=[d for d in daily if d["t"]+DAY<=today_start]
    if not prior:return None
    dprev=prior[-1]
    pivotP=(dprev["h"]+dprev["l"]+dprev["c"])/3
    piv={"P":pivotP,"S1":2*pivotP-dprev["h"],
         "S2":pivotP-(dprev["h"]-dprev["l"]),
         "R1":2*pivotP-dprev["l"],
         "R2":pivotP+(dprev["h"]-dprev["l"])}
    # 0.382-0.618 zone comes only from 18 preceding completed 4H bars.
    preceding=four[idx-18:idx]
    swing_high=max(z["h"] for z in preceding)
    swing_low=min(z["l"] for z in preceding)
    fiblow=swing_low+.382*(swing_high-swing_low)
    fibhigh=swing_low+.618*(swing_high-swing_low)
    fib_hit=fiblow-.30*vola<=price<=fibhigh+.30*vola
    # Daily box exists independently of its future retest outcome.
    zone=broad_box(daily,day_i+1)
    if zone:
        if side=="LONG":
            box_hit=abs(fourbar["l"]-zone["low"])<=vola or (
                zone["low"]<=price<=zone["high"])
        else:
            box_hit=abs(fourbar["h"]-zone["high"])<=vola or (
                zone["low"]<=price<=zone["high"])
    else:box_hit=False
    previous6=four[idx-6:idx]
    if side=="LONG":
        pivot_hit=any(abs(fourbar["l"]-piv[name])<=.65*vola
                      for name in ("P","S1","S2"))
        rsi4=48<=rsi_f[idx]<=68
        rsiDaily=rsi_d[day_i]>=50
        close_loc=(price-fourbar["l"])/max(1e-9,fourbar["h"]-fourbar["l"])
        wyckoff=(fourbar["c"]>fourbar["o"] and close_loc>=.6 and rv is not None and rv>=1.2)
        chart_break=price>max(x["h"] for x in previous6)
        fvg=(fourbar["l"]>four[idx-2]["h"]+.12*vola)
        sma_ok=price>f200 and f100>f200
        daily_ok=daily_price>d200 and d100>d200
    else:
        pivot_hit=any(abs(fourbar["h"]-piv[name])<=.65*vola
                      for name in ("P","R1","R2"))
        rsi4=32<=rsi_f[idx]<=52
        rsiDaily=rsi_d[day_i]<=50
        close_loc=(price-fourbar["l"])/max(1e-9,fourbar["h"]-fourbar["l"])
        wyckoff=(fourbar["c"]<fourbar["o"] and close_loc<=.4 and rv is not None and rv>=1.2)
        chart_break=price<min(x["l"] for x in previous6)
        fvg=(fourbar["h"]<four[idx-2]["l"]-.12*vola)
        sma_ok=price<f200 and f100<f200
        daily_ok=daily_price<d200 and d100<d200
    h_last=(end//HOUR)-1-(one[0]["t"]//HOUR)
    if h_last<24 or one[h_last]["t"]+HOUR!=end:
        raise ValueError("1H_4H_CLOSED_TIME_MISMATCH")
    sweep=recent_liquidity_sweep(one,h_last,side)
    points={
       "4H_SMA100_200":sma_ok,
       "Daily_SMA100_200":daily_ok,
       "4H_RSI14":rsi4,
       "Daily_RSI14":rsiDaily,
       "Prior_Daily_Pivot":pivot_hit,
       "Fibonacci382_618":fib_hit,
       "WyckoffSOS_SOW_Proxy":wyckoff,
       "Past1H_Liquidity_Sweep":sweep,
       "Broad28Day_DemandSupply_Box":box_hit,
       "4H_Volume1_2x":rv is not None and rv>=1.2}
    return {
        "status":"CANDIDATE",
        "side":side,"asOfUTC":iso(end),
        "fourEndTs":end,
        "votes":points,"score10":sum(points.values()),
        "rsi4H":round(rsi_f[idx],4),
        "rsiDaily":round(rsi_d[day_i],4),
        "4HSMA100":round(f100,6),
        "4HSMA200":round(f200,6),
        "dailySMA100":round(d100,6),
        "dailySMA200":round(d200,6),
        "previousDayPivot":{name:round(value,6) for name,value in piv.items()},
        "previousDayPivotClosedUTC":iso(dprev["t"]+DAY),
        "fibRange":[round(fiblow,6),round(fibhigh,6)],
        "broadZone":{k:round(v,5) if isinstance(v,(int,float)) else v
                     for k,v in zone.items()} if zone else None,
        "WyckoffProxyNotProven":True,
        "liquiditySweepNotActualOrderbook":True,
        "4H_OB_BOSProxy":chart_break,
        "4H_FVGProxy":fvg,
        "atr14":vola}


def simulate_trade(one,signal,side,vola):
    j=signal["index"]
    if j+MAX_PAPER_HOURS>=len(one):return None
    price=one[j+1]["o"]
    buffer=max(.03*vola,.0005*price)
    if side=="LONG":
        stop=min(one[j]["l"],one[j-1]["l"])-buffer
    else:
        stop=max(one[j]["h"],one[j-1]["h"])+buffer
    d=(price-stop) if side=="LONG" else (stop-price)
    if price<=0 or not .001<=d/price<=.04:
        return {"status":"SKIP_STOP_INVALID"}
    goal=price+(2*d if side=="LONG" else -2*d)
    exit_price=one[j+MAX_PAPER_HOURS]["c"]
    exitidx=j+MAX_PAPER_HOURS
    reason="24H_CLOSE"
    for k in range(j+1,j+MAX_PAPER_HOURS+1):
        bar=one[k]
        stopgap=bar["o"]<=stop if side=="LONG" else bar["o"]>=stop
        stopped=bar["l"]<=stop if side=="LONG" else bar["h"]>=stop
        profit=bar["h"]>=goal if side=="LONG" else bar["l"]<=goal
        if stopgap:
            exit_price=bar["o"];exitidx=k;reason="STOP_GAP";break
        if stopped:
            exit_price=stop;exitidx=k;reason="STOP_FIRST";break
        if profit:
            exit_price=goal;exitidx=k;reason="TAKE_PROFIT_2R";break
    cost=COST_SIDE*(price+exit_price)
    qty=min(RISK_CAP/(d+COST_SIDE*(price+stop)),NOTIONAL_MAX/price)
    signed=(exit_price-price if side=="LONG" else price-exit_price)
    pnl=qty*(signed-cost)
    if reason=="STOP_FIRST" and pnl<-RISK_CAP-1e-5:
        raise ValueError("PLANNED_RISK_LIMIT_EXCEEDED")
    return {"status":"COMPLETE_PAPER_NOT_FILLED","side":side,
            "entryAtUTC":iso(one[j+1]["t"]),
            "exitKnownUTC":iso(one[exitidx]["t"]+HOUR),
            "entryIndex":j+1,"exitIndex":exitidx,
            "entry":round(price,6),"stop":round(stop,6),"target":round(goal,6),
            "stopDistancePct":round(100*d/price,4),
            "exitReason":reason,"paperNetUSDT":round(pnl,6),
            "marginUSDT":round(qty*price/10,6),
            "plannedRiskUSDT":RISK_CAP,"feeAndSlippageBpsOneWay":9,
            "gapThroughStopCanLoseMoreThanPlannedRisk":reason=="STOP_GAP"}


def scan(one,four,daily,limit=None):
    f_prices=[x["c"] for x in four]
    d_prices=[x["c"] for x in daily]
    f100,f200=rolling_sma(f_prices,100),rolling_sma(f_prices,200)
    d100,d200=rolling_sma(d_prices,100),rolling_sma(d_prices,200)
    frsi,drsi=rolling_rsi14(f_prices),rolling_rsi14(d_prices)
    seen=0
    mixed=0
    no_confirm=0
    last_signal_end=-1
    emitted=[]
    loop_to=len(four)-7 if limit is None else min(len(four)-7,limit)
    start_h=one[0]["t"]
    for i in range(210,loop_to):
        found=features_at_4h_close(one,four,daily,i,f100,f200,frsi,d100,d200,drsi)
        if found is None:continue
        if found["status"]=="ABSTAIN_MIXED_SMA_REGIME":
            mixed+=1;continue
        seen+=1
        end=found["fourEndTs"]
        if end<last_signal_end+COOLDOWN_HOURS*HOUR:
            continue
        hour_idx=(end-start_h)//HOUR
        if hour_idx<0 or hour_idx>=len(one) or one[hour_idx]["t"]!=end:
            raise ValueError("CANDIDATE_1H_FOLLOWUP_MISSING")
        sig=first_1h_confirm_index(one,hour_idx,found["side"])
        if sig is None:
            no_confirm+=1;continue
        when=one[sig["index"]]["t"]+HOUR
        if when>four[i]["t"]+FOUR+CONFIRM_FUTURE_1H*HOUR:
            raise ValueError("1H_FUTURE_CONFIRM_OUTSIDE_WINDOW")
        # 24 h cooldown between incoming setups, deterministic and shared
        # among ALL predeclared filter variants (no hindsight filtering).
        last_signal_end=when
        forward_j=sig["index"]+MAX_PAPER_HOURS
        if forward_j>=len(one):
            raise ValueError("NO_FUTURE_PRICE_REQUIRED_FOR_HISTORICAL_CASE")
        at_close=one[sig["index"]]["c"]
        future=one[forward_j]["c"]
        perf=100*(future/at_close-1)
        success=perf>0 if found["side"]=="LONG" else perf<0
        trade=simulate_trade(one,sig,found["side"],found["atr14"])
        emitted.append({**found,
            "oneHourConfirmation":sig,
            "confirmationKnownUTC":sig["closedUTC"],
            "directional24HPriceChangePct":round(perf,5),
            "directional24HHit":success,
            "paper":trade})
    return emitted,{
        "4HRegimeCandidates":seen,"abstainMixedDaily4HRegime":mixed,
        "abstainNo1HConfirmation":no_confirm,
        "24hCooldownAndStopDataComplete":True,
        "signalsAfterCooldown":len(emitted)}


def variants():
    return {
       "A_RegimePlus1H":lambda e:True,
       "B_AtLeast6of10":lambda e:e["score10"]>=EXPLORATORY_SCORE_THRESHOLD,
       "C_AtLeast8of10":lambda e:e["score10"]>=EXPLORATORY_STRICT_THRESHOLD,
       "D_Score6WithPastSweep":lambda e:e["score10"]>=6
          and e["votes"]["Past1H_Liquidity_Sweep"],
       "E_SMA_RSI_And6":lambda e:e["score10"]>=6
          and e["votes"]["4H_RSI14"] and e["votes"]["Daily_RSI14"],
       "F_WideBox_Fib_Pivot":lambda e:e["votes"]["Broad28Day_DemandSupply_Box"]
          and e["votes"]["Fibonacci382_618"] and e["votes"]["Prior_Daily_Pivot"],
    }


def score(rows,side=None):
    data=[z for z in rows if side is None or z["side"]==side]
    hits=sum(z["directional24HHit"] for z in data)
    n=len(data)
    trades=[z["paper"] for z in data if z["paper"] is not None
            and z["paper"]["status"]=="COMPLETE_PAPER_NOT_FILLED"]
    # Trades can overlap when strategy filters skip other signals. Summing
    # event PnL is not an actual account, so no portfolio profit claim.
    wr=sum(z["paperNetUSDT"]>0 for z in trades)
    return {
       "directionEvents":n,
       "correct24HourDirection":hits,
       "directionHitRatePct":round(100*hits/n,2) if n else None,
       "wilson95LowerPct":round(100*wilson_lower(hits,n),2) if n else None,
       "observedTarget75":(hits/n>=.75) if n else False,
       "atLeast30Events":n>=30,
       "stopFitPaperTrades":len(trades),
       "paperWinPct":round(100*wr/len(trades),2) if trades else None,
       "eventPnLSumUSDTNotPortfolio":round(sum(z["paperNetUSDT"] for z in trades),5),
       "maxPlannedRiskUSD":.50,
       "noForwardValidation":True}


def result_report(buckets,details):
    result={}
    definitions=variants()
    for bucket,events in buckets.items():
        result[bucket]={name:{
           "combined":score([e for e in events if predicate(e)]),
           "LONG":score([e for e in events if predicate(e)],"LONG"),
           "SHORT":score([e for e in events if predicate(e)],"SHORT")}
                       for name,predicate in definitions.items()}
    return result


def markdown(data):
    lines=[
      "# SOL V8.5 — Trend-regime LONG+SHORT with abstention, wide zones and 1H confirmation",
      "",
      "**Experimental historical research only**; not a trading system approval.",
      "**2021–22** older-unseen-regime robustness; not time-forward; "
      "**2023–Sep2026** previously inspected development periods.",
      "",
      "## Sources and validation",
      f"- **{data['verifiedMonths']}** officially checksum-verified Binance USD-M SOLUSDT monthly 1H archives.",
      "- Daily + 4H SMA100 and SMA200 for regime; 4H RSI14, Daily RSI14; prior-day classic pivot.",
      "- Broad Daily 28-day 8.5% width support/supply zone, Fib 38.2–61.8, Wyckoff SOS/SOW OHLCV proxy, 1H liquidity sweep, 4H volume.",
      "- Either direction considered; mixed SMA regimes yield ABSTAIN. Next four closed 1H candles must provide BOS or sweep; next 1H open paper entry.",
      "- Direction judged 24h after 1H confirmation. 24h global event cooldown fixed before looking at outcomes.",
      "- Stop wick 1H+0.03 ATR, risk <= $0.50 planned; 10x notional; TP2R or 24h, worst-case stop first, 9bps/side fees/slippage.",
      "- 4H chart structure BOS/FVG candidate proxies stored but not given votes; no institutionally verified orderbook or actual Wyckoff phase.",
      "",
      "| Test | 2021–22 | 2023–24 | 2025–Sep26 | All |",
      "|---|---:|---:|---:|---:|"]
    for name in variants():
        def fmt(b):
            x=data["comparisons"][b][name]["combined"]
            return f"{x['correct24HourDirection']}/{x['directionEvents']} ({x['directionHitRatePct']}%)" if x["directionEvents"] else "No cases"
        lines.append(f"| {name} | {fmt('olderUnseen2021_2022')} | "
                     f"{fmt('known2023_2024')} | {fmt('known2025_2026')} | {fmt('allCombined')} |")
    lines+=["","## Cautions",
      "- Historical observations are not live-forward; 2021–22 was selected as additional unseen market regime, but backward in calendar time.",
      "- Technical proxies use OHLCV; true Wyckoff manipulation, stops and actual order-book liquidity cannot be validated.",
      "- 75% goal never used to change filter thresholds after results.",
      "- Six different predefined variants; selecting best in retrospect would bias accuracy.",
      "- No funding, gaps in exchange API live execution, latency or liquidation model beyond OHLCV and rough fee/slippage.",
      "- Score result is directional 24h hit, not probability that 10x futures trade would win.",
      "- No production BTC/ETH/SOL branch modifications and no real orders.",
      ""]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--json",default="forward/v85_two_sided/latest.json")
    p.add_argument("--markdown",default="forward/v85_two_sided/latest.md")
    opts=p.parse_args()
    specimens={}
    manifests={}
    for name,start,end in (("olderUnseen2021_2022","2021-01","2022-12"),
                           ("known2023_2024","2023-01","2024-12"),
                           ("known2025_2026","2025-01","2026-09")):
        print("V85_PERIOD_START",name,flush=True)
        one,four,daily,count=verified_history(start,end)
        out,stats=scan(one,four,daily)
        specimens[name]=out
        manifests[name]={"from":start,"to":end,
                         "verifiedMonths":count,
                         "1H":len(one),"4H":len(four),"Daily":len(daily),
                         **stats}
        print("V85_PERIOD_DONE",name,stats,flush=True)
    specimens["allCombined"]=sum((specimens[x] for x in
        ("olderUnseen2021_2022","known2023_2024","known2025_2026")),[])
    comps=result_report(specimens,manifests)
    report={
       "mode":"SOL_V85_TWO_SIDED_SMA_RSI_WYCKOFF_FIB_PIVOT_SWEEP_WIDEZONE_HOURLY",
       "status":"RESEARCH_ONLY_NEVER_AUTO_TRADE",
       "createdAtUTC":datetime.now(timezone.utc).isoformat(),
       "verifiedMonths":sum(x["verifiedMonths"] for x in manifests.values()),
       "source":"Official Binance USD-M SOLUSDT monthly 1H archives + CHECKSUM verification",
       "periods":manifests,"comparisons":comps,
       "configBeforeUnseenPeriod":{
          "SMA4H":[100,200],"SMADaily":[100,200],
          "RSI14":True,"NoMACD":True,"Fibonacci":[.382,.618],
          "classicPreviousDailyPivot":True,"wideZonePct":8.5,
          "wyckoffSOS_SOW_OHLCVProxy":True,"1HUpDownLiquiditySweep":True,
          "orderBlockActualInstitutionalProof":False,
          "1HConfirmationWindow":CONFIRM_FUTURE_1H,
          "score6":EXPLORATORY_SCORE_THRESHOLD,
          "score8":EXPLORATORY_STRICT_THRESHOLD,
          "eventCooldownHours":COOLDOWN_HOURS,
          "noTradeOnMixedRegime":True,
          "gapSlippageCanExceedPlannedRisk":True},
       "userBenchmarkPct":TARGET_GOAL_PCT,
       "unseenDataIsChronologicallyEarlierNotProspective":True,
       "historicalBacktestIsNotValidatedEdge":True,
       "brokerOrders":False,"productionModified":False,
       "liveSignalEnabled":False,
       "researchSignals":{x:specimens[x][-120:] for x in manifests},
    }
    output=Path(opts.json);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    md=Path(opts.markdown);md.parent.mkdir(parents=True,exist_ok=True)
    md.write_text(markdown(report))
    print("V85_RESEARCH_DONE",report["verifiedMonths"],
          json.dumps({t:{name:item["combined"] for name,item in d.items()}
                      for t,d in comps.items()}),flush=True)

if __name__=="__main__":
    main()
