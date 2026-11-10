#!/usr/bin/env python3
"""V8 causal signal-filter ablation: explain attrition, not tune profitable rules.

Uses exactly the same confirmed Binance USD-M monthly 1H archives, 4H/D
aggregation, fill/cost/risk rules and fixed 2025-01--2026-09 span as the
existing three-asset paper benchmark. A previously developed V7 BOS-only
configuration is the preexisting candidate. All other comparisons are
DIAGNOSTIC on the repeatedly inspected history; no fresh out-of-sample.
NO BROKER ORDERS and no promotion to production.
"""
import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from backtest_retest_long_v4 import replay_pair
from signal_quality_v7 import evaluate_bos_quality, evaluate_retest_quality
from v8_three_asset_confluence_backtest import (
    SYMBOLS, PAIRS, START, END, SPLIT, validated_archives, metrics,
    make_gates, retest_features, unix, iso,
)

def ablate(bars, split):
    as_of=bars["1hour"][-1]["t"]+3600
    epoch=unix(split)
    beginning=bars["1hour"][0]["t"]
    gate_b, _gate_r, dummy=make_gates(bars["4hour"],bars["daily"])
    observations={}
    def watch_only_retest(hist, active, bar):
        f=retest_features(hist,active,bar)
        v7=evaluate_retest_quality(hist,active,bar)
        key=(bar["t"]+3600,active["side"],active["knownUTC"])
        # Features are only measured when this retest candle CLOSED.
        observations[key]={
            "score":sum(f.values()),"features":f,
            "v7_retest_passed":v7["passed"],
        }
        return {"passed":True,"reasons":[]}

    # V7 BOS-only is an actual historical strategy baseline, NOT a new
    # post-hoc ruleset selected from the 2026 Jul-Sep observations.
    candidates=[
        ("V7_BOS_only_existing",{
            "bos_quality_filter":evaluate_bos_quality,
            "retest_quality_filter":None,
        }),
        ("V8_EMA_trend_only_context_shadow",{
            "bos_quality_filter":gate_b,
            "retest_quality_filter":watch_only_retest,
        }),
    ]
    results={}
    for name,kwargs in candidates:
        print("ABLATION_REPLAY",name,flush=True)
        sim=replay_pair(bars["1hour"],bars["4hour"],bars["daily"],
                        as_of=as_of,**kwargs)
        if sim["status"]!="PAPER_BACKTEST_NOT_LIVE":
            raise RuntimeError("SIMULATION_INCOMPLETE_"+name)
        results[name]={
            "allTrades":sim["hypotheticalClosedTrades"],
            "allAlerts":sim["alertsCount"],
            "preSplit":metrics(sim["trades"],beginning,epoch),
            "reusedHistoricalHoldout":metrics(sim["trades"],epoch,as_of),
            "rejectedBOS":sim["qualityGateRejectedBOS"],
            "unresolvedExcluded":sim["unresolvedPositionExcluded"],
            "pendingEntryExcluded":sim["pendingEntryExcluded"],
        }
        if name=="V8_EMA_trend_only_context_shadow":
            breakdown=Counter()
            joined=[]
            for trade in sim["trades"]:
                key=(trade["retestKnownUTC"],trade["side"],trade["watchKnownUTC"])
                found=observations.get(key)
                if found is None:
                    raise RuntimeError("MISSING_RETEST_CONTEXT")
                class_key=("score>=2" if found["score"]>=2 else "score<2")
                breakdown[class_key]+=1
                row={"entryOpenUTC":iso(trade["entryOpenUTC"]),
                     "signalSide":trade["side"],"confluenceScore":found["score"],
                     "v7StrongRetestPassed":found["v7_retest_passed"],
                     "netR":round(trade["netRIllustrative"],6),
                     "features":found["features"],
                     "isReusedHoldout":trade["entryOpenUTC"]>=epoch}
                joined.append(row)
            results[name]["diagnosticOnly"]={
                "retestObservationsAtClosedTime":len(observations),
                "completedTradeScores":dict(breakdown),
                "tradeFeatureAudit":joined,
                "caution":"Post-outcome association only; no post-hoc rule selection."}
    return results


def run(args):
    full,manifest=validated_archives(args.start,args.end,args.workers)
    output={
        "mode":"V8_THREE_ASSET_DIAGNOSTIC_ABLATION_NO_ORDERS",
        "status":"RESEARCH_ONLY_NO_PERFORMANCE_APPROVAL",
        "createdUTC":datetime.now(timezone.utc).isoformat(),
        "period":{"start":args.start,"end":args.end,
                  "reusedHoldoutStartsUTC":args.split},
        "officialBinanceChecksumVerifiedZIPs":len(manifest),
        "units":"USDT; each coin independently starts at 100 USDT, 10x notional cap, 0.50 USDT risk ceiling",
        "method":"Previously established V7 BOS-only rule vs V8 EMA trend vote without hard OB/FVG/Fib filter.",
        "holdoutContaminatedByEarlierAnalysis":True,
        "prohibitThresholdFittingOrLiveTrading":True,
        "symbolResults":{},
        "brokerOrders":False,"productionSystemModified":False,
    }
    for sym in SYMBOLS:
        output["symbolResults"][sym]=ablate(full[sym],args.split)
        print("ABLATION_COMPLETE",sym,flush=True)
    return output


def render(d):
    lines=["# V8 signal-filter ablation — BTC / ETH / SOL",
           "","This is a **repeatedly inspected historical period**, not fresh out-of-sample.",
           "No actual trades, no new threshold tuning, no authorization for live entry.",
           "",
           "| Asset | Variant | Earlier paper trades | Earlier net USD | Reused Jul-Sep trades | Reused Jul-Sep net USD |",
           "|---|---|---:|---:|---:|---:|"]
    for coin,results in d["symbolResults"].items():
        for variant,row in results.items():
            pre=row["preSplit"]
            hold=row["reusedHistoricalHoldout"]
            lines.append(f"| {coin} | {variant} | {pre['trades']} | {pre['netPnLUSDT']:+.3f} | "
                         f"{hold['trades']} | {hold['netPnLUSDT']:+.3f} |")
        diag=results["V8_EMA_trend_only_context_shadow"]["diagnosticOnly"]
        lines.append("")
        lines.append(f"- {coin} retest closed-candle feature readings: {diag['retestObservationsAtClosedTime']}; "
                     f"completed trades with score below 2: {diag['completedTradeScores'].get('score<2',0)}; "
                     f"score >= 2: {diag['completedTradeScores'].get('score>=2',0)}.")
    lines+=["","**Interpretation:** This can diagnose scarcity from rule confluence, "
            "not prove profitable future performance. Future paper-forward outcomes "
            "are the required next independent evaluation.",
            "",
            "No OI/funding/cross-asset votes included in historical entries because "
            "their contemporary availability is not verified throughout the study."]
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default=START)
    p.add_argument("--end",default=END)
    p.add_argument("--split",default=SPLIT)
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--output",required=True)
    p.add_argument("--markdown",required=True)
    args=p.parse_args()
    if args.workers<1 or args.workers>6:
        raise ValueError("WORKERS_1_TO_6")
    output=run(args)
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    md=Path(args.markdown)
    md.parent.mkdir(parents=True,exist_ok=True)
    md.write_text(render(output),encoding="utf-8")
    print("V8_ABLATION_RESEARCH_COMPLETED",flush=True)


if __name__=="__main__":
    main()
