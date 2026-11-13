#!/usr/bin/env python3
"""V9.2 BTC/ETH/SOL historical 4H rolling-correlation and regime ablation.

Research-only: verifies 72 Binance official USD-M monthly SHA256 klines.
FROZEN questions: Do ETH losing retests occur when 3-asset correlation is
weak, when BTC 4H disagrees, or when ETH 4H ATR% is high vs BTC?
Baseline remains V9.1 max4h BOS/retest with original V7 BOS quality and
V9.2 SOL-only opposing Star/Harami liquidity-sweep veto.
All filters use ONLY already-CLOSED 4H bars at the 1H retest close.
No production changes, broker orders, user alerts or paper backfill.
"""
import argparse
from bisect import bisect_right
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from download_binance_um_history import (download_month, aggregate,
                                         months_inclusive, month_start, month_end)
from market_structure import average_true_range
from signal_quality_v7 import evaluate_bos_quality
from v92_bull_bear_candle_invalidation import HOUR, FOUR, START, END, stamp, metrics
from v92_higher_timeframe_context import ema20_50_trend
from v92_selected_reversal_patterns import make_selective_gate

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
WINDOW=30*24//4  # 180 sequential 4H returns (=30 complete days)
HIGH_CORR=0.65
MAX_ETH_ATR_RATIO=1.5
PAIRS=(("BTCUSDT","ETHUSDT"),("BTCUSDT","SOLUSDT"),("ETHUSDT","SOLUSDT"))
MODES={
 "BTCUSDT":("V92_BASELINE","THREE_CORR_GE_0P65","THREE_CORR_AND_4H_ALIGNED",
            "BTC_ETH_4H_AGREE"),
 "ETHUSDT":("V92_BASELINE","THREE_CORR_GE_0P65","THREE_CORR_AND_4H_ALIGNED",
            "ETH_BTC_CORR_AND_BTC_4H_AGREE","ETH_ATR_LE_1P5_BTC",
            "ETH_BTC_4H_AGREE_AND_ATR_LE_1P5"),
 "SOLUSDT":("V92_BASELINE","THREE_CORR_GE_0P65","THREE_CORR_AND_4H_ALIGNED",
            "BTC_SOL_4H_AGREE"),
}

def pearson(xs,ys):
    if len(xs)!=WINDOW or len(ys)!=WINDOW:
        raise ValueError("CORR_WINDOW_INCOMPLETE")
    mx=sum(xs)/WINDOW; my=sum(ys)/WINDOW
    a=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    b=sum((x-mx)**2 for x in xs)
    c=sum((y-my)**2 for y in ys)
    return a/math.sqrt(b*c) if b>0 and c>0 else None

def gate_decision(mode,symbol,side,ctx):
    if mode=="V92_BASELINE":return True
    corr=ctx.get("correlations",{})
    reg=ctx.get("trend4H",{})
    at=ctx.get("atrPercent4H",{})
    min_corr=ctx.get("minimumPairCorrelation")
    all_correlated=min_corr is not None and min_corr>=HIGH_CORR
    def paired(a,b):
        k="_".join(sorted([a,b]))
        z=corr.get(k)
        return z is not None and z>=HIGH_CORR
    match=lambda s:reg.get(s)==side
    ratio=(at.get("ETHUSDT")/at.get("BTCUSDT")
           if at.get("BTCUSDT") and at.get("ETHUSDT") else None)
    known={
        "THREE_CORR_GE_0P65":all_correlated,
        "THREE_CORR_AND_4H_ALIGNED":all_correlated and all(match(s) for s in SYMBOLS),
        "BTC_ETH_4H_AGREE":match("BTCUSDT") and match("ETHUSDT"),
        "ETH_BTC_CORR_AND_BTC_4H_AGREE":paired("BTCUSDT","ETHUSDT") and match("BTCUSDT"),
        "ETH_ATR_LE_1P5_BTC":ratio is not None and ratio<=MAX_ETH_ATR_RATIO,
        "ETH_BTC_4H_AGREE_AND_ATR_LE_1P5":match("BTCUSDT") and match("ETHUSDT") and ratio is not None and ratio<=MAX_ETH_ATR_RATIO,
        "BTC_SOL_4H_AGREE":match("BTCUSDT") and match("SOLUSDT"),
    }
    if mode not in MODES[symbol]:
        raise ValueError("CORR_MODE_NOT_AUTHORIZED_FOR_SYMBOL")
    return bool(known[mode])

