#!/usr/bin/env python3
"""BTC/ETH/SOL V8 1H/4H/1D three-asset confluence paper backtest.

Official Binance USD-M monthly SHA256-verified 1H Futures archives;
4H and 1D built from exact 1H UTC groups. No network trading, no orders.
This research is in-sample plus a locked chronological test period;
it is NOT independently validated predictive performance or live execution.

V4 and V7 are replayed as fixed baselines. V8 is a chronological V7+
EMA200, OB/FVG, Fibonacci, liquidity, candlestick confluence hypothesis.
Funding/OI/taker are unavailable in same-time uniform historical feed and
MUST NOT be inferred retrospectively from newer snapshots.
"""
import argparse
from bisect import bisect_right
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import mean

from download_binance_um_history import (
    aggregate, download_month, months_inclusive, month_start, month_end,
)
from backtest_retest_long_v4 import replay_pair, indicators, ema
from market_structure import analyze, average_true_range
from signal_quality_v7 import evaluate_bos_quality, evaluate_retest_quality

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
PAIRS=tuple(s+"_PERP.A" for s in SYMBOLS)
SECONDS={"1hour":3600,"4hour":14400,"daily":86400}
SPLIT="2026-07-01T00:00:00Z"
START="2025-01"
END="2026-09"
COST_BPS_PER_SIDE=9
RISK_HARD_CAP_USDT=0.50
ISOLATED_LEVERAGE=10
START_EQUITY_USDT=100.0


def unix(x):
    return int(datetime.fromisoformat(x.replace("Z","+00:00")).timestamp())


def iso(t):
    return datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validated_archives(start,end,workers):
    months=months_inclusive(start,end)
    if not 1<=len(months)<=24:
        raise ValueError("ARCHIVE_MONTHS_RANGE_NOT_1_TO_24")
    if month_end(end)>int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("CANNOT_BACKTEST_INCOMPLETE_MONTH")
    tasks=[(symbol,month) for symbol in SYMBOLS for month in months]
    monthly={}
    manifest=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future={pool.submit(download_month,s,m):(s,m) for s,m in tasks}
        for job in as_completed(future):
            symbol,month=future[job]
            s,m,rows,proof=job.result()
            if (s,m)!=(symbol,month):
                raise ValueError("DOWNLOADED_WRONG_SYMBOL_MONTH")
            monthly[(s,m)]=rows
            manifest.append({"symbol":s,"month":m,**proof})
            print("ARCHIVE_SHA256_VERIFIED",s,m,len(rows),flush=True)
    hist={}
    expected=(month_end(end)-month_start(start))//3600
    first=month_start(start)
    for symbol in SYMBOLS:
        hourly=[bar for m in months for bar in monthly[(symbol,m)]]
        if len(hourly)!=expected or any(
            row["t"]!=first+3600*i for i,row in enumerate(hourly)
        ):
            raise ValueError("MISSING_OR_DUPLICATE_1H_HISTORY_"+symbol)
        hist[symbol]={tf:aggregate(hourly,seconds)
                      for tf,seconds in SECONDS.items()}
    return hist,sorted(manifest,key=lambda r:(r["symbol"],r["month"]))


def signal(side):
    return 1 if side=="bullish" else -1


def matches_candle_pattern(prev,bar,side,atr):
    s=signal(side)
    body=abs(bar["c"]-bar["o"])
    if body<1e-10 or not s*(bar["c"]-bar["o"])>0:
        return False
    prev_body_low=min(prev["o"],prev["c"])
    prev_body_high=max(prev["o"],prev["c"])
    engulf=(s*(prev["c"]-prev["o"])<0
             and min(bar["o"],bar["c"])<=prev_body_low
             and max(bar["o"],bar["c"])>=prev_body_high)
    low_wick=min(bar["o"],bar["c"])-bar["l"]
    high_wick=bar["h"]-max(bar["o"],bar["c"])
    rejection=(low_wick if s>0 else high_wick)
    opposite_wick=(high_wick if s>0 else low_wick)
    pin=rejection>=max(1.5*body,0.25*atr) and rejection>2*opposite_wick
    return engulf or pin


