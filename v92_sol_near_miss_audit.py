#!/usr/bin/env python3
"""Descriptive near-miss audit for the frozen SOL Star/Harami+sweep rule.

This is NOT a new filter or a performance-tuned strategy. It replays the SOL
V9.1 control with an observation-only gate and counts opposing closed Star /
confirmed Harami patterns both with and without the prior-20 sweep condition.
The gate never vetoes, and baseline parity is required.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from market_structure import candles_from_history
from signal_quality_v7 import evaluate_bos_quality
from v7_paper_comparison import read_history
from v92_bull_bear_candle_invalidation import HOUR, SYMBOLS, stamp, metrics
from v92_multi_candle_invalidation import warnings_at_retest
from v92_sol_holdout_backtest import START, END, validate_manifest

FAMILIES={"STAR","HARAMI_CONFIRMED"}
SYMBOL="SOLUSDT"


def make_diagnostic_gate(four,audit):
    def gate(one,active,retest):
        at=int(retest["t"])+HOUR
        warnings=warnings_at_retest(
            one,four,at,active["side"],FAMILIES,require_sweep=False)
        if at>=START:
            audit["baselineRetests"]+=1
            if warnings:
                audit["retestsWithOpposingPattern"]+=1
                swept=[w for w in warnings
                       if w.get("prior20LiquiditySweepAndReentry") is True]
                if swept:
                    audit["retestsWithQualifyingSweep"]+=1
                else:
                    audit["retestsWithPatternButNoSweep"]+=1
                for w in warnings:
                    suffix="_WITH_SWEEP" if w.get("prior20LiquiditySweepAndReentry") else "_NO_SWEEP"
                    audit[w["name"]+"_"+w["tf"]+suffix]+=1
                if len(audit["examples"])<50:
                    audit["examples"].append({
                      "retestUTC":stamp(at),
                      "activeBOSDirection":active["side"],
                      "patterns":warnings,
                    })
        # Diagnostic arm: observe only, never reject a retest.
        return {"passed":True,"reasons":[]}
    return gate


def audit_dict(a):
    return {
      "baselineRetests":a["baselineRetests"],
      "retestsWithOpposingPattern":a["retestsWithOpposingPattern"],
      "retestsWithQualifyingSweep":a["retestsWithQualifyingSweep"],
      "retestsWithPatternButNoSweep":a["retestsWithPatternButNoSweep"],
      "patternInstances":{k:v for k,v in a.items()
        if isinstance(v,int) and k not in {
          "baselineRetests","retestsWithOpposingPattern",
          "retestsWithQualifyingSweep","retestsWithPatternButNoSweep"}},
      "examples":a["examples"],
    }


def run(histories,manifest):
    validate_manifest(manifest)
    h=histories["1hour"][SYMBOL+"_PERP.A"]
    four=histories["4hour"][SYMBOL+"_PERP.A"]
    daily=histories["daily"][SYMBOL+"_PERP.A"]
    closedh=candles_from_history(h,"1hour",END)
    closedf=candles_from_history(four,"4hour",END)
    closedd=candles_from_history(daily,"daily",END)
    if (len(closedh)!=21216 or len(closedf)!=5304 or len(closedd)!=884):
        raise ValueError("V92_SOL_NEARMISS_HOLDOUT_HISTORY_LENGTH_INVALID")
    baseline=replay_pair(
      h,four,daily,as_of=END,retest_hours=4,
      bos_quality_filter=evaluate_bos_quality)
    audit=Counter();audit["examples"]=[]
    diagnostic=replay_pair(
      h,four,daily,as_of=END,retest_hours=4,
      bos_quality_filter=evaluate_bos_quality,
      retest_quality_filter=make_diagnostic_gate(closedf,audit))
    base_score=metrics(baseline,START,END)
    diag_score=metrics(diagnostic,START,END)
    for key in ("trades","wins","totalNetR9BpsPerSide",
                "totalNetR25BpsPerSideStress"):
        a,b=base_score[key],diag_score[key]
        if (a!=b if isinstance(a,int) else abs(a-b)>.00001):
            raise ValueError("V92_SOL_NEARMISS_OBSERVATION_ONLY_PARITY_FAILED_"+key)
    return {
      "status":"V92_SOL_HOLDOUT_NEARMISS_DIAGNOSTIC_OBSERVATION_ONLY",
      "periodUTC":[stamp(START),stamp(END)],
      "warmupUTC":["2022-05-01T00:00:00Z",stamp(START)],
      "source":{"checksumsVerified":manifest["checksumsVerified"],
                "monthlyArchives":len(manifest["inputFiles"]),
                "source":"Official Binance USD-M monthly 1H; SHA256 verified; 4H/Daily aggregated"},
      "frozenRuleUnderInspection":{
        "opposingFamilies":["STAR","HARAMI_CONFIRMED"],
        "strictVetoAlsoRequiresPrior20SweepAndReentry":True,
        "thisDiagnosticIgnoresSweepForCountingOnly":True,
        "noVetoApplied":True,"noThresholdRetuned":True,
      },
      "audit":audit_dict(audit),
      "baselineV91":{"trades":base_score["trades"],"wins":base_score["wins"],
        "winRatePct":base_score["winRatePct"],
        "netR":base_score["totalNetR9BpsPerSide"],
        "stressNetR":base_score["totalNetR25BpsPerSideStress"]},
      "diagnosticReplayExactlyMatchesBaseline":{
        "trades":diag_score["trades"]==base_score["trades"],
        "wins":diag_score["wins"]==base_score["wins"],
        "netR":abs(diag_score["totalNetR9BpsPerSide"]-base_score["totalNetR9BpsPerSide"])<.00001,
        "stressNetR":abs(diag_score["totalNetR25BpsPerSideStress"]-base_score["totalNetR25BpsPerSideStress"])<.00001,
      },
      "noBrokerOrders":True,"noUserNotifications":True,
      "noVetoOrProductionChanges":True,"paperOnlyNotRealPnL":True,
      "notAnIndependentNewPerformanceHoldout":True,
    }


def markdown(x):
    a=x["audit"]
    b=x["baselineV91"]
    return "\\n".join([
      "# SOL Star/Harami near-miss diagnostic (observation only)","",
      "**No veto was applied. This is a descriptive diagnostic, not a performance test.**",
      "Period: {} to {} (exclusive).".format(*x["periodUTC"]),
      "Source: {} SHA256-verified official Binance monthly archives.".format(x["source"]["monthlyArchives"]),
      "",
      "| V9.1 SOL retests | Count |",
      "|---|---:|",
      f"| Baseline retests assessed | {a['baselineRetests']} |",
      f"| Retests with opposing Star/Harami, sweep ignored | {a['retestsWithOpposingPattern']} |",
      f"| Of those, prior-20 sweep present | {a['retestsWithQualifyingSweep']} |",
      f"| Pattern present but no prior-20 sweep | {a['retestsWithPatternButNoSweep']} |",
      "",
      "| V9.1 baseline | Value |",
      "|---|---:|",
      f"| Closed trades | {b['trades']} |",
      f"| Net R, 9 bp/side | {b['netR']:.4f} |",
      f"| Stress R, 25 bp/side | {b['stressNetR']:.4f} |",
      "",
      "The diagnostic gate passed every retest; its replay was required to match the unmodified V9.1 baseline exactly.",
      "This count does not authorize relaxing the sweep requirement. Any alternative rule must be frozen as a separate future prospective experiment.",
      "No orders, alerts, or production changes.",
      "",
    ])


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",default="v92_sol_holdout_archive")
    p.add_argument("--out",default="forward/v92_sol_holdout_2022_2024_nearmiss")
    a=p.parse_args()
    root=Path(a.archive)
    manifest=json.loads((root/"source_manifest.json").read_text())
    validate_manifest(manifest)
    histories={tf:read_history(str(root/("history_"+tf+".json"))
      ) for tf in ("1hour","4hour","daily")}
    result=run(histories,manifest)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    (out/"diagnostic.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    (out/"diagnostic.md").write_text(markdown(result)+"\n")
    print("V92_SOL_NEARMISS_DIAGNOSTIC_COMPLETE",json.dumps({
      "baselineRetests":result["audit"]["baselineRetests"],
      "opposingPatternRetests":result["audit"]["retestsWithOpposingPattern"],
      "withSweep":result["audit"]["retestsWithQualifyingSweep"],
      "withoutSweep":result["audit"]["retestsWithPatternButNoSweep"],
      "baselineTrades":result["baselineV91"]["trades"]}),flush=True)


if __name__=="__main__":
    main()