class AsOfRegimes:
    def __init__(self,hour):
        if set(hour)!=set(SYMBOLS):raise ValueError("CORR_MISSING_SYMBOL")
        self.four={s:aggregate(hour[s],FOUR) for s in SYMBOLS}
        self.closed={s:[z["t"]+FOUR for z in self.four[s]] for s in SYMBOLS}
        self.cache={}

    def at(self,as_of):
        if type(as_of) is not int or as_of%HOUR:
            raise ValueError("CORR_RETEST_NOT_EXACT_CLOSED_1H")
        if as_of in self.cache:return self.cache[as_of]
        idx={s:bisect_right(self.closed[s],as_of)-1 for s in SYMBOLS}
        if min(idx.values())<WINDOW:
            return {"asOfUTC":stamp(as_of),"available":False,
                    "reason":"INSUFFICIENT_PREVIOUSLY_CLOSED_4H_BARS"}
        # Check complete aligned, 4H timeframe and UTC chronology.
        for s in SYMBOLS:
            i=idx[s]; bars=self.four[s]
            assert bars[i]["t"]+FOUR<=as_of
            assert i+1==len([t for t in self.closed[s] if t<=as_of])  # defensive
            if any(bars[j]["t"]+FOUR*(1 if j==i else 0)>as_of
                   for j in (i,)):
                raise ValueError("CORR_FUTURE_CANDLE")
        rtns={}
        trends={}
        atrp={}
        for s in SYMBOLS:
            bars=self.four[s]; i=idx[s]
            rtns[s]=[math.log(bars[j]["c"]/bars[j-1]["c"])
                     for j in range(i-WINDOW+1,i+1)]
            trends[s]=ema20_50_trend(bars[:i+1])
            atr=average_true_range(bars,i,count=14)
            atrp[s]=100*atr/bars[i]["c"]
        corrs={}
        for a,b in PAIRS:
            label="_".join(sorted((a,b)))
            corrs[label]=pearson(rtns[a],rtns[b])
        available=[x for x in corrs.values() if x is not None]
        min_corr=min(available) if len(available)==len(PAIRS) else None
        out={"asOfUTC":stamp(as_of),"available":True,
             "lastAll4HCloseUTC":stamp(min(self.closed[s][idx[s]] for s in SYMBOLS)),
             "correlations":{k:round(v,7) if v is not None else None for k,v in corrs.items()},
             "minimumPairCorrelation":round(min_corr,7) if min_corr is not None else None,
             "trend4H":trends,
             "atrPercent4H":{k:round(v,7) for k,v in atrp.items()},
             "ethAtrPercentVsBTC":round(atrp["ETHUSDT"]/atrp["BTCUSDT"],7) if atrp["BTCUSDT"]>0 else None,
             "highAllThreeCorrAtRetest":min_corr is not None and min_corr>=HIGH_CORR,
             "allPricesAlreadyClosed":True,
             "window4HReturns":WINDOW,
             "noFutureCandles":True}
        self.cache[as_of]=out
        return out

def gate_for(symbol,mode,regimes,audit):
    candle=make_selective_gate(symbol,regimes.four[symbol],
                               "SELECTED_SOL_STRICT_SWEEP",
                               Counter(examples=[])) if symbol=="SOLUSDT" else None
    def gate(one,active,retest):
        at=int(retest["t"])+HOUR
        if active["knownUTC"]>=at:raise ValueError("CORR_BOS_NOT_PREVIOUS")
        audit["checkedOriginalRetests"]+=1
        if candle:
            z=candle(one,active,retest)
            if not z["passed"]:
                audit["blockedByOriginalV92Candle"]+=1
                return z
        if mode=="V92_BASELINE":
            return {"passed":True,"reasons":[]}
        ctx=regimes.at(at)
        if not ctx["available"]:
            audit["insufficientRegimeWarmup"]+=1
            return {"passed":False,"reasons":["CORR_4H_WARMUP_INSIDE_SAMPLE"]}
        passed=gate_decision(mode,symbol,active["side"],ctx)
        if passed:audit["passedCorrelationOrRegime"]+=1
        else:audit["rejectedCorrelationOrRegime"]+=1
        if len(audit["exampleDecisions"])<15:
            audit["exampleDecisions"].append({
                "atUTC":stamp(at),"side":active["side"],"passed":passed,
                "minCorr":ctx["minimumPairCorrelation"],
                "btcEthCorr":ctx["correlations"]["BTCUSDT_ETHUSDT"],
                "btcTrend":ctx["trend4H"]["BTCUSDT"],
                "ethTrend":ctx["trend4H"]["ETHUSDT"],
                "solTrend":ctx["trend4H"]["SOLUSDT"],
                "ethAtrRatio":ctx["ethAtrPercentVsBTC"],
            })
        return {"passed":passed,"reasons":[] if passed else
                ["RESEARCH_ONLY_"+mode+"_NOT_MET"]}
    return gate

