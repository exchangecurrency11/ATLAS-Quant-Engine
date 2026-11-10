#!/usr/bin/env python3
"""V8.2 SOL same frozen Fib/pivot criteria on earlier 2023–24 archival history.

The code/rules are identical to V8.2 2025–26; no threshold adjustment.
Older data is an additional *historical* robustness check, not prospective
live validation. No orders, no execution. Every archive SHA256 verified.
"""
import json
from pathlib import Path
from datetime import datetime,timezone
from sol_v81_htf_role_flip_research import official_history
from sol_v82_fib_pivot_confluence import evaluate,wilson_lower,render,MIN_EVENTS_FOR_PRELIMINARY_CONFIDENCE

OLDER_START="2023-01"
OLDER_END="2024-12"
EARLIER=Path("forward/v82_fib_pivot/latest.json")
OUTPUT=Path("forward/v82_fib_pivot/older_2023_2024.json")
OUTPUT_MD=Path("forward/v82_fib_pivot/older_2023_2024.md")


def combined(older,new):
    x={}
    for name in older:
        a=older[name]
        b=new[name]
        n=a["complete24hObservations"]+b["complete24hObservations"]
        succ=a["lowerAfter24h"]+b["lowerAfter24h"]
        pct=round(succ*100/n,2) if n else None
        x[name]={"older24hObservations":a["complete24hObservations"],
                 "recent24hObservations":b["complete24hObservations"],
                 "complete24hObservations":n,
                 "lowerAfter24h":succ,
                 "directionHitRatePct":pct,
                 "wilson95LowerBoundPct":round(100*wilson_lower(succ,n),2) if n else None,
                 "observed75PctGoal":pct is not None and pct>=75,
                 "atLeast30":n>=MIN_EVENTS_FOR_PRELIMINARY_CONFIDENCE,
                 "provenPredictiveAdvantage":False}
    return x


def run():
    recent=json.loads(EARLIER.read_text())
    if recent.get("status")!="HISTORICAL_EXPLORATION_NO_LIVE_SIGNAL":
        raise ValueError("MISSING_VALID_PRIOR_RESEARCH_RESULT")
    if recent.get("period",{}).get("start")!="2025-01" or recent.get("period",{}).get("end")!="2026-09":
        raise ValueError("COMPARISON_PERIOD_CHANGED")
    p=recent.get("frozenParameters",{})
    if p.get("thresholdTunedToOutcomes") is not False or p.get("MACDUsed") is not False:
        raise ValueError("COMPARISON_RULES_NOT_FROZEN")
    four,daily,proofs=official_history(OLDER_START,OLDER_END,6)
    rows,results,counts=evaluate(four,daily)
    newer=recent["filterResults"]["all"]
    older=results["all"]
    joined=combined(older,newer)
    return {"mode":"V82_SOL_UNMODIFIED_FIB_PIVOT_EARLIER_HISTORICAL_REPLICATION",
            "status":"HISTORICAL_ROBUSTNESS_CHECK_NO_LIVE_SIGNAL",
            "createdUTC":datetime.now(timezone.utc).isoformat(),
            "earlierPeriod":{"start":OLDER_START,"end":OLDER_END},
            "earlierVerifiedChecksumArchives":len(proofs),
            "earlierMarket":"Binance USD-M SOLUSDT 1H official monthly archives",
            "earlierCounts":counts,
            "rulesUnchangedFrom2025_2026":True,
            "frozenParameters":p,
            "earlier":older,
            "recent2025_2026":newer,
            "combinedHistorical":joined,
            "earlierExamples":rows[-12:],
            "repeatedComparisonsNotAdjustedForMultipleTesting":True,
            "notRealTimeProspectiveEvidence":True,
            "brokerOrders":False,"liveTradingApproved":False,
            "productionModified":False}


def to_md(doc):
    out=[
      "# V8.2 SOL — Fibonacci/Pivot historical robustness check, earlier 2023–24",
      "",
      "Fixed rules from the 2025–26 study applied unchanged to **2023–24**; "
      "this is retrospective older-market validation, not prospective trading evidence.",
      "",
      "| Filter | Earlier 2023–24 | 2025–26 | Combined historical | 75% goal met? |",
      "|---|---|---|---|---|"]
    for name,v in doc["combinedHistorical"].items():
        early=doc["earlier"][name]
        new=doc["recent2025_2026"][name]
        def cell(x):
            n=x["complete24hObservations"]
            return f"{x['lowerAfter24h']}/{n} ({x['directionHitRatePct']}%)" if n else "No cases"
        out.append(f"| {name} | {cell(early)} | {cell(new)} | "
                   f"{cell(v)} | {'Yes, historic only' if v['observed75PctGoal'] else 'No'} |")
    out+=["","## Limits",
          "- Historical periods were investigated backwards from a research hypothesis; never mistake this for forward testing.",
          "- Even an observed 75% rate requires large samples, stable splits, fee/stop-aware execution backtests and prospective paper validation.",
          "- The multiple filters compared were not adjusted for multiple testing.",
          "- No orders, production changes, or live signal approvals.",
          ""]
    return "\n".join(out)


def main():
    doc=run()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n")
    OUTPUT_MD.write_text(to_md(doc))
    print("SOL_V82_OLDER_HISTORICAL_REPLICATION",doc["earlierVerifiedChecksumArchives"],
          json.dumps(doc["combinedHistorical"]),flush=True)


if __name__=="__main__":
    main()
