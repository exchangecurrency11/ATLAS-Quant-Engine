#!/usr/bin/env python3
"""Research-only two-year BTC/ETH chronological BOS-retest forensics.

- Binance USD-M official 1H ZIPs & SHA256 (48 total); derived 4H and daily.
- Existing V7 quality BOS + V9.1 4H retest engine, unchanged fills/stops/TP.
- Fixed exploratory gates use only *closed retest-hour* info.
- Exact historical V9.1 source parity required before interpreting variants.
- These are selection-biased historical samples, NOT prospective or true fills.
- No V7/V9.1/V9.2 strategy edits, broker orders or notifications.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json
import math
from pathlib import Path

from backtest_retest_long_v4 import replay_pair,earliest_stop
from download_binance_um_history import (
    aggregate,download_month,month_start,month_end,months_inclusive)
from market_structure import average_true_range
from signal_quality_v7 import evaluate_bos_quality
from v92_bull_bear_candle_invalidation import START,END,HOUR,stamp,metrics
from v92_higher_timeframe_context import context_at

SYMBOLS=("BTCUSDT","ETHUSDT")
REQUIRED_MODES={
  "BTCUSDT":(
   "BASELINE_4H","BASELINE_6H",
   "BTC_SHORT_ONLY",
   "BTC_DAILY_TREND_ALIGNED",
   "BTC_1H_ATR_VOL_GE_0P5PCT",
   "BTC_RETEST_STOPWIDTH_LE_2ATR",
  ),
  "ETHUSDT":(
   "BASELINE_4H","BASELINE_6H",
   "ETH_SHORT_ONLY",
   "ETH_RETEST_STOPWIDTH_LE_2ATR",
   "ETH_RETEST_BODY_GE_0P2ATR",
   "ETH_RETEST_RVOL20_GE_1P2",
   "ETH_SHORT_AND_STOPWIDTH_LE_2ATR",
  ),
}

def info_at_retest(one,active,daily):
    """All fields known when the 1H retest candle has CLOSED."""
    ret=one[-1]
    asof=ret["t"]+HOUR
    if ret["t"]+HOUR!=asof or active["knownUTC"]>=asof:
        raise ValueError("FORENSICS_NOT_PRECONFIRMED_BOS")
    atr=average_true_range(one,len(one)-1,count=14)
    if atr is None or atr<=0 or not math.isfinite(atr):
        raise ValueError("FORENSICS_NO_RETEST_ATR")
    stop=earliest_stop(active["side"],active["bosBar"],ret,atr)
    stop_atr=abs(stop-ret["c"])/atr
    if not math.isfinite(stop_atr):
        raise ValueError("FORENSICS_NONFINITE_STOP")
    prior=one[-21:-1]
    if len(prior)!=20 or any(z["t"]>=ret["t"] for z in prior):
        raise ValueError("FORENSICS_PRIOR_VOLUME_NOT_ASOF")
    mean_volume=sum(z["v"] for z in prior)/20
    rvol=(ret["v"]/mean_volume if mean_volume>0 else 0)
    regime=context_at(daily,asof)["1D"]
    side=active["side"]
    return {
        "asOfClosed1HUTC":stamp(asof),"side":side,
        "atr14":atr,"stopRelativeATRRetestClose":stop_atr,
        "atrPctOfRetestClose":100*atr/ret["c"],
        "retestBodyATR":abs(ret["c"]-ret["o"])/atr,
        "retestRelativeVolume20":rvol,
        "dailyEMA20_50Regime":regime,
        "dailyAlignedWithBOS":regime==side,
        "noFutureCandlesUsed":True,
    }

def accepted(mode,features):
    side=features["side"]
    if mode.startswith("BASELINE_"):return True
    rules={
      "BTC_SHORT_ONLY":side=="bearish",
      "BTC_DAILY_TREND_ALIGNED":features["dailyAlignedWithBOS"],
      "BTC_1H_ATR_VOL_GE_0P5PCT":features["atrPctOfRetestClose"]>=0.5,
      "BTC_RETEST_STOPWIDTH_LE_2ATR":features["stopRelativeATRRetestClose"]<=2.,
      "ETH_SHORT_ONLY":side=="bearish",
      "ETH_RETEST_STOPWIDTH_LE_2ATR":features["stopRelativeATRRetestClose"]<=2.,
      "ETH_RETEST_BODY_GE_0P2ATR":features["retestBodyATR"]>=0.2,
      "ETH_RETEST_RVOL20_GE_1P2":features["retestRelativeVolume20"]>=1.2,
      "ETH_SHORT_AND_STOPWIDTH_LE_2ATR":(
          side=="bearish" and features["stopRelativeATRRetestClose"]<=2.),
    }
    if mode not in rules:
        raise ValueError("FORENSICS_UNREGISTERED_MODE_"+mode)
    return rules[mode]

def gate_for(mode,daily,audit):
    def gate(one,active,retest):
        info=info_at_retest(one,active,daily)
        if info["asOfClosed1HUTC"]!=stamp(retest["t"]+HOUR):
            raise ValueError("FORENSICS_MISMATCHED_CLOSE")
        audit["evaluatedRetests"]+=1
        decision=accepted(mode,info)
        if not decision:audit["rejectedRetests"]+=1
        if len(audit["examples"])<12:
            audit["examples"].append({
               **{k:round(v,6) if isinstance(v,float) else v
                  for k,v in info.items() if k not in ("atr14",)},
               "passed":decision})
        return {"passed":decision,
                "reasons":[] if decision else ["RESEARCH_"+mode+"_NOT_MET"]}
    return gate

def trade_diagnostics(result,hour,daily):
    """Inspect *the same untouched baseline trade ledger*, not optimized exits."""
    bytime={b["t"]:i for i,b in enumerate(hour)}
    out=[]
    for tr in result["trades"]:
        if not(START<=tr["entryOpenUTC"]<END and tr["exitKnownUTC"]<=END):
            continue
        ri=bytime.get(tr["retestKnownUTC"]-HOUR)
        if ri is None or ri<20:
            raise ValueError("FORENSICS_RETEST_NOT_IN_ARCHIVE")
        atr=average_true_range(hour,ri,count=14)
        ret=hour[ri]
        if atr is None or atr<=0:
            raise ValueError("FORENSICS_MISSING_TRADE_ATR")
        ratio=tr["risk"]/atr
        if not math.isfinite(ratio) or ratio<=0:
            raise ValueError("FORENSICS_INVALID_TRADE_RISK_ATR")
        history=hour[ri-20:ri]
        mean=sum(x["v"] for x in history)/len(history)
        out.append({
          "side":tr["side"],
          "entryUTC":stamp(tr["entryOpenUTC"]),
          "retestUTC":stamp(tr["retestKnownUTC"]),
          "exitUTC":stamp(tr["exitKnownUTC"]),
          "exitReason":tr["exitReason"],
          "entryNextOpenPrice":round(tr["entry"],6),
          "stop":round(tr["stop"],6),
          "absoluteStopRisk":round(tr["risk"],6),
          "stopDistanceAsATR14AtRetest":round(ratio,6),
          "retestBodyAsATR14":round(abs(ret["c"]-ret["o"])/atr,6),
          "retestRVOL20":round(ret["v"]/mean,6) if mean>0 else None,
          "ret1HATRPct":round(100*atr/ret["c"],6),
          "dailyRegimeAtRetest":context_at(daily,tr["retestKnownUTC"])["1D"],
          "cost9BpsNetR":round(tr["netRIllustrative"],6),
          "isWinnerAfterAssumed9Bps":tr["netRIllustrative"]>0,
          "scoreUsesKnownHistoricalOutcomeOnly":True,
          "notExecutableFillProof":True,
        })
    return out

def robust_performance(result,summary):
    return {"trades":summary["trades"],"wins":summary["wins"],
            "winRatePct":summary["winRatePct"],
            "netR9BpsPerSide":summary["totalNetR9BpsPerSide"],
            "netR25BpsStress":summary["totalNetR25BpsPerSideStress"],
            "profitFactor":summary["profitFactor"],
            "maxRealizedDrawdownR":summary["maxDrawdownR"],
            "watchCount":summary["BOSWatches"],
            "expiredRetestCount":summary["retestExpires"],
            "vetoedRetestCount":summary["retestVetoes"],
            "riskRuleRejected":result["riskRuleRejected"],
            "unresolvedOrPendingExcluded":result["unresolvedPositionExcluded"]
             or result["pendingEntryExcluded"]}

def symbol_study(symbol,rows):
    if len(rows)!=17520 or rows[0]["t"]!=START or rows[-1]["t"]+HOUR!=END:
        raise ValueError("FORENSICS_INVALID_VERIFIED_TWO_YEAR_RANGE")
    four=aggregate(rows,4*HOUR)
    daily=aggregate(rows,24*HOUR)
    data={"symbol":symbol,
          "verifiedCandles":{"1H":len(rows),"4H":len(four),"1D":len(daily)},
          "results":{}, "originalTrades":[], "directionTotals":{}}
    base=None
    for mode in REQUIRED_MODES[symbol]:
        a=Counter()
        a["examples"]=[]
        hours=6 if mode=="BASELINE_6H" else 4
        filt=None if mode.startswith("BASELINE") else gate_for(mode,daily,a)
        result=replay_pair(rows,four,daily,as_of=END,retest_hours=hours,
                           bos_quality_filter=evaluate_bos_quality,
                           retest_quality_filter=filt)
        score=metrics(result,START,END)
        if mode=="BASELINE_4H":
            base=result
            data["originalTrades"]=trade_diagnostics(result,rows,daily)
        data["results"][mode]={
           **robust_performance(result,score),
           "gateAudit":dict(a) if filt is not None else {"unchangedOriginal":True},
           "tradeEntryExitEvidence":score["tradeEntryExitEvidence"],
        }
        print("FORENSICS_MODEL",symbol,mode,
              "trades",score["trades"],
              "R",score["totalNetR9BpsPerSide"],
              "stress",score["totalNetR25BpsPerSideStress"],flush=True)
    if base is None:
        raise ValueError("FORENSICS_BASELINE_ABSENT")
    for side in ("bullish","bearish"):
        ts=[t for t in data["originalTrades"] if t["side"]==side]
        data["directionTotals"][side]={
          "trades":len(ts),
          "wins":sum(t["isWinnerAfterAssumed9Bps"] for t in ts),
          "netR":round(sum(t["cost9BpsNetR"] for t in ts),6)}
    return data

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",default="forward/v92_btc_eth_forensics_20261113")
    p.add_argument("--workers",type=int,default=6)
    args=p.parse_args()
    if args.workers<1 or args.workers>6:
        p.error("workers must be 1..6")
    months=months_inclusive("2024-10","2026-09")
    source_files=[]
    per={s:{} for s in SYMBOLS}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        tasks={pool.submit(download_month,s,m):(s,m)
               for s in SYMBOLS for m in months}
        for f in as_completed(tasks):
            sym,mon,rows,proof=f.result()
            if tasks[f]!=(sym,mon):
                raise ValueError("FORENSICS_INVALID_SOURCE_PAIR")
            per[sym][mon]=rows
            source_files.append({"symbol":sym,"month":mon,**proof})
            print("FORENSICS_SHA256_MONTH",sym,mon,flush=True)
    if len(source_files)!=48 or any(len(x["sha256"])!=64 for x in source_files):
        raise ValueError("FORENSICS_ALL_48_SHA256_REQUIRED")
    out={
       "status":"V92_BTC_ETH_CHRONOLOGICAL_LOSS_AND_REGIME_FORENSICS_ONLY",
       "period":[stamp(START),stamp(END)],
       "marketData":"48 official Binance USD-M 1H ZIPs with each SHA256 verified",
       "sourceManifest":{"checksumsVerified":len(source_files),
                         "inputFiles":sorted(source_files,key=lambda x:(x["symbol"],x["month"]))},
       "usesOriginalV7BOSQualityAndV91NextOpenExitEngine":True,
       "closedRetestFiltersOnly":True,
       "stopDistanceFiltersDoNOTChangeTheStopPrice":True,
       "stressCostBpsPerSide":25,
       "baseCostBpsPerSide":9,
       "independentSelectionBiasedHistoricalSample":False,
       "noBrokerOrders":True,
       "noUserNotifications":True,
       "productionV7V91V92Unchanged":True,
       "noRetrospectiveTradesAddedToForwardBook":True,
       "assets":{},
    }
    for sym in SYMBOLS:
        rows=[b for mon in months for b in per[sym][mon]]
        out["assets"][sym]=symbol_study(sym,rows)
    loc=Path(args.out);loc.mkdir(parents=True,exist_ok=True)
    (loc/"historical.json").write_text(
        json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (loc/"historical.md").write_text(md(out)+"\n",encoding="utf-8")
    print("FORENSICS_BACKTEST_2_ASSETS_COMPLETE",flush=True)

def md(x):
    lines=["# V9.2 BTC/ETH losses, stop-ATR and regime test",
          "","**RESEARCH ONLY. NO BROKER ORDERS. No live V7/V9.2 modifications.**",
          "","Period: 2024-10 through 2026-09; official Binance USD-M archives, 48 verified SHA256 ZIPs.",
          "These experiments were selected after seeing earlier performance: results are",
          "exploratory and not out-of-sample evidence. Baseline uses the original",
          "V7 BOS quality and V9.1 four-hour retest chronological next-open simulation.",
          "","## Comparative results",
          "",
          "| Asset | Variant | Trades | Wins | Net R (9bps) | Stress R (25bps) | PF | Max DD R | Veto |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for s,d in x["assets"].items():
        for mode,a in d["results"].items():
            lines.append(
               f"| {s} | {mode} | {a['trades']} | {a['wins']} | "
               f"{a['netR9BpsPerSide']:+.3f} | {a['netR25BpsStress']:+.3f} | "
               f"{a['profitFactor']} | {a['maxRealizedDrawdownR']:.3f} | "
               f"{a['vetoedRetestCount']} |")
    lines.extend(["","## Baseline trade diagnostics",
                  "","| Asset | Entry UTC | Direction | Net R | Stop / ATR14 | Retest RVOL20 | Daily regime | Exit |",
                  "|---|---|---|---:|---:|---:|---|---|"])
    for s,d in x["assets"].items():
        for t in d["originalTrades"]:
            lines.append(f"| {s} | {t['entryUTC']} | {t['side']} | {t['cost9BpsNetR']:+.3f} | "
                         f"{t['stopDistanceAsATR14AtRetest']:.2f} | {t['retestRVOL20']} | "
                         f"{t['dailyRegimeAtRetest']} | {t['exitReason']} |")
    lines.extend(["","## Important limitations","",
      "- The 2-year period had previously been analyzed, so differences are selection-biased hypotheses.",
      "- Gate decisions are known at retest close; original entry remains next 1H *open*, not live executable fill.",
      "- ATR stop-width scenario vetoes trades; it never edits historical stop/TP prices.",
      "- All costs are assumed; no full funding, spread variation, liquidation, orderbook or slippage proof.",
      "- Too few trades to conclude statistical significance, especially one-direction subsets.",
      "- Historical completed trades cannot count toward the 50 genuinely prospective completed trades gate.",
      "- Source data do not establish historical Coinalyze/Binance parity for ETH; official Binance only.",
      "",""])
    return "\n".join(lines)

if __name__=="__main__":
    main()