def diagnostic_trades(reference,regimes):
    out=[]
    for t in reference["trades"]:
        if not START<=t["entryOpenUTC"]<END or t["exitKnownUTC"]>END:
            continue
        ctx=regimes.at(t["retestKnownUTC"])
        if not ctx["available"]:raise ValueError("CORR_BASELINE_RETEST_MISSING_30D_CONTEXT")
        out.append({
            "watchKnownUTC":stamp(t["watchKnownUTC"]),
            "retestUTC":stamp(t["retestKnownUTC"]),
            "entryUTC":stamp(t["entryOpenUTC"]),
            "exitUTC":stamp(t["exitKnownUTC"]),
            "side":t["side"],
            "netR9bps":round(t["netRIllustrative"],6),
            "winner":t["netRIllustrative"]>0,
            "exitReason":t["exitReason"],
            "last4HKnownUTC":ctx["lastAll4HCloseUTC"],
            "tripleCorrHigh":ctx["highAllThreeCorrAtRetest"],
            "btcEthCorr":ctx["correlations"]["BTCUSDT_ETHUSDT"],
            "btcSolCorr":ctx["correlations"]["BTCUSDT_SOLUSDT"],
            "ethSolCorr":ctx["correlations"]["ETHUSDT_SOLUSDT"],
            "allThree4HAligned":all(ctx["trend4H"][s]==t["side"] for s in SYMBOLS),
            "btc4HAligned":ctx["trend4H"]["BTCUSDT"]==t["side"],
            "eth4HAligned":ctx["trend4H"]["ETHUSDT"]==t["side"],
            "sol4HAligned":ctx["trend4H"]["SOLUSDT"]==t["side"],
            "relativeEth4HATRvsBTC":ctx["ethAtrPercentVsBTC"],
            "onlyPreRetestClosed4HUsed":True,
            "notForwardProof":True,
        })
    return out

def analyze(hour):
    for s in SYMBOLS:
        rows=hour[s]
        if (len(rows)!=17520 or rows[0]["t"]!=START or
            rows[-1]["t"]+HOUR!=END or
            any(rows[i]["t"]!=START+i*HOUR for i in range(len(rows)))):
            raise ValueError("CORR_INVALID_SHA_VERIFIED_HOURLY_SPAN_"+s)
    regimes=AsOfRegimes(hour)
    data={}
    for symbol in SYMBOLS:
        hrs=hour[symbol]
        four=regimes.four[symbol]
        daily=aggregate(hrs,24*HOUR)
        result={"verified1H":len(hrs),"variants":{},"baselineTrades":[]}
        for mode in MODES[symbol]:
            audit=Counter()
            audit["exampleDecisions"]=[]
            replay=replay_pair(hrs,four,daily,as_of=END,
                               retest_hours=4,
                               bos_quality_filter=evaluate_bos_quality,
                               retest_quality_filter=gate_for(symbol,mode,regimes,audit))
            score=metrics(replay,START,END)
            result["variants"][mode]={
               **score,
               "regimeGateAudit":dict(audit),
            }
            if mode=="V92_BASELINE":
                result["baselineTrades"]=diagnostic_trades(replay,regimes)
            print("V92_CORR_REPLAY",symbol,mode,
                  "trades",score["trades"],
                  "netR",score["totalNetR9BpsPerSide"],
                  "stress",score["totalNetR25BpsPerSideStress"],flush=True)
        data[symbol]=result
    return data