def fib_levels(prior,side):
    if len(prior)<30:
        return None
    lookback=prior[-48:]
    high=max(b["h"] for b in lookback)
    low=min(b["l"] for b in lookback)
    span=high-low
    if span<=0:return None
    if side=="bullish":
        return (high-0.618*span,high-0.382*span)
    return (low+0.382*span,low+0.618*span)


def zone_overlap(lo1,hi1,lo2,hi2,tolerance=0):
    return lo1<=hi2+tolerance and hi1>=lo2-tolerance


def retest_features(bars,active,bar):
    # ALL inputs are <= the CLOSED retest candle. Restrict "prior" to avoid
    # the candle whose condition is being evaluated in Fibonacci/pattern.
    if len(bars)<55:
        raise ValueError("RETEST_HISTORY_INSUFFICIENT")
    ts=bar["t"]+3600
    side=active["side"]
    prior=bars[:-1]
    prev=prior[-1]
    atr=average_true_range(bars,len(bars)-1,14)
    if not atr or atr<=0:
        raise ValueError("BAD_RETEST_ATR")
    levels=fib_levels(prior,side)
    fib=bool(levels and zone_overlap(bar["l"],bar["h"],levels[0],levels[1],0.15*atr))
    pattern=matches_candle_pattern(prev,bar,side,atr)
    # Reusing the repository's closed-candle structure engine: chart-only
    # OB/FVG/near-equal-level heuristics, NOT real orderbook or fill records.
    structure=analyze(bars,"1hour",as_of=ts)
    obs=[z for z in structure["orderBlocks"]
         if z["side"]==side and z["confirmedAt"]<ts
         and z.get("state")!="invalidated"
         and zone_overlap(bar["l"],bar["h"],z["wick"]["low"],
                          z["wick"]["high"],0.15*atr)]
    ob=bool(obs)
    gaps=[z for z in structure["fvg"]
          if z["side"]==side and z["confirmedAt"]<ts
          and zone_overlap(bar["l"],bar["h"],z["low"],z["high"],0.15*atr)]
    fvg=bool(gaps)
    supports=[z for z in structure["liquidity"]
              if z["knownAt"]<ts
              and z["kind"]==("equal_lows" if side=="bullish" else "equal_highs")
              and abs(z["level"]-bar["c"])<=0.50*atr]
    liquidity=bool(supports)
    # A close back through a prior 1H extreme is a small-scale sweep.
    prev_extreme=(min(p["l"] for p in prior[-24:]) if side=="bullish"
                  else max(p["h"] for p in prior[-24:]))
    sweep=(bar["l"]<prev_extreme and bar["c"]>prev_extreme
           if side=="bullish" else
           bar["h"]>prev_extreme and bar["c"]<prev_extreme)
    return {"fib382to618":fib,"candlestickEngulfingOrPinbar":pattern,
            "orderBlockRetest":ob,"FVGTouch":fvg,
            "equalHighLowLiquidity":liquidity,"prior24HourSweep":sweep}


def higher_trend(h4,day,ts,side):
    checks=[]
    for bars,secs in ((h4,14400),(day,86400)):
        n=bisect_right([b["t"]+secs for b in bars],ts)
        if n<205:
            checks.append(False)
            continue
        hist=bars[:n]
        e200=ema([b["c"] for b in hist],200)
        checks.append(signal(side)*(hist[-1]["c"]-e200)>0)
    return checks


