#!/usr/bin/env python3
"""V9.2 BTC/ETH/SOL historical divergence ablation; NO ORDERS, NO ALERTS.

CVD is a 1H Binance USD-M kline-derived approximation:
signed base delta = 2 * taker-buy-base-volume - total-base-volume.
It is NOT tick-by-tick trade-level CVD; monthly ZIP and SHA256 are verified.
Confirmed price swing pivot requires TWO subsequently CLOSED 1H candles.
All factors are calculated at the CLOSED retest candle; no future observations.

This study is historical research, already selected/inspected market period.
Does not update V7, V9.1, V9.2 or prospective paper accounts.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import json
import math
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from download_binance_um_history import (
    aggregate, download_month, month_end, month_start, months_inclusive
)
from signal_quality_v7 import evaluate_bos_quality
from v92_bull_bear_candle_invalidation import metrics, START, END, HOUR, stamp
from v92_selected_reversal_patterns import make_selective_gate

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
MODES = (
    "V91_NO_CANDLE_VETO",
    "V92_SELECTED_BASELINE",
    "CVD_DIVERGENCE_BOS_RETEST",
    "CVD_DIVERGENCE_LIQUIDITY_SWEEP",
    "CVD_DIVERGENCE_VOLUME_SPIKE",
    "RSI_DIVERGENCE_BOS_RETEST",
    "MACD_DIVERGENCE_BOS_RETEST",
    "RSI_AND_MACD_DIVERGENCE_RETEST",
)
LEFT = 2
RIGHT = 2
MAX_LAST_PIVOT_AGE = 24
MAX_PREVIOUS_PIVOT_AGE = 96
MIN_PIVOT_GAP = 3
VOLUME_SPIKE_RATIO = 1.5
SWEEP_LOOKBACK = 20

def indicators(rows):
    """Wilder RSI14, MACD12/26/9 histogram and base-volume cumulative delta."""
    out={"rsi":[],"macd_hist":[],"cvd":[]}
    prev=None
    up=down=0.
    fast=slow=signal=None
    cumulative=0.
    seeded_gain=[]
    seeded_loss=[]
    for i,b in enumerate(rows):
        for k in ("v","tbv","o","h","l","c","t"):
            if k not in b:
                raise ValueError("DIVERGENCE_BINANCE_TAKER_OR_PRICE_FIELD_MISSING_"+k)
        if not (0<=b["tbv"]<=b["v"]+max(1e-7,1e-8*b["v"])
                and math.isfinite(float(b["tbv"])) and math.isfinite(float(b["v"]))):
            raise ValueError("DIVERGENCE_TAKER_VOLUME_INVALID")
        if i and b["t"]!=rows[i-1]["t"]+HOUR:
            raise ValueError("DIVERGENCE_GAPPED_HOURLY_HISTORY")
        close=float(b["c"])
        fast=close if fast is None else fast+(2/13)*(close-fast)
        slow=close if slow is None else slow+(2/27)*(close-slow)
        line=fast-slow
        signal=line if signal is None else signal+(2/10)*(line-signal)
        out["macd_hist"].append(line-signal)
        if prev is None:
            out["rsi"].append(None)
        elif i<=14:
            seeded_gain.append(max(0.,close-prev))
            seeded_loss.append(max(0.,prev-close))
            if i==14:
                up=sum(seeded_gain)/14
                down=sum(seeded_loss)/14
                out["rsi"].append(100. if down==0 and up>0 else
                    50. if up==0 and down==0 else 100.-100./(1+up/down))
            else:out["rsi"].append(None)
        else:
            up=(13*up+max(0.,close-prev))/14
            down=(13*down+max(0.,prev-close))/14
            out["rsi"].append(100. if down==0 and up>0 else
                50. if up==0 and down==0 else 100.-100./(1+up/down))
        cumulative+=2*float(b["tbv"])-float(b["v"])
        out["cvd"].append(cumulative)
        prev=close
    return out

def pivot_index(rows, i, side):
    """Pivot at i is first *known* two full candles after i (not earlier)."""
    if i<LEFT or i+RIGHT>=len(rows):
        return False
    field="l" if side=="bullish" else "h"
    val=rows[i][field]
    prev=[rows[j][field] for j in range(i-LEFT,i)]
    nxt=[rows[j][field] for j in range(i+1,i+RIGHT+1)]
    return (all(val<x for x in prev) and all(val<=x for x in nxt)
            if side=="bullish" else
            all(val>x for x in prev) and all(val>=x for x in nxt))

def divergence_at(rows, oscillator, i, side):
    """Require two price pivots confirmed no later than the 1H close at i."""
    if i>=len(rows) or i<MAX_PREVIOUS_PIVOT_AGE:
        return False
    earliest=max(LEFT,i-MAX_PREVIOUS_PIVOT_AGE)
    pivots=[j for j in range(earliest,i-RIGHT+1)
            if pivot_index(rows,j,side) and oscillator[j] is not None]
    if len(pivots)<2:return False
    latest=pivots[-1]
    if i-latest>MAX_LAST_PIVOT_AGE:return False
    earlier=next((j for j in reversed(pivots[:-1])
                  if latest-j>=MIN_PIVOT_GAP),None)
    if earlier is None:return False
    if side=="bullish":
        return (rows[latest]["l"]<rows[earlier]["l"]
                and oscillator[latest]>oscillator[earlier])
    return (rows[latest]["h"]>rows[earlier]["h"]
            and oscillator[latest]<oscillator[earlier])

def sweep_at(rows,i,side):
    if i<SWEEP_LOOKBACK:return False
    current=rows[i]
    history=rows[i-SWEEP_LOOKBACK:i]
    if side=="bullish":
        lower=min(z["l"] for z in history)
        return current["l"]<lower and current["c"]>lower
    upper=max(z["h"] for z in history)
    return current["h"]>upper and current["c"]<upper

def volume_spike_at(rows,i):
    if i<SWEEP_LOOKBACK:return False
    avg=sum(b["v"] for b in rows[i-SWEEP_LOOKBACK:i])/SWEEP_LOOKBACK
    return avg>0 and rows[i]["v"]>=VOLUME_SPIKE_RATIO*avg

def features_at(rows,ind,close_to_index,close_utc,side):
    """As-of-only: future rows might be supplied, but never inspected."""
    i=close_to_index.get(close_utc)
    if i is None or i<MAX_PREVIOUS_PIVOT_AGE:
        raise ValueError("DIVERGENCE_MISSING_CONFIRMED_CLOSE")
    # rows used for volume/sweep and pivots end strictly at or before i
    return {
       "cvd":divergence_at(rows,ind["cvd"],i,side),
       "rsi":divergence_at(rows,ind["rsi"],i,side),
       "macd":divergence_at(rows,ind["macd_hist"],i,side),
       "sweep":sweep_at(rows,i,side),
       "volumeSpike":volume_spike_at(rows,i),
    }

def matched_gate(symbol,four,rows,ind,mode,audit):
    closes={b["t"]+HOUR:i for i,b in enumerate(rows)}
    selected_audit=Counter()
    selected_audit["examples"]=[]
    original=make_selective_gate(
        symbol,four,"SELECTED_SOL_STRICT_SWEEP",selected_audit)
    cache={}
    def gate(one,active,retest):
        decision=original(one,active,retest)
        audit["evaluatedRetests"]+=1
        if not decision["passed"]:
            audit["v92CandleVetos"]+=1
            return decision
        if mode=="V92_SELECTED_BASELINE":
            return {"passed":True,"reasons":[]}
        at=int(retest["t"])+HOUR
        side=active["side"]
        if at not in cache:cache[at]={}
        if side not in cache[at]:
            cache[at][side]=features_at(rows,ind,closes,at,side)
        f=cache[at][side]
        for key,value in f.items():
            if value:audit["observed_"+key]+=1
        required={
          "CVD_DIVERGENCE_BOS_RETEST":f["cvd"],
          "CVD_DIVERGENCE_LIQUIDITY_SWEEP":f["cvd"] and f["sweep"],
          "CVD_DIVERGENCE_VOLUME_SPIKE":f["cvd"] and f["volumeSpike"],
          "RSI_DIVERGENCE_BOS_RETEST":f["rsi"],
          "MACD_DIVERGENCE_BOS_RETEST":f["macd"],
          "RSI_AND_MACD_DIVERGENCE_RETEST":f["rsi"] and f["macd"],
        }
        passed=required[mode]
        if passed:audit["passedDivergence"]+=1
        else:audit["rejectedDivergence"]+=1
        return {"passed":passed,
                "reasons":[] if passed else ["DIVERGENCE_"+mode+"_NOT_CONFIRMED"]}
    return gate

def validate_month_rows(rows, first,last):
    start,end=month_start(first),month_end(last)
    if len(rows)!=(end-start)//HOUR:
        raise ValueError("DIVERGENCE_ARCHIVE_CANDLE_COUNT_MISMATCH")
    for i,b in enumerate(rows):
        if b["t"]!=start+i*HOUR or any(k not in b for k in ("qv","tbv","tbq","trades")):
            raise ValueError("DIVERGENCE_ARCHIVE_GAP_OR_FLOW_FIELDS_MISSING")
    return start,end

def run_symbol(symbol, rows, first,last):
    start,end=validate_month_rows(rows,first,last)
    if start!=START or end!=END:
        raise ValueError("DIVERGENCE_MISMATCHED_V92_REFERENCE_PERIOD")
    data={tf:aggregate(rows,secs) for tf,secs in
          (("1hour",HOUR),("4hour",4*HOUR),("daily",24*HOUR))}
    ind=indicators(rows)
    results={}
    for mode in MODES:
        audit=Counter()
        filt=(None if mode=="V91_NO_CANDLE_VETO" else
              matched_gate(symbol,data["4hour"],rows,ind,mode,audit))
        replay=replay_pair(data["1hour"],data["4hour"],data["daily"],
                           as_of=END,retest_hours=4,
                           bos_quality_filter=evaluate_bos_quality,
                           retest_quality_filter=filt)
        m=metrics(replay,START,END)
        m["divergenceGateAudit"]=dict(audit)
        results[mode]=m
        print("DIVERGENCE_REPLAY",symbol,mode,"trades",m["trades"],
              "NetR",m["totalNetR9BpsPerSide"],
              "stressR",m["totalNetR25BpsPerSideStress"],flush=True)
    return results

def run(first="2024-10",last="2026-09",workers=6):
    months=months_inclusive(first,last)
    if len(months)!=24 or not 1<=workers<=6:
        raise ValueError("DIVERGENCE_TWO_YEAR_FROZEN_PERIOD_ONLY")
    manifest=[]
    by_symbol={s:{} for s in SYMBOLS}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs={pool.submit(download_month,s,m):(s,m)
              for s in SYMBOLS for m in months}
        for future in as_completed(futs):
            symbol,month,rows,proof=future.result()
            if (symbol,month)!=futs[future]:
                raise ValueError("DIVERGENCE_MONTH_SOURCE_MISMATCH")
            by_symbol[symbol][month]=rows
            manifest.append({"symbol":symbol,"month":month,**proof})
            print("DIVERGENCE_BINANCE_SHA256",symbol,month,len(rows),flush=True)
    manifest=sorted(manifest,key=lambda x:(x["symbol"],x["month"]))
    if len(manifest)!=72 or any(len(x["sha256"])!=64 for x in manifest):
        raise ValueError("DIVERGENCE_MONTHLY_SHA256_COVERAGE_INCOMPLETE")
    output={
      "status":"V92_CVD_RSI_MACD_DIVERGENCE_HISTORICAL_RESEARCH_ONLY",
      "periodStartUTC":stamp(START),"periodEndExclusiveUTC":stamp(END),
      "source":"72 Binance official USD-M monthly 1H ZIPs with SHA256 verified",
      "sourceManifest":{"checksumsVerified":72,"inputFiles":manifest},
      "cvdSource":"1H taker buy base from Binance klines",
      "cvdFormula":"cumulative sum(2*takerBuyBase - totalBaseVolume)",
      "cvdIsHourlyProxyNotTickLevel":True,
      "noOrderbookOrRealFills":True,
      "confirmedPivotRightBars":RIGHT,
      "pivotLastMaxAgeHours":MAX_LAST_PIVOT_AGE,
      "volumeSpikeVsPrevious20BarMean":VOLUME_SPIKE_RATIO,
      "liquiditySweepPriorBars":SWEEP_LOOKBACK,
      "allDecisionsAtCLOSEDRetestOnly":True,
      "noLookaheadOrRetrospectiveTradeFills":True,
      "originalV7V91V92Unchanged":True,
      "noBrokerOrders":True,"noUserNotifications":True,
      "historicalPreviouslyInspectedNotForwardEvidence":True,
      "models":list(MODES),"assets":{},
    }
    for s in SYMBOLS:
        one=[r for m in months for r in by_symbol[s][m]]
        output["assets"][s]={
           "verifiedCandles":{"1H":len(one),"4H":len(one)//4,"1D":len(one)//24},
           "results":run_symbol(s,one,first,last),
        }
    return output

def markdown(result):
    lines=[
        "# V9.2 CVD / RSI / MACD divergence — historical 1H study",
        "","**RESEARCH ONLY — no live orders or V7/V9.2 strategy changes.**","",
        "Data: official Binance USD-M 1H kline archives, 72 SHA256 verified ZIPs,",
        "BTC/ETH/SOL, 2024-10-01 through 2026-09-30. CVD is only an **hourly",
        "taker-volume-derived approximation** (not tick-trade CVD).","",
        "Pivot confirmation needs 2 future-to-pivot but already CLOSED 1H bars;",
        "at a retest decision only information already closed by that hour is read.","",
        "## Results (9 bps / 25 bps per side assumed cost)","",
        "| Asset | Scenario | Closed trades | Win % | Net R | Stress net R | PF | Max DD R | Retest rejections |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s,asset in result["assets"].items():
        for mode,m in asset["results"].items():
            lines.append(
                f"| {s} | {mode} | {m['trades']} | {m['winRatePct']} | "
                f"{m['totalNetR9BpsPerSide']:+.3f} | "
                f"{m['totalNetR25BpsPerSideStress']:+.3f} | "
                f"{m['profitFactor']} | {m['maxDrawdownR']:.3f} | "
                f"{m['retestVetoes']} |"
            )
    lines.extend([
        "","## Limitations","",
        "- Models require baseline BOS/retest AND any stated divergence; not stand-alone entry signals.",
        "- V9.2 SOL selected Star/Harami sweep veto remains in all V9.2/divergence arms.",
        "- Data were previously inspected in earlier V9.2 work; filters are research candidates, not independently validated signals.",
        "- Future *relative to pivot* bars are needed to confirm it, but these bars close before the retest decision.",
        "- Simulator uses assumed next 1H open and stop/TP fills, not executable exchange quotes.",
        "- No funding, market depth, real fill prices or liquidation risk modeled.",
        "- Trades here cannot count toward the separate 10/20 USDT forward paper threshold.",
        "",
    ])
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",default="forward/v92_divergence_historical")
    p.add_argument("--workers",type=int,default=6)
    a=p.parse_args()
    result=run(workers=a.workers)
    out=Path(a.output_dir)
    out.mkdir(parents=True,exist_ok=True)
    (out/"historical.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"historical.md").write_text(markdown(result)+"\n",encoding="utf-8")
    print("V92_DIVERGENCE_THREE_ASSET_HISTORICAL_COMPLETE",flush=True)
if __name__=="__main__":
    main()