def run(workers=6):
    months=months_inclusive("2024-10","2026-09")
    if len(months)!=24 or not 1<=workers<=6:
        raise ValueError("CORR_FIXED_HISTORY_24_MONTHS")
    sources={s:{} for s in SYMBOLS}; manifests=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(download_month,s,m):(s,m)
                 for s in SYMBOLS for m in months}
        for future in as_completed(futures):
            sym,m,rows,proof=future.result()
            if futures[future]!=(sym,m):
                raise ValueError("CORR_ARCHIVE_SYMBOL_MONTH_MISMATCH")
            sources[sym][m]=rows
            manifests.append({"symbol":sym,"month":m,**proof})
            print("V92_CORR_ARCHIVE_SHA_VERIFIED",sym,m,len(rows),flush=True)
    if len(manifests)!=72 or any(len(q["sha256"])!=64 for q in manifests):
        raise ValueError("CORR_ARCHIVE_MISSING_SHA256")
    hour={s:[r for m in months for r in sources[s][m]] for s in SYMBOLS}
    result={
      "status":"V92_THREE_ASSET_ASOF_4H_CORRELATION_AND_ETH_LOSS_HISTORICAL_RESEARCH",
      "periodUTC":[stamp(START),stamp(END)],
      "source":"Binance official USD-M 1H archives (72 monthly SHA256 verified ZIPs)",
      "verifiedMonthlySHA256Files":72,
      "sourceManifest":sorted(manifests,key=lambda x:(x["symbol"],x["month"])),
      "corrFormula":"Pearson correlation of 180 already-completed 4H log returns",
      "corrWindowDays":30,
      "highCorrelationThreshold":HIGH_CORR,
      "trendDefinition":"Closed 4H close vs 4H EMA20/EMA50",
      "atrDefinition":"14 closed 4H TR average divided by latest closed 4H price",
      "noFutureCandleAtRetest":True,
      "usesSameV7BOSQualityAndV91Max4hRetestBaseline":True,
      "retainsV92SOLStarHaramiSweepVeto":True,
      "alreadyInspectedHistoricalPeriodNotOutOfSample":True,
      "noRealOrders":True,"noUserNotifications":True,
      "productionV7V91V92Unchanged":True,
      "historicalBacktestDoesNotCountAsForwardPaper":True,
      "assets":analyze(hour),
    }
    return result

def markdown(x):
    out=["# BTC / ETH / SOL — triple 30D correlation and 4H regime historical research",
         "","**Historical research, not forward evidence or a trading instruction.**",
         "","**Data:** 72 official Binance USD-M monthly 1H ZIPs SHA256 verified,",
         "October 2024 to September 2026; all 4H bars are already CLOSED at the",
         "original later 1H retest decision.","",
         "Pearson correlation over 180 fully closed 4H log returns per pair;",
         "high correlation means all three pair correlations >=0.65.","",
         "| Symbol | Mode | Trades | Wins | Net R 9bps | Net R 25bps | Max DD R | Retest veto |",
         "|---|---|---:|---:|---:|---:|---:|---:|"]
    for sym,asset in x["assets"].items():
        for mode,z in asset["variants"].items():
            out.append(f"| {sym} | {mode} | {z['trades']} | {z['wins']} | "
                       f"{z['totalNetR9BpsPerSide']:+.4f} | "
                       f"{z['totalNetR25BpsPerSideStress']:+.4f} | "
                       f"{z['maxDrawdownR']:.4f} | {z['retestVetoes']} |")
    out.extend(["","## ETH baseline trades classified by information known at retest",
                "","| Entry UTC | Direction | Net R | BTC/ETH 30D corr | All3 corr >=0.65 | BTC 4H aligned | ETH ATR% / BTC ATR% |",
                "|---|---|---:|---:|---|---|---:|"])
    for t in x["assets"]["ETHUSDT"]["baselineTrades"]:
        out.append(f"| {t['entryUTC']} | {t['side']} | {t['netR9bps']:+.4f} | "
                   f"{t['btcEthCorr']} | {t['tripleCorrHigh']} | "
                   f"{t['btc4HAligned']} | {t['relativeEth4HATRvsBTC']} |")
    out.extend(["","## Limitations","",
                "- Same historical period had already been studied, so selecting any winner is post-selection and not independent validation.",
                "- A 4H candle closing *after* a retest cannot contribute to its signal.",
                "- All three correlation is not three independent risks; shared positions may amplify joint market drawdown.",
                "- ETH historical Binance/CoinAlyze live-source parity is not guaranteed.",
                "- Brokerage costs assumed; no funding, exchange book slippage, real executions or liquidations.",
                "- Tiny historical trade samples; a 0-trade filter has 0 R because it does not trade, not because profitable.",
                "- V7 and V9.2 production and capped paper risk settings are untouched; no historical trades backfilled.",
                ""])
    return "\n".join(out)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",default="forward/v92_three_asset_correlation_20261113")
    p.add_argument("--workers",type=int,default=6)
    args=p.parse_args()
    data=run(args.workers)
    dest=Path(args.out);dest.mkdir(parents=True,exist_ok=True)
    (dest/"historical.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    (dest/"historical.md").write_text(markdown(data)+"\n")
    print("V92_THREE_ASSET_CORRELATION_STUDY_COMPLETE",flush=True)
if __name__=="__main__":
    main()