def make_gates(h4,day):
    # Cache higher-timeframe EMA200 results at each BOS confirmation time.
    closes4=[b["t"]+14400 for b in h4]
    closesD=[b["t"]+86400 for b in day]
    cache={}
    audits={"bosEvaluated":0,"bosRejectedReasons":Counter(),
            "retestEvaluated":0,"retestRejectedReasons":Counter(),
            "retestFeatureObserved":Counter()}
    def evaluate_bos(bars,bos,ind):
        audits["bosEvaluated"]+=1
        quality=evaluate_bos_quality(bars,bos,ind)
        reasons=list(quality["reasons"])
        side=bos["direction"]
        signed=signal(side)
        close=bars[-1]["c"]
        closes=[b["c"] for b in bars]
        e200=ema(closes,200)
        e20,e50=ind["EMA20"],ind["EMA50"]
        score=sum([signed*(close-e200)>0,
                   signed*(e20-e50)>0])
        ts=bos["at"]+3600
        n4=bisect_right(closes4,ts)
        nD=bisect_right(closesD,ts)
        if (n4,nD) not in cache:
            checks=[]
            for h,n in ((h4,n4),(day,nD)):
                if n<205:
                    checks.append(False)
                else:
                    h200=ema([bar["c"] for bar in h[:n]],200)
                    checks.append(signed*(h[n-1]["c"]-h200)>0)
            cache[(n4,nD)]=checks
        score+=sum(cache[(n4,nD)])
        if score<3:
            reasons.append("EMA20_50_200_MULTI_TF_SCORE_BELOW_3_OF_4")
        # RSI14 / MACD sign and V7 bos volume/retest are already V4+V7 gates.
        for why in reasons:audits["bosRejectedReasons"][why]+=1
        return {"passed":not reasons,"reasons":reasons,
                "features":{"emaTrendScore4Votes":score,"v7Quality":quality}}
    def evaluate_retest(bars,active,bar):
        audits["retestEvaluated"]+=1
        quality=evaluate_retest_quality(bars,active,bar)
        features=retest_features(bars,active,bar)
        for k,v in features.items():
            if v: audits["retestFeatureObserved"][k]+=1
        score=sum(features.values())
        reasons=list(quality["reasons"])
        if score<2:
            reasons.append("FIB_OB_FVG_LIQUIDITY_PATTERN_SCORE_BELOW_2_OF_6")
        for why in reasons:audits["retestRejectedReasons"][why]+=1
        return {"passed":not reasons,"reasons":reasons,
                "features":{"score":score,**features}}
    return evaluate_bos,evaluate_retest,audits


def metrics(trades,split,range_end,price_only=False):
    # The paper engine runs over full history. Only trades whose hypothetical
    # NEXT-open entry falls in the chosen interval are counted here.
    selected=[x for x in trades if split<=x["entryOpenUTC"]<range_end]
    vals=[x["netRIllustrative"] for x in selected]
    count=len(vals)
    gross_plus=sum(max(0,r) for r in vals)
    gross_minus=-sum(min(0,r) for r in vals)
    peak=cum=dd=0.0
    for r in vals:
        cum+=r
        peak=max(peak,cum)
        dd=max(dd,peak-cum)
    # Standalone $100 equity simulation PER ASSET (not an aggregated
    # portfolio); risk 0.5% of equity, capped at 0.50 USD, with 10x max.
    equity=START_EQUITY_USDT
    eqpeak=equity
    maxdd=0.0
    fills=[]
    for t in selected:
        price=t["entry"]
        stopdistance=abs(price-t["stop"])
        unit_cost=2*COST_BPS_PER_SIDE/10000*price
        risk_limit=min(RISK_HARD_CAP_USDT,0.005*equity)
        qty=min(risk_limit/(stopdistance+unit_cost),
                ISOLATED_LEVERAGE*equity/price) if equity>0 and stopdistance>0 else 0
        pnl=qty*stopdistance*t["netRIllustrative"]
        margin=qty*price/ISOLATED_LEVERAGE
        equity+=pnl
        eqpeak=max(eqpeak,equity)
        maxdd=max(maxdd,eqpeak-equity)
        fills.append({"entryOpenUTC":iso(t["entryOpenUTC"]),"side":t["side"],
                      "entry":round(price,7),"stop":round(t["stop"],7),
                      "exitKnownUTC":iso(t["exitKnownUTC"]),
                      "netR":round(t["netRIllustrative"],5),
                      "hypotheticalQty":round(qty,8),
                      "illustrativeInitialMarginUSDT":round(margin,4),
                      "netPnlUSDT":round(pnl,5),
                      "equityAfterUSDT":round(equity,5),
                      "exitReason":t["exitReason"]})
    return {
        "trades":count,"positive":sum(x>0 for x in vals),
        "winRatePct":round(100*sum(x>0 for x in vals)/count,2) if count else None,
        "avgNetR":round(mean(vals),5) if count else None,
        "sumNetR":round(sum(vals),5),
        "profitFactor":round(gross_plus/gross_minus,4) if gross_minus>0 else None,
        "maxSequentialDrawdownR":round(dd,5) if count else None,
        "hypotheticalStartUSDT":START_EQUITY_USDT,
        "hypotheticalEndUSDT":round(equity,5),
        "netPnLUSDT":round(equity-START_EQUITY_USDT,5),
        "maxEquityDrawdownUSDT":round(maxdd,5),
        "tradesDetail":fills,
    }


def run_asset(bars,split):
    h=bars["1hour"]
    four=bars["4hour"]
    daily=bars["daily"]
    as_of=h[-1]["t"]+3600
    gate_b,gate_r,diag=make_gates(four,daily)
    variants={
        "V4_baseline":{},
        "V7_quality_retest":{"bos_quality_filter":evaluate_bos_quality,
                             "retest_quality_filter":evaluate_retest_quality},
        "V8_all_OHLCV_confluence":{"bos_quality_filter":gate_b,
                                  "retest_quality_filter":gate_r},
    }
    output={}
    boundary=unix(split)
    begin=h[0]["t"]
    for label,opts in variants.items():
        print("REPLAY_START",label,iso(begin),iso(as_of),flush=True)
        back=replay_pair(h,four,daily,as_of=as_of,**opts)
        if back.get("status")!="PAPER_BACKTEST_NOT_LIVE":
            raise ValueError("BACKTEST_NOT_COMPUTED_"+label+":"+str(back.get("status")))
        output[label]={
            "alertsAll":back["alertsCount"],
            "completedTradesAll":back["hypotheticalClosedTrades"],
            "unresolvedExcluded":back["unresolvedPositionExcluded"],
            "pendingEntryExcluded":back["pendingEntryExcluded"],
            "preSplit":metrics(back["trades"],begin,boundary),
            "holdout":metrics(back["trades"],boundary,as_of),
            "qualityGateRejectedBOS":back["qualityGateRejectedBOS"],
            "qualityGateRejectedRetest":back["qualityGateRejectedRetest"],
        }
    diag["bosRejectedReasons"]=dict(diag["bosRejectedReasons"])
    diag["retestRejectedReasons"]=dict(diag["retestRejectedReasons"])
    diag["retestFeatureObserved"]=dict(diag["retestFeatureObserved"])
    return {"candles":{tf:len(bars[tf]) for tf in SECONDS},
            "variants":output,"V8GateDiagnostics":diag}


def render(report):
    lines=[
        "# BTC / ETH / SOL — V8 multi-timeframe paper-only historical test",
        "",
        "**Official source:** Binance USD-M Futures 1H monthly ZIP + SHA256 CHECKSUM.",
        "**Timeframes:** 1H archive; 4H and Daily aggregated from exact closed 1H.",
        "**Strategy:** V4 BOS → later retest → next 1H open; V7 ATR/RVOL quality; "
        "V8 EMA20/50/200, RSI14, MACD, OB, FVG, Fibonacci 0.382/0.618, "
        "equal-high/low liquidity, 24H sweep, pin/engulfing form.",
        "",
        f"**Data:** {report['period']['start']} through {report['period']['end']}; "
        f"**untuned holdout entry dates:** {report['period']['holdoutStartsUTC']} onward.",
        "",
        "| Coin | Variant | Holdout trades | Win rate | Avg net R | Profit factor | Simulated net PnL ($100 independent account) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for symbol,data in report["results"].items():
        for name,var in data["variants"].items():
            h=var["holdout"]
            lines.append(f"| {symbol} | {name} | {h['trades']} | "
                f"{h['winRatePct'] if h['winRatePct'] is not None else 'N/A'} | "
                f"{h['avgNetR'] if h['avgNetR'] is not None else 'N/A'} | "
                f"{h['profitFactor'] if h['profitFactor'] is not None else 'N/A'} | "
                f"{h['netPnLUSDT']:+.4f} |")
    lines.extend(["","## Important rules / limitations",
      "- ALL 4H/1D features refer only to already closed candles at the BOS hour.",
      "- 1H BOS requires a later closed retest; paper entry is NEXT open.",
      "- If stop and target share a candle, stop is hit first.",
      "- Cost assumption: 6 bps fee + 3 bps slippage per side, illustrative.",
      "- 100 USDT START per coin; <=0.50 USDT risk including modeled entry/exit costs per trade, 10x isolated notional cap.",
      "- USD report is a **standalone account per asset**, not a joint portfolio and not observed fills.",
      "- Funding, OI/taker, live spread, partial fills, liquidations, gap-through-stop and changing exchange rules are NOT included in PnL.",
      "- No model fitting on holdout in this run. Historical sample and tests do not establish forward profitability.",
      "- OHLCV OB/liquidity zones are heuristic; they are not verified institutional orders.",
      "- Strategy intentionally uses scored confluence; all filters are evaluated, NOT all must be simultaneously true.",
      "- No live broker orders or production changes; do NOT activate live trades from this report alone.",
    ])
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default=START)
    p.add_argument("--end",default=END)
    p.add_argument("--split",default=SPLIT)
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--output",required=True)
    p.add_argument("--report",required=True)
    args=p.parse_args()
    if args.workers<1 or args.workers>6:
        raise ValueError("WORKERS_1_TO_6")
    split=unix(args.split)
    if not month_start(args.start)<split<month_end(args.end):
        raise ValueError("SPLIT_OUTSIDE_ARCHIVED_PERIOD")
    histories,manifest=validated_archives(args.start,args.end,args.workers)
    output={"mode":"V8_BTC_ETH_SOL_HISTORICAL_PAPER_BACKTEST_NO_ORDERS",
            "status":"RESEARCH_ONLY_NOT_LIVE_SIGNAL",
            "createdUTC":datetime.now(timezone.utc).isoformat(),
            "period":{"start":args.start,"end":args.end,
                      "holdoutStartsUTC":args.split},
            "universe":list(PAIRS),
            "assumedCostsBpsPerSide":COST_BPS_PER_SIDE,
            "riskCapPerTradeUSDT":RISK_HARD_CAP_USDT,
            "startingEquityUSDTPerCoin":START_EQUITY_USDT,
            "leverageCapIsolated":ISOLATED_LEVERAGE,
            "archiveSHA256VerifiedCount":len(manifest),
            "sourceManifest":manifest,
            "derivativesStatus":"OI/funding/taker unavailable point-in-time throughout common history; EXCLUDED, not faked.",
            "results":{},"brokerOrders":False,
            "productionSystemModified":False,"liveSignalEnabled":False}
    for symbol in SYMBOLS:
        print("ASSET_BACKTEST",symbol,flush=True)
        output["results"][symbol]=run_asset(histories[symbol],args.split)
        print("ASSET_DONE",symbol,flush=True)
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    report=Path(args.report)
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(render(output),encoding="utf-8")
    print("V8_THREE_ASSET_PAPER_COMPLETE",len(manifest),
          {s:{v:x["holdout"]["trades"] for v,x in r["variants"].items()}
           for s,r in output["results"].items()},flush=True)


if __name__=="__main__":
    main()
